from django.utils import timezone


def apply_order_status_change(order, new_status):
    """Update order status and set the appropriate timestamp."""
    now = timezone.now()
    order.status = new_status

    if new_status == 'paid' and not order.paid_at:
        order.paid_at = now
    elif new_status == 'printing' and not order.printing_at:
        order.printing_at = now
    elif new_status == 'ready' and not order.ready_at:
        order.ready_at = now
    elif new_status == 'collected' and not order.collected_at:
        order.collected_at = now

    order.save()
