# orders/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal

from .models import Order


@receiver(post_save, sender=Order)
def handle_order_status_change(sender, instance, created, **kwargs):
    """
    Handle side effects when order status changes:
    - Set timestamps for status changes
    - Deduct paper inventory when printing
    - Create financial records when collected
    - Create notifications for status changes
    """
    
    if created:
        return
    
    old_status = getattr(instance, '_old_status', None)
    
    if old_status == instance.status:
        return
    
    now = timezone.now()
    
    if instance.status == 'paid' and not instance.paid_at:
        instance.paid_at = now
        instance.save(update_fields=['paid_at'])
    
    elif instance.status == 'printing':
        if not instance.printing_at:
            instance.printing_at = now
            instance.save(update_fields=['printing_at'])
        instance.deduct_paper_inventory()
    
    elif instance.status == 'in_transit' and not instance.in_transit_at:
        instance.in_transit_at = now
        instance.save(update_fields=['in_transit_at'])
    
    elif instance.status == 'ready' and not instance.ready_at:
        instance.ready_at = now
        instance.save(update_fields=['ready_at'])
        create_order_notification(instance, 'ready')
    
    elif instance.status == 'collected':
        if not instance.collected_at:
            instance.collected_at = now
        # FIX: Calculate financials BEFORE creating records
        instance.calculate_financials()
        instance.save(update_fields=['paper_used', 'cost_of_goods', 'agent_commission', 'profit', 'collected_at'])
        create_financial_records(instance)
    
    elif instance.status == 'cancelled':
        create_order_notification(instance, 'cancelled')


def create_order_notification(order, status_type):
    """Create notification for order status changes."""
    try:
        from notifications.models import Notification
        
        notifications_map = {
            'paid': {
                'title': 'Payment Confirmed',
                'message': f'Payment received for Order #{order.id}. Your order is being processed.',
            },
            'printing': {
                'title': 'Printing Started',
                'message': f'Order #{order.id} ({order.file_name}) is now printing.',
            },
            'in_transit': {
                'title': 'Order In Transit',
                'message': f'Order #{order.id} is on its way to {order.station.name if order.station else "the station"}.',
            },
            'ready': {
                'title': 'Order Ready for Pickup',
                'message': f'Order #{order.id} ({order.file_name}) is ready at {order.station.name if order.station else "the station"}.',
            },
            'cancelled': {
                'title': 'Order Cancelled',
                'message': f'Order #{order.id} has been cancelled. {order.cancellation_reason or ""}',
            },
        }
        
        info = notifications_map.get(status_type)
        if info:
            Notification.create_notification(
                user=order.client,
                notification_type='order_status',
                title=info['title'],
                message=info['message'],
                link=f'/orders/{order.id}/receipt/'
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Notification failed for Order #{order.id}: {e}")


def create_financial_records(order):
    """Create FinancialRecord and AgentEarning entries for completed order."""
    try:
        from finances.models import FinancialRecord, AgentEarning, CommissionRate
        from django.contrib.auth import get_user_model
        
        if FinancialRecord.objects.filter(order=order, transaction_type='income').exists():
            return
        
        # Income record
        FinancialRecord.objects.create(
            transaction_type='income',
            amount=order.total_price,
            description=f'Order #{order.id} - {order.file_name}',
            order=order
        )
        
        # Find agent for this station
        User = get_user_model()
        agent = None
        if order.station:
            agent = User.objects.filter(role='agent', station=order.station).first()
        
        # Commission record
        if order.agent_commission > 0 and agent:
            FinancialRecord.objects.create(
                transaction_type='commission',
                amount=order.agent_commission,
                description=f'Commission for Order #{order.id}',
                order=order,
                agent=agent
            )
            
            rate = CommissionRate.get_active_rate()
            AgentEarning.objects.get_or_create(
                order=order,
                agent=agent,
                defaults={
                    'commission_rate': rate.rate_percentage if rate else Decimal('0.00'),
                    'commission_amount': order.agent_commission,
                    'order_total': order.total_price,
                }
            )
            
            # Notify agent
            from notifications.models import Notification
            Notification.create_notification(
                user=agent,
                notification_type='commission_paid',
                title='Commission Earned',
                message=f'You earned {order.agent_commission} UGX from Order #{order.id}.',
                link=f'/finances/agent-earnings/'
            )
                
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Financial records failed for Order #{order.id}: {e}")
