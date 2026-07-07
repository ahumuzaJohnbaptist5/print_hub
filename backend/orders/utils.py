from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()
def send_welcome_email(user):
    """Send welcome email when user registers."""
    if not user.email:
        print(f"⚠️ User {user.username} has no email!")
        return
    
    print(f"📧 Sending welcome email to {user.email}...")
    
    subject = 'Welcome to PrintHub! 🎉'
    message = f"""Hi {user.first_name or user.username},

Welcome to PrintHub! We're excited to have you on board.

Here's how to get started:
1. Log in to your account
2. Upload your document
3. Choose your printing options (color, double-sided, etc.)
4. Make payment via MTN or Airtel Mobile Money
5. Track your order status in real-time

If you have any questions, just reply to this email.

Happy printing!
The PrintHub Team
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    
    print(f"✅ Welcome email sent!")

def send_payment_confirmed_email(order):
    """Send email when payment is approved."""
    if not order.client.email:
        print(f"⚠️ Order #{order.id} client has no email!")
        return
    
    print(f"📧 Sending payment confirmed email to {order.client.email}...")
    
    subject = f'Payment Confirmed - Order #{order.id} ✅'
    message = f"""Hi {order.client.first_name or order.client.username},

Great news! Your payment of UGX {order.total_price} for Order #{order.id} has been confirmed.

Order Details:
- File: {order.file_name}
- Pages: {order.page_count}
- Type: {'Color' if order.is_color else 'Black & White'}
- Double-sided: {'Yes' if order.is_double_sided else 'No'}

We're now processing your prints. You'll receive another email when your order is ready for pickup.

Thank you for choosing PrintHub!
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.client.email],
        fail_silently=False,
    )
    
    print(f"✅ Payment confirmed email sent!")

def send_order_started_email(order):
    """Send email when agent starts printing."""
    if not order.client.email:
        print(f"⚠️ Order #{order.id} client has no email!")
        return
    
    print(f"📧 Sending printing started email to {order.client.email}...")
    
    subject = f'Printing Started - Order #{order.id} 🖨️'
    message = f"""Hi {order.client.first_name or order.client.username},

Good news! We've started printing your Order #{order.id}.

Your document is now being processed at our station. We'll notify you as soon as it's ready for pickup or out for delivery.

Thank you for your patience!
The PrintHub Team
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.client.email],
        fail_silently=False,
    )
    
    print(f"✅ Printing started email sent!")

def send_order_ready_email(order):
    """Send email when order is ready for pickup."""
    if not order.client.email:
        print(f"⚠️ Order #{order.id} client has no email!")
        return
    
    station_name = order.station.name if order.station else 'our station'
    
    print(f"📧 Sending ready for pickup email to {order.client.email}...")
    
    subject = f'Order Ready for Pickup - Order #{order.id} 📦'
    message = f"""Hi {order.client.first_name or order.client.username},

Your Order #{order.id} is now ready for pickup!

Pickup Details:
- Order ID: #{order.id}
- Location: {station_name}
- Status: Ready for Pickup

Please come and collect your prints at your convenience. Don't forget to bring your order ID.

Thank you for choosing PrintHub!
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.client.email],
        fail_silently=False,
    )
    
    print(f"✅ Ready for pickup email sent!")

def send_order_collected_email(order):
    """Send email when order is collected/delivered."""
    if not order.client.email:
        print(f"⚠️ Order #{order.id} client has no email!")
        return
    
    print(f"📧 Sending collected email to {order.client.email}...")
    
    subject = f'Order Successfully Delivered - Order #{order.id} ✅'
    message = f"""Hi {order.client.first_name or order.client.username},

Your Order #{order.id} has been successfully collected.

Thank you for choosing PrintHub! We hope you're satisfied with our service.

We'd love to hear your feedback. If you have any questions or concerns, please don't hesitate to contact us.

Looking forward to serving you again!
The PrintHub Team
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.client.email],
        fail_silently=False,
    )
    
    print(f"✅ Collected email sent!")

def send_delayed_order_email(order, reason=''):
    """Send email when order is delayed."""
    if not order.client.email:
        print(f"⚠️ Order #{order.id} client has no email!")
        return
    
    print(f"📧 Sending delay notification to {order.client.email}...")
    
    subject = f'Update on Your Order #{order.id} ⏰'
    
    if reason:
        reason_text = f"\nReason: {reason}\n"
    else:
        reason_text = "\nWe're experiencing a slight delay in processing your order.\n"
    
    message = f"""Hi {order.client.first_name or order.client.username},

We wanted to give you an update on your Order #{order.id}.
{reason_text}
We apologize for any inconvenience and appreciate your patience. Your order is still being processed and we're working to complete it as soon as possible.

If you have any questions, please reply to this email.

Thank you for your understanding!
The PrintHub Team
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.client.email],
        fail_silently=False,
    )
    
    print(f"✅ Delay notification sent!")


# ==========================================
# --- UPDATED STATUS CHANGE FUNCTION ---
# ==========================================
def apply_order_status_change(order, new_status, user=None):
    """
    Updates the order status, sends email notification, and creates agent earnings.
    """
    old_status = order.status
    
    if old_status == new_status:
        return False
    
    order.status = new_status
    order.save() # This triggers calculate_financials() in the Order model
    
    # --- AUTOMATIC AGENT EARNING ---
    if new_status == 'collected' and order.station:
        from finances.models import AgentEarning
        
        # Find the agent assigned to this specific station
        agent = User.objects.filter(role='agent', station=order.station).first()
        
        # If an agent is found and we haven't paid them for this order yet
        if agent and not AgentEarning.objects.filter(order=order).exists():
            
            # Calculate the percentage safely
            rate = 0
            if order.total_price > 0:
                rate = float(order.agent_commission) / float(order.total_price) * 100
                
            AgentEarning.objects.create(
                agent=agent,
                order=order,
                commission_rate=round(rate, 2),
                commission_amount=order.agent_commission,
                order_total=order.total_price
            )

    # --- EMAIL TRIGGERS ---
    try:
        if new_status == 'paid':
            send_payment_confirmed_email(order)
        elif new_status == 'ready':
            send_order_ready_email(order)
        elif new_status == 'collected':
            send_order_collected_email(order)
    except Exception as e:
        print(f"Email notification failed for Order #{order.id}: {e}")
    
    return True
