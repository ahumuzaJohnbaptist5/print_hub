import os
import mimetypes
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import FileResponse, HttpResponseForbidden, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from django.views.decorators.cache import cache_control
from PIL import Image, ImageDraw, ImageFont
import io

from stations.models import Station

from .models import Order, SystemSettings, DeliveryZone, Announcement
from .utils import apply_order_status_change, send_delayed_order_email

User = get_user_model()

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg', '.pptx'}
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


def _can_view_order(user, order):
    if _user_role(user) in ('admin', 'agent'):
        return True
    return order.client == user


@login_required
def dashboard_view(request):
    orders = Order.objects.filter(client=request.user).order_by('-created_at')

    stats = Order.objects.filter(client=request.user).aggregate(
        total_orders=Count('id'),
        completed_orders=Count('id', filter=Q(status='collected')),
        pending_orders=Count('id', filter=Q(status='pending')),
        total_spent=Sum('total_price', filter=Q(status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']))
    )

    return render(request, 'orders/dashboard.html', {
        'orders': orders,
        'stats': stats,
    })


def upload_view(request):
    stations = Station.objects.all()
    delivery_zones = DeliveryZone.objects.filter(is_active=True)
    upload_error = None

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in or create an account to complete your upload.')
            return redirect('/auth/login/?next=/upload/')

        file = request.FILES.get('file')
        page_count = request.POST.get('page_count', 1)
        is_color = request.POST.get('is_color', 'False') == 'True'
        is_double_sided = request.POST.get('is_double_sided') == 'on'
        station_id = request.POST.get('station')

        binding = request.POST.get('binding', 'none')
        delivery_type = request.POST.get('delivery_type', 'pickup')
        delivery_zone_id = request.POST.get('delivery_zone')
        notes = request.POST.get('notes', '').strip()

        if not file:
            upload_error = 'Please select a file.'
        else:
            upload_error = validate_upload_file(file)

        if upload_error:
            return render(request, 'orders/upload.html', {
                'stations': stations,
                'delivery_zones': delivery_zones,
                'upload_error': upload_error,
            })

        station = Station.objects.filter(id=station_id).first() if station_id else None

        delivery_zone = None
        if delivery_type == 'delivery' and delivery_zone_id:
            delivery_zone = DeliveryZone.objects.filter(id=delivery_zone_id).first()

        try:
            page_count_int = int(page_count)
            if page_count_int < 1:
                raise ValueError("Page count must be at least 1")

            order = Order.objects.create(
                client=request.user,
                station=station,
                file=file,
                file_name=file.name,
                page_count=page_count_int,
                is_color=is_color,
                is_double_sided=is_double_sided,
                binding=binding,
                delivery_type=delivery_type,
                delivery_zone=delivery_zone,
                notes=notes,
                status='pending',
            )

            try:
                send_order_confirmation_email(order)
            except Exception:
                pass

            messages.success(request, f'Order #{order.id} submitted! Total: {order.total_price:,.0f} UGX')
            return redirect('order_receipt', order_id=order.id)

        except ValueError as e:
            upload_error = f'Invalid page count: {str(e)}'
        except Exception as e:
            upload_error = f'Error creating order: {str(e)}'

    return render(request, 'orders/upload.html', {
        'stations': stations,
        'delivery_zones': delivery_zones,
        'upload_error': upload_error,
    })


@login_required
def order_receipt_view(request, order_id):
    order = get_object_or_404(Order.objects.select_related('station', 'delivery_zone'), id=order_id)

    if not _can_view_order(request.user, order):
        return HttpResponseForbidden('You do not have permission to view this receipt.')

    estimated_ready = order.estimated_ready_at()

    payment = None
    try:
        from payments.models import Payment
        payment = Payment.objects.filter(order=order).first()
    except Exception:
        pass

    return render(request, 'orders/receipt.html', {
        'order': order,
        'estimated_ready': estimated_ready,
        'payment': payment,
    })


def _build_order_queryset(request):
    qs = Order.objects.select_related('client', 'station', 'delivery_zone').order_by('-created_at')

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    station_id = request.GET.get('station', '').strip()
    if station_id:
        qs = qs.filter(station_id=station_id)

    date_filter = request.GET.get('date', '').strip()
    now = timezone.now()
    if date_filter == 'today':
        qs = qs.filter(created_at__date=now.date())
    elif date_filter == 'week':
        qs = qs.filter(created_at__gte=now - timedelta(days=7))
    elif date_filter == 'month':
        qs = qs.filter(created_at__gte=now - timedelta(days=30))

    search = request.GET.get('search', '').strip()
    if search:
        if search.isdigit():
            qs = qs.filter(Q(id=int(search)) | Q(client__email__icontains=search))
        else:
            qs = qs.filter(
                Q(client__email__icontains=search)
                | Q(client__username__icontains=search)
                | Q(file_name__icontains=search)
            )

    return qs


def _order_summary_counts():
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        'total': Order.objects.count(),
        'pending': Order.objects.filter(status='pending').count(),
        'paid': Order.objects.filter(status='paid').count(),
        'printing': Order.objects.filter(status='printing').count(),
        'in_transit': Order.objects.filter(status='in_transit').count(),
        'ready': Order.objects.filter(status='ready').count(),
        'collected_today': Order.objects.filter(status='collected', collected_at__gte=today_start).count(),
        'cancelled': Order.objects.filter(status='cancelled').count(),
        'overdue': Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']).count(),
    }


@login_required
def admin_dashboard_view(request):
    if _user_role(request.user) != 'admin':
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'assign_agent':
            agent_id = request.POST.get('agent_id')
            station_id = request.POST.get('agent_station_id') or None
            agent = get_object_or_404(User, id=agent_id, role='agent')
            if hasattr(agent, 'station'):
                agent.station_id = station_id
                agent.save(update_fields=['station'])
                messages.success(request, f'Station updated for agent {agent.username}.')
            else:
                messages.error(request, 'Agent model does not have station field.')
            return redirect('admin_dashboard')

        if action == 'bulk_status':
            new_status = request.POST.get('bulk_status')
            order_ids = request.POST.getlist('order_ids')
            valid = ['printing', 'in_transit', 'ready', 'collected', 'cancelled']
            if new_status in valid and order_ids:
                updated_count = 0
                for oid in order_ids:
                    order = Order.objects.filter(id=oid).first()
                    if order:
                        if apply_order_status_change(order, new_status, request.user):
                            updated_count += 1
                messages.success(request, f'Updated {updated_count} order(s) to {new_status}.')
            return redirect(request.get_full_path() or 'admin_dashboard')

        if action == 'update_announcement':
            if request.POST.get('delete_announcement'):
                Announcement.objects.filter(is_active=True).update(is_active=False)
                messages.success(request, 'Announcement removed.')
            else:
                title = request.POST.get('announcement_title', 'Announcement')
                message_text = request.POST.get('announcement_message', '')
                color = request.POST.get('announcement_color', 'bg-blue-600')
                is_active = request.POST.get('announcement_active') == 'on'
                show_home = request.POST.get('announcement_home') == 'on'

                if message_text:
                    Announcement.objects.update_or_create(
                        is_active=True,
                        defaults={
                            'title': title,
                            'message': message_text,
                            'background_color': color,
                            'is_active': is_active,
                            'show_on_home': show_home,
                        }
                    )
                    messages.success(request, 'Announcement updated!')
                else:
                    messages.error(request, 'Message cannot be empty.')
            return redirect('admin_dashboard')

    orders_qs = _build_order_queryset(request)
    summary = _order_summary_counts()

    overdue_count = 0
    for order in orders_qs.filter(status__in=['paid', 'printing', 'in_transit', 'ready']):
        if order.is_overdue:
            overdue_count += 1
    summary['overdue'] = overdue_count

    paginator = Paginator(orders_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    agents = User.objects.filter(role='agent').select_related('station')
    stations = Station.objects.all()

    system_settings = SystemSettings.load()

    active_filters = []
    for key, label in [('status', 'Status'), ('station', 'Station'), ('date', 'Date'), ('search', 'Search')]:
        val = request.GET.get(key, '').strip()
        if val:
            active_filters.append({'key': key, 'value': val, 'label': label})

    return render(request, 'orders/admin_dashboard.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'summary': summary,
        'agents': agents,
        'stations': stations,
        'status_choices': Order.STATUS_CHOICES,
        'active_filters': active_filters,
        'filter_status': request.GET.get('status', ''),
        'filter_station': request.GET.get('station', ''),
        'filter_date': request.GET.get('date', ''),
        'filter_search': request.GET.get('search', ''),
        'total_filtered': orders_qs.count(),
        'system_settings': system_settings,
        'active_announcement': Announcement.get_active(),
    })


@login_required
def toggle_system_pause_view(request):
    if _user_role(request.user) != 'admin':
        return HttpResponseForbidden("Admin access only.")

    sys_settings = SystemSettings.load()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'pause':
            if not sys_settings.is_paused:
                sys_settings.is_paused = True
                sys_settings.pause_reason = request.POST.get('reason', 'Unforeseen circumstances')
                sys_settings.pause_started_at = timezone.now()
                sys_settings.save()
                messages.success(request, "System timers PAUSED successfully.")

        elif action == 'resume':
            if sys_settings.is_paused:
                if sys_settings.pause_started_at:
                    sys_settings.total_paused_seconds += (timezone.now() - sys_settings.pause_started_at).total_seconds()
                sys_settings.is_paused = False
                sys_settings.pause_started_at = None
                sys_settings.save()
                messages.success(request, "System timers RESUMED successfully.")

    return redirect('admin_dashboard')


def is_agent_or_admin(user):
    return user.is_authenticated and (user.role == 'agent' or user.is_staff)


@login_required
@user_passes_test(is_agent_or_admin, login_url='login')
def agent_dashboard_view(request):
    if request.user.role == 'agent':
        if request.user.station:
            orders = Order.objects.filter(
                station=request.user.station
            ).select_related('client', 'delivery_zone').order_by('-created_at')
        else:
            orders = Order.objects.none()
            messages.warning(request, 'You are not assigned to any station.')
    else:
        orders = Order.objects.select_related(
            'client', 'station', 'delivery_zone'
        ).order_by('-created_at')

    agent_earnings = None
    if request.user.role == 'agent':
        try:
            from finances.models import AgentEarning
            agent_earnings = AgentEarning.objects.filter(
                agent=request.user
            ).aggregate(
                total_earned=Sum('commission_amount'),
                pending=Sum('commission_amount', filter=Q(is_paid=False)),
                paid=Sum('commission_amount', filter=Q(is_paid=True)),
                total_orders=Count('id')
            )
        except Exception:
            pass

    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')

        if action == 'update_status':
            new_status = request.POST.get('status')
            order = get_object_or_404(Order, id=order_id)

            if request.user.role == 'agent' and order.station != request.user.station:
                messages.error(request, 'You can only update orders for your station.')
                return redirect('agent_dashboard')

            if apply_order_status_change(order, new_status, request.user):
                messages.success(request, f'Order #{order.id} updated to {order.get_status_display()}.')
            else:
                messages.info(request, f'Order #{order.id} status unchanged.')

        elif action == 'notify_delay':
            order = get_object_or_404(Order, id=order_id)
            reason = request.POST.get('delay_reason', '').strip()

            from notifications.models import Notification
            Notification.create_notification(
                user=order.client,
                notification_type='order_delayed',
                title='Order Delayed',
                message=f'Your Order #{order.id} ({order.file_name}) has been delayed. Reason: {reason}',
                link=f'/orders/{order.id}/receipt/'
            )

            send_delayed_order_email(order, reason)

            messages.success(request, f'Delay notification sent for Order #{order.id}.')

        elif action == 'cancel_order':
            order = get_object_or_404(Order, id=order_id)
            if order.status not in ['collected', 'cancelled']:
                reason = request.POST.get('cancellation_reason', '').strip()
                order.status = 'cancelled'
                order.cancellation_reason = reason
                order.cancelled_at = timezone.now()
                order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])
                messages.success(request, f'Order #{order.id} has been CANCELLED.')
            else:
                messages.error(request, 'Cannot cancel this order.')

        elif action == 'postpone_order':
            order = get_object_or_404(Order, id=order_id)
            if order.status not in ['collected', 'cancelled']:
                try:
                    extra_minutes = int(request.POST.get('extra_minutes', 30))
                    if extra_minutes > 0:
                        order.postponed_minutes += extra_minutes
                        order.save(update_fields=['postponed_minutes'])
                        messages.success(request, f'Order #{order.id} postponed by {extra_minutes} minutes.')
                    else:
                        messages.error(request, 'Please enter a valid number of minutes.')
                except ValueError:
                    messages.error(request, 'Invalid number of minutes.')
            else:
                messages.error(request, 'Cannot postpone this order.')

        elif action == 'add_note':
            order = get_object_or_404(Order, id=order_id)
            note = request.POST.get('note', '').strip()
            if note:
                existing_notes = order.notes or ''
                order.notes = f"{existing_notes}\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {request.user.username}: {note}".strip()
                order.save(update_fields=['notes'])
                messages.success(request, f'Note added to Order #{order.id}.')

        return redirect('agent_dashboard')

    return render(request, 'orders/agent_dashboard.html', {
        'orders': orders,
        'agent_earnings': agent_earnings,
    })


