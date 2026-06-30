from django.core.mail import send_mail
from django.conf import settings

def send_order_update_email(order, status_type):
    """Sends an email to the client when their order status changes."""
    if not order.client.email:
        return

    subjects = {
        'paid': f"Payment Confirmed - Order #{order.id}",
        'ready': f"Order Ready for Pickup - Order #{order.id}",
        'collected': f"Order Successfully Delivered - Order #{order.id}",
    }
    
    messages = {
        'paid': f"Hi {order.client.first_name or order.client.username},\n\nGreat news! Your payment for Order #{order.id} has been confirmed. We are now processing your prints.\n\nThank you,\nPrintHub Team",
        'ready': f"Hi {order.client.first_name or order.client.username},\n\nYour Order #{order.id} is now ready for pickup at the station. Please come and collect it.\n\nThank you,\nPrintHub Team",
        'collected': f"Hi {order.client.first_name or order.client.username},\n\nYour Order #{order.id} has been successfully delivered/collected. Thank you for choosing PrintHub!\n\nThank you,\nPrintHub Team",
    }

    if status_type in subjects:
        send_mail(
            subjects[status_type],
            messages[status_type],
            settings.DEFAULT_FROM_EMAIL,
            [order.client.email],
            fail_silently=True,
        )

def apply_order_status_change(order, new_status, user=None):
    """
    Updates the order status and sends email notification if needed.
    Returns True if successful, False otherwise.
    """
    old_status = order.status
    
    # Don't update if status is the same
    if old_status == new_status:
        return False
    
    # Update the status
    order.status = new_status
    order.save()
    
    # Send email notification for specific status changes
    if new_status in ['paid', 'ready', 'collected']:
        send_order_update_email(order, new_status)
    
    return True
