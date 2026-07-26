# orders/views/agent_views.py
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from django.http import HttpResponseForbidden
from django.contrib.auth import get_user_model

from orders.models import Order
from orders.utils import apply_order_status_change, send_delayed_order_email
from .helpers import _user_role, _is_staff_role, is_agent_or_admin

User = get_user_model()
logger = logging.getLogger(__name__)

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
        except Exception as e:
            logger.error(f"Error fetching agent earnings: {e}")
            
    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        if not order_id or not order_id.isdigit():
            messages.error(request, 'Invalid order ID.')
            return redirect('agent_dashboard')
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=int(order_id))
                if action == 'update_status':
                    new_status = request.POST.get('status')
                    valid_statuses = dict(Order.STATUS_CHOICES).keys()
                    if new_status not in valid_statuses:
                        messages.error(request, 'Invalid status.')
                        return redirect('agent_dashboard')
                    if request.user.role == 'agent' and order.station != request.user.station:
                        messages.error(request, 'You can only update orders for your station.')
                        return redirect('agent_dashboard')
                    if apply_order_status_change(order, new_status, request.user):
                        messages.success(request, f'Order #{order.id} updated to {order.get_status_display()}.')
                    else:
                        messages.info(request, f'Order #{order.id} status unchanged.')
                elif action == 'notify_delay':
                    reason = strip_tags(request.POST.get('delay_reason', '').strip())
                    if not reason:
                        messages.error(request, 'Please provide a delay reason.')
                        return redirect('agent_dashboard')
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
                    if order.status not in ['collected', 'cancelled']:
                        reason = strip_tags(request.POST.get('cancellation_reason', '').strip())
                        order.status = 'cancelled'
                        order.cancellation_reason = reason[:500]
                        order.cancelled_at = timezone.now()
                        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])
                        messages.success(request, f'Order #{order.id} has been CANCELLED.')
                    else:
                        messages.error(request, 'Cannot cancel this order.')
                elif action == 'postpone_order':
                    if order.status not in ['collected', 'cancelled']:
                        try:
                            extra_minutes = int(request.POST.get('extra_minutes', 30))
                            if 0 < extra_minutes <= 1440:
                                order.postponed_minutes += extra_minutes
                                order.save(update_fields=['postponed_minutes'])
                                messages.success(request, f'Order #{order.id} postponed by {extra_minutes} minutes.')
                            else:
                                messages.error(request, 'Please enter a valid number of minutes (1-1440).')
                        except ValueError:
                            messages.error(request, 'Invalid number of minutes.')
                    else:
                        messages.error(request, 'Cannot postpone this order.')
                elif action == 'add_note':
                    note = strip_tags(request.POST.get('note', '').strip())
                    if note:
                        existing_notes = order.notes or ''
                        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                        order.notes = f"{existing_notes}\n[{timestamp}] {request.user.username}: {note}".strip()
                        order.save(update_fields=['notes'])
                        messages.success(request, f'Note added to Order #{order.id}.')
                    else:
                        messages.error(request, 'Note cannot be empty.')
        except Order.DoesNotExist:
            messages.error(request, 'Order not found.')
        except Exception as e:
            logger.error(f"Error in agent dashboard action: {e}", exc_info=True)
            messages.error(request, 'An error occurred. Please try again.')
        return redirect('agent_dashboard')
        
    return render(request, 'orders/agent_dashboard.html', {
        'orders': orders,
        'agent_earnings': agent_earnings,
    })

@login_required
@transaction.atomic
def update_order_status_view(request, order_id):
    if not _is_staff_role(request.user):
        return HttpResponseForbidden('You do not have permission to update order status.')
    if not str(order_id).isdigit():
        return HttpResponseForbidden('Invalid order ID.')
    try:
        order = Order.objects.select_for_update().get(id=int(order_id))
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('dashboard')
    if _user_role(request.user) == 'agent':
        if not request.user.station or order.station_id != request.user.station_id:
            return HttpResponseForbidden('You can only update orders for your assigned station.')
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = dict(Order.STATUS_CHOICES).keys()
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