@login_required
def update_order_status_view(request, order_id):
    if not _is_staff_role(request.user):
        return HttpResponseForbidden('You do not have permission to update order status.')

    order = get_object_or_404(Order, id=order_id)

    if _user_role(request.user) == 'agent':
        if not request.user.station or order.station_id != request.user.station_id:
            return HttpResponseForbidden('You can only update orders for your assigned station.')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = ['pending', 'paid', 'printing', 'in_transit', 'ready', 'collected', 'cancelled']
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status.')
            return redirect('dashboard')

        if apply_order_status_change(order, new_status, request.user):
            messages.success(request, f'Order #{order.id} status updated to {order.get_status_display()}.')
        else:
            messages.error(request, 'Failed to update order status.')

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


def _get_tracked_orders(order_id=None, email=None):
    qs = Order.objects.select_related('station', 'client', 'delivery_zone')
    if order_id: return qs.filter(id=order_id)
    if email: return qs.filter(client__email__iexact=email).order_by('-created_at')
    return Order.objects.none()


def order_track_view(request):
    orders = None
    lookup_error = None
    order_id = request.GET.get('order_id', '').strip() or request.POST.get('order_id', '').strip()
    email = request.GET.get('email', '').strip() or request.POST.get('email', '').strip()

    if order_id or email:
        if order_id:
            orders = _get_tracked_orders(order_id=order_id)
            if not orders.exists(): lookup_error = 'No order found with that order ID.'; orders = None
        elif email:
            orders = _get_tracked_orders(email=email)
            if not orders.exists(): lookup_error = 'No orders found for that email address.'; orders = None

    timeline_steps = [
        ('submitted', 'Submitted', 'created_at'), ('paid', 'Paid', 'paid_at'),
        ('printing', 'Printing', 'printing_at'), ('in_transit', 'In Transit', 'in_transit_at'),
        ('ready', 'Ready for Pickup', 'ready_at'), ('collected', 'Collected', 'collected_at'),
    ]

    order_timelines = []
    if orders:
        status_step_map = {'pending': 0, 'paid': 1, 'printing': 2, 'in_transit': 3, 'ready': 4, 'collected': 5}
        for order in orders:
            current_step = status_step_map.get(order.status, 0)
            if order.status == 'cancelled': current_step = -1
            steps = []
            for i, (key, label, ts_field) in enumerate(timeline_steps):
                ts = getattr(order, ts_field, None)
                if order.status == 'cancelled': state = 'cancelled'
                elif i < current_step: state = 'completed'
                elif i == current_step: state = 'current'
                else: state = 'future'
                steps.append({'key': key, 'label': label, 'timestamp': ts, 'state': state})
            order_timelines.append({
                'order': order, 'steps': steps, 'estimated_ready': order.estimated_ready_at(),
                'is_overdue': order.is_overdue,
                'progress_width': int(current_step / (len(timeline_steps) - 1) * 100) if len(timeline_steps) > 1 and current_step >= 0 else 0,
            })

    return render(request, 'orders/track.html', {
        'orders': orders, 'order_timelines': order_timelines,
        'lookup_error': lookup_error, 'query_order_id': order_id, 'query_email': email,
    })


