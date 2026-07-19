from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from datetime import timedelta
from decimal import Decimal
import re
import logging

from .models import Payment, PaymentReminder, PaymentMethod
from orders.models import Order
from finances.models import MerchantSettings
from notifications.models import Notification

logger = logging.getLogger(__name__)


@login_required
def payment_page(request, order_id):
    """
    Unified payment page - Copy & Pay with transaction ID submission.
    Shows merchant details and accepts payment confirmation.
    """
    order = get_object_or_404(
        Order.objects.select_related('delivery_zone', 'station'), 
        id=order_id, 
        client=request.user
    )
    
    if order.status not in ['pending']:
        messages.warning(request, f'This order is already {order.get_status_display().lower()}.')
        return redirect('order_receipt', order_id=order.id)
    
    existing_payment = Payment.objects.filter(order=order, status='pending').first()
    
    if existing_payment:
        time_diff = timezone.now() - existing_payment.created_at
        if time_diff > timedelta(minutes=30):
            existing_payment.mark_as_expired()
        else:
            messages.info(request, 'You have a pending payment waiting for approval.')
            return redirect('payment_status', payment_id=existing_payment.id)
    
    saved_methods = PaymentMethod.objects.filter(user=request.user, is_verified=True)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        customer_phone = request.POST.get('customer_phone', '').strip()
        transaction_id = request.POST.get('transaction_id', '').strip()
        transaction_message = request.POST.get('transaction_message', '').strip()
        save_method = request.POST.get('save_method') == 'on'
        
        errors = []
        if not payment_method or payment_method not in ['mtn', 'airtel']:
            errors.append('Please select a valid payment method.')
        if not customer_phone:
            errors.append('Please enter your phone number.')
        if not transaction_id:
            errors.append('Please enter the transaction ID.')
        if not transaction_message:
            errors.append('Please paste the transaction message for verification.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'payments/payment_page.html', {
                'order': order,
                'saved_methods': saved_methods,
            })
        
        merchant = MerchantSettings.get_merchant(payment_method)
        if merchant:
            merchant_phone = merchant.merchant_phone
            merchant_name = merchant.merchant_name
        else:
            merchant_phone = '0765511075' if payment_method == 'mtn' else '0775523720'
            merchant_name = 'Matovu Evaristo' if payment_method == 'mtn' else 'Ezra Nasaasira'
        
        customer_phone = re.sub(r'[^\d+]', '', customer_phone)
        if not customer_phone.startswith('+'):
            if customer_phone.startswith('0'):
                customer_phone = '+256' + customer_phone[1:]
            elif len(customer_phone) == 9:
                customer_phone = '+256' + customer_phone
        
        try:
            payment = Payment.objects.create(
                order=order,
                user=request.user,
                amount=order.total_price,
                payment_method=payment_method,
                payment_type='full',
                customer_phone=customer_phone,
                customer_name=request.user.get_full_name() or request.user.username,
                merchant_phone=merchant_phone,
                merchant_name=merchant_name,
                transaction_id=transaction_id.upper(),
                transaction_message=transaction_message,
                status='pending',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            
            if save_method:
                PaymentMethod.objects.get_or_create(
                    user=request.user,
                    phone_number=customer_phone,
                    defaults={
                        'payment_type': payment_method,
                        'is_default': not saved_methods.exists(),
                    }
                )
            
            send_payment_notification(payment)
            
            messages.success(request, 'Payment submitted successfully! Waiting for admin verification.')
            return redirect('payment_status', payment_id=payment.id)
            
        except Exception as e:
            logger.error(f"Payment creation failed: {str(e)}")
            messages.error(request, 'An error occurred. Please try again.')
    
    return render(request, 'payments/payment_page.html', {
        'order': order,
        'saved_methods': saved_methods,
    })


@login_required
def payment_status(request, payment_id):
    """Show payment status and details."""
    payment = get_object_or_404(
        Payment.objects.select_related('order', 'order__station'),
        id=payment_id
    )
    
    if payment.user != request.user and not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if payment.status == 'pending':
        time_diff = timezone.now() - payment.created_at
        if time_diff > timedelta(minutes=30):
            payment.mark_as_expired()
    
    order = payment.order
    
    return render(request, 'payments/payment_status.html', {
        'payment': payment,
        'order': order,
        'estimated_ready': order.estimated_ready_at(),
    })


@login_required
def payment_check_api(request, payment_id):
    """API endpoint for auto-refreshing payment status."""
    payment = get_object_or_404(Payment.objects.select_related('order'), id=payment_id)
    
    if payment.user != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    return JsonResponse({
        'status': payment.status,
        'order_status': payment.order.status,
        'approved_at': payment.approved_at.isoformat() if payment.approved_at else None,
        'rejected_at': payment.rejected_at.isoformat() if payment.rejected_at else None,
    })


@login_required
@require_POST
def extract_transaction_id(request):
    """AJAX endpoint to extract Transaction ID from pasted SMS/message."""
    message = request.POST.get('message', '')
    payment_method = request.POST.get('payment_method', '')
    
    if not message:
        return JsonResponse({'success': False, 'error': 'No message provided'})
    
    transaction_id = None
    amount = None
    sender_name = None
    
    if payment_method == 'mtn':
        patterns = [
            r'(?:Transaction\s*ID|Trans\s*ID|Txn\s*ID)[:\s]*([A-Z0-9]+)',
            r'\b(NP[A-Z0-9]+)\b',
        ]
    else:
        patterns = [
            r'(?:Ref|Reference|Transaction\s*ID)[:\s]*([A-Z0-9]+)',
            r'\b([A-Z]{2,}[0-9]{6,})\b',
        ]
    
    common_patterns = [
        r'\b([A-Z]{2,}[0-9]{6,})\b',
        r'\b([0-9]{10,})\b',
    ]
    
    for pattern in patterns + common_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            transaction_id = match.group(1).upper()
            break
    
    amount_patterns = [
        r'(?:Amount|Amt|UGX)[:\s]*([\d,]+)',
        r'(?:UGX|UG\.?X\.?)\s*([\d,]+)',
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                amount_str = match.group(1).replace(',', '')
                amount = float(amount_str)
            except ValueError:
                pass
            break
    
    name_patterns = [
        r'(?:From|Sender)[:\s]*([A-Za-z\s]+)',
        r'(?:paid by|sent by)\s*([A-Za-z\s]+)',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            sender_name = match.group(1).strip()
            break
    
    return JsonResponse({
        'success': True,
        'transaction_id': transaction_id,
        'amount': amount,
        'sender_name': sender_name,
        'is_valid': bool(transaction_id and len(transaction_id) >= 6),
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_approve_payments(request):
    """Admin page to approve/reject payments."""
    if request.method == 'POST':
        action = request.POST.get('action')
        payment_id = request.POST.get('payment_id')
        
        if not payment_id:
            messages.error(request, 'No payment selected.')
            return redirect('admin_approve_payments')
        
        payment = get_object_or_404(Payment.objects.select_related('order', 'user'), id=payment_id)
        
        if action == 'approve':
            reason = request.POST.get('approve_reason', '').strip()
            if payment.approve(approved_by=request.user):
                Notification.create_notification(
                    user=payment.user,
                    notification_type='payment_approved',
                    title='Payment Approved',
                    message=f'Your payment of {payment.amount} UGX for Order #{payment.order.id} has been approved.',
                    link=f'/orders/{payment.order.id}/receipt/'
                )
                try:
                    send_payment_confirmation(payment)
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}")
                messages.success(request, f'Payment #{payment.id} approved! Order #{payment.order.id} is now paid.')
            else:
                messages.error(request, 'Could not approve this payment.')
                
        elif action == 'reject':
            reason = request.POST.get('reject_reason', '').strip()
            if not reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('admin_approve_payments')
            if payment.reject(rejected_by=request.user, reason=reason):
                Notification.create_notification(
                    user=payment.user,
                    notification_type='payment_rejected',
                    title='Payment Rejected',
                    message=f'Your payment for Order #{payment.order.id} was not verified. Reason: {reason}',
                    link=f'/payments/order/{payment.order.id}/'
                )
                try:
                    send_payment_rejection(payment)
                except Exception as e:
                    logger.error(f"Failed to send rejection email: {e}")
                messages.warning(request, f'Payment #{payment.id} rejected. Customer will be notified.')
            else:
                messages.error(request, 'Could not reject this payment.')
        
        elif action == 'refund':
            reason = request.POST.get('refund_reason', '').strip()
            if payment.refund(refunded_by=request.user, reason=reason):
                messages.info(request, f'Payment #{payment.id} refunded.')
            else:
                messages.error(request, 'Could not refund this payment.')
        
        elif action == 'bulk_approve':
            payment_ids = request.POST.getlist('payment_ids')
            if payment_ids:
                approved_count = 0
                for pid in payment_ids:
                    try:
                        p = Payment.objects.get(id=pid, status='pending')
                        if p.approve(approved_by=request.user):
                            approved_count += 1
                            Notification.create_notification(
                                user=p.user,
                                notification_type='payment_approved',
                                title='Payment Approved',
                                message=f'Your payment of {p.amount} UGX for Order #{p.order.id} has been approved.',
                                link=f'/orders/{p.order.id}/receipt/'
                            )
                    except Payment.DoesNotExist:
                        pass
                messages.success(request, f'{approved_count} payment(s) approved successfully.')
            else:
                messages.error(request, 'No payments selected.')
        
        return redirect('admin_approve_payments')
    
    status_filter = request.GET.get('status', 'pending')
    payment_method = request.GET.get('method', '')
    date_filter = request.GET.get('date', 'today')
    search = request.GET.get('search', '').strip()
    
    now = timezone.now()
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0)
    elif date_filter == 'week':
        start_date = now - timedelta(days=7)
    elif date_filter == 'month':
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=1)
    
    payments = Payment.objects.select_related('order', 'user', 'approved_by', 'rejected_by').filter(created_at__gte=start_date)
    
    if status_filter:
        payments = payments.filter(status=status_filter)
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    if search:
        payments = payments.filter(
            Q(transaction_id__icontains=search) |
            Q(customer_phone__icontains=search) |
            Q(user__username__icontains=search) |
            Q(order__id__icontains=search)
        )
    
    summary = Payment.objects.filter(created_at__gte=start_date).aggregate(
        total_amount=Sum('amount'),
        total_count=Count('id'),
        approved_count=Count('id', filter=Q(status='approved')),
        pending_count=Count('id', filter=Q(status='pending')),
        rejected_count=Count('id', filter=Q(status='rejected')),
        refunded_count=Count('id', filter=Q(status='refunded')),
    )
    
    today_stats = Payment.get_today_summary()
    success_rate = Payment.get_success_rate(days=30)
    
    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'payments/admin_approve.html', {
        'page_obj': page_obj,
        'payments': page_obj.object_list,
        'summary': summary,
        'today_stats': today_stats,
        'success_rate': round(success_rate, 1),
        'filter_status': status_filter,
        'filter_method': payment_method,
        'filter_date': date_filter,
        'filter_search': search,
    })


@login_required
def payment_history(request):
    """User's payment history."""
    payments = Payment.objects.filter(user=request.user).select_related('order').order_by('-created_at')
    
    summary = payments.aggregate(
        total_paid=Sum('amount', filter=Q(status='approved')),
        total_pending=Sum('amount', filter=Q(status='pending')),
        total_refunded=Sum('amount', filter=Q(status='refunded')),
        count=Count('id'),
    )
    
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'payments/payment_history.html', {
        'page_obj': page_obj,
        'payments': page_obj.object_list,
        'summary': summary,
    })


