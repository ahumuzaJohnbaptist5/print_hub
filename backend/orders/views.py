import os
import mimetypes

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from stations.models import Station

from .models import Order

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def _user_role(user):
    return getattr(user, 'role', None)


def _is_staff_role(user):
    return _user_role(user) in ('admin', 'agent')


def validate_upload_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        return f'Invalid file type. Allowed: {allowed}'
    if file.size > MAX_UPLOAD_SIZE:
        return 'File size exceeds 10MB limit.'
    return None


@login_required
def dashboard_view(request):
    orders = Order.objects.filter(client=request.user).order_by('-created_at')
    return render(request, 'orders/dashboard.html', {'orders': orders})


@login_required
def upload_view(request):
    stations = Station.objects.all()
    upload_error = None

    if request.method == 'POST':
        file = request.FILES.get('file')
        page_count = request.POST.get('page_count', 1)
        is_color = request.POST.get('is_color', 'False') == 'True'
        is_double_sided = request.POST.get('is_double_sided') == 'on'
        station_id = request.POST.get('station')

        if not file:
            upload_error = 'Please select a file.'
        else:
            upload_error = validate_upload_file(file)

        if upload_error:
            return render(request, 'orders/upload.html', {
                'stations': stations,
                'upload_error': upload_error,
            })

        station = None
        if station_id:
            station = Station.objects.filter(id=station_id).first()

        try:
            order = Order.objects.create(
                client=request.user,
                station=station,
                file=file,
                file_name=file.name,
                page_count=int(page_count),
                is_color=is_color,
                is_double_sided=is_double_sided,
                status='pending',
            )
            messages.success(
                request,
                f'Order submitted successfully! Total: {order.total_price:,} UGX',
            )
            return redirect('dashboard')
        except Exception as e:
            upload_error = f'Error creating order: {str(e)}'
            return render(request, 'orders/upload.html', {
                'stations': stations,
                'upload_error': upload_error,
            })

    return render(request, 'orders/upload.html', {'stations': stations})


@login_required
def verify_payment_view(request):
    order_id = request.GET.get('order_id') or request.POST.get('order_id')
    if not order_id:
        messages.error(request, 'Missing order ID.')
        return redirect('dashboard')

    order = get_object_or_404(Order, id=order_id, client=request.user)

    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        tx_ref = request.POST.get('tx_ref', '')

        if not transaction_id:
            messages.error(request, 'Missing transaction ID.')
            return redirect('dashboard')

        if not settings.FLUTTERWAVE_SECRET_KEY:
            messages.error(request, 'Payment verification is not configured.')
            return redirect('dashboard')

        url = f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify'
        headers = {
            'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            data = response.json()

            if (
                data.get('status') == 'success'
                and data.get('data', {}).get('status') == 'successful'
            ):
                paid_amount = int(float(data['data'].get('amount', 0)))
                if paid_amount != order.total_price:
                    messages.error(request, 'Payment amount does not match order total.')
                    return redirect('dashboard')

                order.status = 'paid'
                order.transaction_id = str(transaction_id)
                order.tx_ref = tx_ref or data['data'].get('tx_ref', '')
                order.paid_at = timezone.now()
                order.save()
                messages.success(request, 'Payment verified successfully!')
            else:
                messages.error(request, 'Payment verification failed.')
        except Exception as e:
            messages.error(request, f'Error verifying payment: {str(e)}')

        return redirect('dashboard')

    return render(request, 'orders/verify_payment.html', {
        'order': order,
        'flutterwave_public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
    })


@login_required
def admin_dashboard_view(request):
    if _user_role(request.user) != 'admin':
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')

    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'orders/admin_dashboard.html', {'orders': orders})


@login_required
def agent_dashboard_view(request):
    if _user_role(request.user) != 'agent':
        messages.error(request, 'Access denied. Agent only.')
        return redirect('dashboard')

    orders = Order.objects.filter(
        status__in=['paid', 'printing', 'ready'],
    ).order_by('-created_at')

    return render(request, 'orders/agent_dashboard.html', {'orders': orders})


@login_required
def update_order_status_view(request, order_id):
    if not _is_staff_role(request.user):
        return HttpResponseForbidden('You do not have permission to update order status.')

    order = get_object_or_404(Order, id=order_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        valid_statuses = ['pending', 'paid', 'printing', 'ready', 'collected']
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status.')
            return redirect('dashboard')

        order.status = new_status
        order.save()
        messages.success(request, f'Order status updated to {new_status}.')

        if _user_role(request.user) == 'admin':
            return redirect('admin_dashboard')
        if _user_role(request.user) == 'agent':
            return redirect('agent_dashboard')

        return redirect('dashboard')

    return render(request, 'orders/update_status.html', {'order': order})


@login_required
def download_order_file_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    user = request.user

    if _user_role(user) not in ('admin', 'agent') and order.client != user:
        return HttpResponseForbidden('You do not have permission to download this file.')

    if not order.file:
        messages.error(request, 'File not found.')
        return redirect('dashboard')

    content_type, _ = mimetypes.guess_type(order.file_name)
    response = FileResponse(order.file.open('rb'), content_type=content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{order.file_name}"'
    return response


def order_track_view(request):
    orders = None
    lookup_error = None

    if request.method == 'POST':
        order_id = request.POST.get('order_id', '').strip()
        email = request.POST.get('email', '').strip()

        if order_id:
            orders = Order.objects.filter(id=order_id)
            if not orders.exists():
                lookup_error = 'No order found with that order ID.'
                orders = None
        elif email:
            orders = Order.objects.filter(client__email__iexact=email).order_by('-created_at')
            if not orders.exists():
                lookup_error = 'No orders found for that email address.'
                orders = None
        else:
            lookup_error = 'Please enter an order ID or email address.'

    return render(request, 'orders/track.html', {
        'orders': orders,
        'lookup_error': lookup_error,
    })