def home_view(request):
    try:
        total_orders = Order.objects.count()
        stations = Station.objects.filter(is_active=True).count()
    except Exception:
        total_orders = 0; stations = 0
    return render(request, 'home.html', {'total_orders': total_orders, 'total_stations': stations})


@login_required
def live_board_view(request):
    return render(request, 'orders/live_board.html')


def live_board_api_view(request):
    active_statuses = ['paid', 'printing', 'in_transit', 'ready']
    orders = Order.objects.filter(status__in=active_statuses).select_related('station', 'client')
    cancelled_orders = Order.objects.filter(status='cancelled', cancelled_at__gte=timezone.now() - timedelta(minutes=30)).select_related('station', 'client')
    all_orders = list(orders) + list(cancelled_orders)
    sys_settings = SystemSettings.load()

    board_data = []
    for order in all_orders:
        priority = order.priority_info
        board_data.append({
            'id': order.id, 'client': order.client.username,
            'station': order.station.name if order.station else 'Unassigned',
            'file_name': order.file_name, 'status': order.get_status_display(),
            'status_raw': order.status, 'time_left': priority['time_display'],
            'remaining_seconds': priority['remaining_seconds'],
            'priority': priority['display'], 'priority_level': priority['level'],
            'is_overdue': priority['is_overdue'], 'page_count': order.page_count,
            'is_color': order.is_color, 'binding': order.get_binding_display(),
        })

    board_data.sort(key=lambda x: (x['status_raw'] == 'cancelled', x['remaining_seconds']))

    response = JsonResponse({
        'orders': board_data, 'system_paused': sys_settings.is_paused,
        'pause_reason': sys_settings.pause_reason, 'total_active': len(orders),
        'total_cancelled': len(cancelled_orders), 'last_updated': timezone.now().isoformat(),
    })
    response["Access-Control-Allow-Origin"] = "*"
    return response