@login_required
def save_payment_method(request):
    """Save a payment method for future use."""
    if request.method == 'POST':
        payment_type = request.POST.get('payment_type')
        phone_number = request.POST.get('phone_number', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        
        phone_number = re.sub(r'[^\d+]', '', phone_number)
        
        if not payment_type or not phone_number:
            messages.error(request, 'Please provide payment type and phone number.')
            return redirect('payment_methods')
        
        method, created = PaymentMethod.objects.get_or_create(
            user=request.user,
            phone_number=phone_number,
            defaults={'payment_type': payment_type, 'is_default': is_default}
        )
        
        if created:
            messages.success(request, 'Payment method saved.')
        else:
            messages.info(request, 'This payment method already exists.')
        
        return redirect('payment_methods')
    
    return redirect('payment_methods')


@login_required
def payment_methods(request):
    """Manage saved payment methods."""
    methods = PaymentMethod.objects.filter(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        method_id = request.POST.get('method_id')
        
        if action == 'set_default':
            method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
            method.is_default = True
            method.save()
            messages.success(request, 'Default payment method updated.')
        elif action == 'delete':
            method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
            method.delete()
            messages.success(request, 'Payment method removed.')
        
        return redirect('payment_methods')
    
    return render(request, 'payments/payment_methods.html', {'methods': methods})


@login_required
@require_POST
def resubmit_payment(request, payment_id):
    """Allow user to resubmit a rejected/failed payment."""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user, status__in=['rejected', 'failed'])
    
    new_payment = Payment.objects.create(
        order=payment.order,
        user=request.user,
        amount=payment.amount,
        payment_method=payment.payment_method,
        payment_type=payment.payment_type,
        customer_phone=payment.customer_phone,
        merchant_phone=payment.merchant_phone,
        merchant_name=payment.merchant_name,
        transaction_id=payment.transaction_id,
        transaction_message=payment.transaction_message,
        status='pending',
        notes=f'Resubmitted from Payment #{payment.id}',
    )
    
    messages.success(request, 'Payment resubmitted for verification.')
    return redirect('payment_status', payment_id=new_payment.id)


@login_required
@user_passes_test(lambda u: u.is_staff)
def payment_detail(request, payment_id):
    """Admin view for detailed payment information."""
    payment = get_object_or_404(
        Payment.objects.select_related('order', 'user', 'approved_by', 'rejected_by'),
        id=payment_id
    )
    
    related_payments = Payment.objects.filter(order=payment.order).exclude(id=payment.id).order_by('-created_at')
    
    return render(request, 'payments/payment_detail.html', {
        'payment': payment,
        'related_payments': related_payments,
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def expire_pending_payments(request):
    """Expire all pending payments older than 30 minutes."""
    cutoff_time = timezone.now() - timedelta(minutes=30)
    expired_payments = Payment.objects.filter(status='pending', created_at__lte=cutoff_time)
    
    expired_count = 0
    for payment in expired_payments:
        if payment.mark_as_expired():
            expired_count += 1
    
    messages.info(request, f'{expired_count} pending payment(s) expired.')
    return redirect('admin_approve_payments')


@login_required
@user_passes_test(lambda u: u.is_staff)
def payment_stats_api(request):
    """API endpoint for payment statistics."""
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)
    
    daily_stats = []
    for i in range(days):
        day = timezone.now().date() - timedelta(days=i)
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        
        stats = Payment.objects.filter(created_at__gte=day_start, created_at__lt=day_end).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected')),
            amount=Sum('amount', filter=Q(status='approved')),
        )
        
        daily_stats.append({
            'date': day.strftime('%Y-%m-%d'),
            'total': stats['total'],
            'approved': stats['approved'],
            'rejected': stats['rejected'],
            'amount': float(stats['amount'] or 0),
        })
    
    return JsonResponse({
        'daily_stats': list(reversed(daily_stats)),
        'success_rate': Payment.get_success_rate(days),
    })


def send_payment_notification(payment):
    """Send notification to admin about new payment."""
    subject = f'New Payment - Order #{payment.order.id}'
    message = f"""
    New payment requires approval:
    
    Payment ID: #{payment.id}
    Order ID: #{payment.order.id}
    Customer: {payment.user.username}
    Amount: UGX {payment.amount:,.0f}
    Method: {payment.get_payment_method_display()}
    Transaction ID: {payment.transaction_id}
    
    Approve or reject at: {settings.SITE_URL}/payments/admin/approve/
    """
    
    admin_emails = settings.ADMIN_EMAILS if hasattr(settings, 'ADMIN_EMAILS') else [admin[1] for admin in settings.ADMINS]
    
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, admin_emails, fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send payment notification: {e}")


def send_payment_confirmation(payment):
    """Send confirmation email to customer when payment is approved."""
    subject = f'Payment Confirmed - Order #{payment.order.id}'
    message = f"""
    Dear {payment.user.username},
    
    Your payment of UGX {payment.amount:,.0f} has been confirmed.
    
    Order Details:
    - Order ID: #{payment.order.id}
    - File: {payment.order.file_name}
    - Total Pages: {payment.order.page_count}
    - Status: Processing
    
    Estimated completion: {payment.order.estimated_ready_at().strftime('%I:%M %p') if payment.order.estimated_ready_at() else 'To be determined'}
    
    Track your order: {settings.SITE_URL}/track/?order_id={payment.order.id}
    
    Thank you for choosing PrintHub!
    """
    
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [payment.user.email], fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send payment confirmation: {e}")


def send_payment_rejection(payment):
    """Send rejection notification to customer."""
    subject = f'Payment Not Approved - Order #{payment.order.id}'
    message = f"""
    Dear {payment.user.username},
    
    Unfortunately, your payment of UGX {payment.amount:,.0f} for Order #{payment.order.id} could not be verified.
    
    Reason: {payment.status_reason or 'Transaction details could not be verified'}
    
    Please resubmit your payment with the correct transaction details:
    {settings.SITE_URL}/payments/resubmit/{payment.id}/
    
    If you believe this is an error, please contact support.
    
    Order ID: #{payment.order.id}
    """
    
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [payment.user.email], fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send payment rejection: {e}")
