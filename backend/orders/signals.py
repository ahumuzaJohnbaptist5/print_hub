# orders/signals.py
from django.db.models.signals import post_save, pre_save
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
    """
    
    # Skip if this is a new order (handled in save method)
    if created:
        return
    
    # Get old status (stored in save method)
    old_status = getattr(instance, '_old_status', None)
    
    if old_status == instance.status:
        return  # Status didn't change
    
    now = timezone.now()
    
    # Set timestamps based on status
    if instance.status == 'paid' and not instance.paid_at:
        instance.paid_at = now
        instance.save(update_fields=['paid_at'])
    
    elif instance.status == 'printing':
        if not instance.printing_at:
            instance.printing_at = now
            instance.save(update_fields=['printing_at'])
        # Deduct paper from inventory when printing starts
        instance.deduct_paper_inventory()
    
    elif instance.status == 'in_transit' and not instance.in_transit_at:
        instance.in_transit_at = now
        instance.save(update_fields=['in_transit_at'])
    
    elif instance.status == 'ready' and not instance.ready_at:
        instance.ready_at = now
        instance.save(update_fields=['ready_at'])
    
    elif instance.status == 'collected':
        if not instance.collected_at:
            instance.collected_at = now
            instance.save(update_fields=['collected_at'])
        
        # Create financial records only once
        create_financial_records(instance)


def create_financial_records(order):
    """Create FinancialRecord and AgentEarning entries for completed order."""
    try:
        from finances.models import FinancialRecord, AgentEarning, CommissionRate
        
        # Check if records already exist
        if FinancialRecord.objects.filter(order=order, transaction_type='income').exists():
            return  # Already processed
        
        # 1. Income record
        FinancialRecord.objects.create(
            transaction_type='income',
            amount=order.total_price,
            description=f'Order #{order.id} - {order.file_name}',
            order=order
        )
        
        # 2. Commission record (if agent commission exists)
        if order.agent_commission > 0:
            FinancialRecord.objects.create(
                transaction_type='commission',
                amount=order.agent_commission,
                description=f'Commission for Order #{order.id}',
                order=order,
                agent=order.station.agent if order.station and hasattr(order.station, 'agent') else None
            )
            
            # 3. Create AgentEarning
            rate = CommissionRate.get_active_rate()
            if order.station and hasattr(order.station, 'agent') and order.station.agent:
                AgentEarning.objects.get_or_create(
                    order=order,
                    agent=order.station.agent,
                    defaults={
                        'commission_rate': rate.rate_percentage if rate else Decimal('0.00'),
                        'commission_amount': order.agent_commission,
                        'order_total': order.total_price,
                    }
                )
                
    except Exception as e:
        # Log the error but don't break the save
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create financial records for Order #{order.id}: {e}")