def all_links_view(request):
    links_data = [
        ('home', 'Home', 'Landing page'), ('dashboard', 'Client Dashboard', 'View your past orders'),
        ('upload', 'Upload / Place Order', 'Upload files for printing'),
        ('track_order', 'Track Order', 'Track order status by ID or email'),
        ('admin_dashboard', 'Admin Dashboard', 'Admin overview and management'),
        ('agent_dashboard', 'Agent Dashboard', 'Station agent dashboard'),
        ('live_board', 'Live Board', 'Full screen live board'),
        ('login', 'Login', 'User login page'), ('register', 'Register', 'User registration page'),
    ]
    links = []
    for url_name, name, desc in links_data:
        try: url = reverse(url_name)
        except Exception: url = '#'
        links.append({'name': name, 'url': url, 'desc': desc})
    links.append({'name': 'Django Admin', 'url': '/admin/', 'desc': 'Built-in database admin panel'})
    return render(request, 'all_links.html', {'links': links})


# ============================================================
# Live Board Preview Image (for social sharing)
# ============================================================

@cache_control(max_age=60)
def live_board_preview_image(request):
    active_statuses = ['paid', 'printing', 'in_transit', 'ready']
    orders = Order.objects.filter(
        status__in=active_statuses
    ).select_related('station', 'client').order_by('id')

    total_active = orders.count()
    ready_count = orders.filter(status='ready').count()
    printing_count = orders.filter(status='printing').count()
    cancelled_count = Order.objects.filter(
        status='cancelled',
        cancelled_at__gte=timezone.now() - timedelta(minutes=30)
    ).count()

    img = Image.new('RGB', (1200, 630), color='#0f172a')
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 46)
        font_subtitle = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
        font_body = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
        font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((50, 50), "PrintHub Live Board", fill='#e2e8f0', font=font_title)
    draw.text((50, 110), "Kabale University Printing Service", fill='#94a3b8', font=font_subtitle)

    stats = [
        ("Active", total_active, '#22c55e'),
        ("Ready", ready_count, '#3b82f6'),
        ("Printing", printing_count, '#a855f7'),
        ("Total Today", total_active + cancelled_count, '#f59e0b'),
    ]
    x = 50
    for label, value, color in stats:
        draw.text((x, 180), label, fill='#94a3b8', font=font_small)
        draw.text((x, 210), str(value), fill=color, font=font_body)
        x += 250

    draw.rectangle([50, 280, 1150, 320], fill='#1e293b')
    headers = [
        ("Order", 70), ("Client", 200), ("Station", 400),
        ("Status", 600), ("Time Left", 800), ("Priority", 1000)
    ]
    for text, x_pos in headers:
        draw.text((x_pos, 285), text, fill='#94a3b8', font=font_small)

    y = 330
    for order in orders[:4]:
        priority = order.priority_info
        items = [
            (70, f"#{order.id}"),
            (200, order.client.username[:12]),
            (400, order.station.name[:15] if order.station else '—'),
            (600, order.get_status_display()),
            (800, priority['time_display']),
            (1000, priority['display']),
        ]
        for x_pos, text in items:
            draw.text((x_pos, y), text, fill='#e2e8f0', font=font_small)
        y += 55

    draw.text((50, 570), "Scan to track your order  |  printlink.pythonanywhere.com", fill='#64748b', font=font_small)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return HttpResponse(buffer, content_type='image/png')


# ============================================================
# Email helpers
# ============================================================

def send_order_confirmation_email(order):
    subject = f'Order #{order.id} Confirmed - PrintHub'
    message = f"""
    Dear {order.client.username},

    Your print order has been received!

    Order Details:
    - Order ID: #{order.id}
    - File: {order.file_name}
    - Pages: {order.page_count}
    - Color: {'Yes' if order.is_color else 'No'}
    - Double-sided: {'Yes' if order.is_double_sided else 'No'}
    - Binding: {order.get_binding_display()}
    - Total: {order.total_price:,.0f} UGX

    Track your order at: {settings.SITE_URL}/track/?order_id={order.id}

    Thank you for choosing PrintHub!
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [order.client.email], fail_silently=True)
