# whatsapp_bot/views.py - COMPLETE FINAL VERSION

import json
import re
import requests
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.contrib.auth import get_user_model

from orders.models import Order, SystemSettings, DeliveryZone, Announcement
from stations.models import Station
from payments.models import Payment
from finances.models import (
    PaperInventory, CommissionRate, AgentEarning, 
    DiscountCode, Expense, FinancialRecord
)
from notifications.models import Notification

User = get_user_model()


# ╔══════════════════════════════════════════════════════════╗
# ║          WHATSAPP CLOUD API HELPER FUNCTIONS            ║
# ╚══════════════════════════════════════════════════════════╝

def send_whatsapp_message(to_phone, message_text):
    """Send a text message via WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text[:4000]}
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code, response.json()
    except Exception as e:
        return 500, {"error": str(e)}


def send_interactive_buttons(to_phone, body_text, buttons):
    """Send a message with up to 3 quick-reply buttons."""
    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    button_list = []
    for i, btn in enumerate(buttons[:3]):
        btn_id = btn.lower().replace(" ", "_")[:20]
        button_list.append({
            "type": "reply",
            "reply": {"id": btn_id, "title": btn[:20]}
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text[:200]},
            "action": {"buttons": button_list}
        }
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code, response.json()
    except Exception as e:
        return 500, {"error": str(e)}


# ╔══════════════════════════════════════════════════════════╗
# ║                 COMMAND HANDLERS                        ║
# ╚══════════════════════════════════════════════════════════╝

def get_status_emoji(status):
    emoji_map = {
        'pending': '⏳', 'paid': '💳', 'printing': '🖨️',
        'in_transit': '🚚', 'ready': '✅', 'collected': '📦',
        'cancelled': '❌'
    }
    return emoji_map.get(status, '📋')


def get_priority_emoji(level):
    emoji_map = {
        'normal': '🟢', 'high': '🔵', 'urgent': '🟠',
        'critical': '🔴', 'overdue': '⛔', 'postponed': '🟡',
        'cancelled': '⚫'
    }
    return emoji_map.get(level, '⚪')


def get_user_by_phone(phone):
    """Find a user by their phone number."""
    # Normalize phone number
    phone = phone.replace('+', '').strip()
    if len(phone) == 9:
        phone = '256' + phone  # Assume Ugandan number
    elif len(phone) == 10 and phone.startswith('0'):
        phone = '256' + phone[1:]
    
    try:
        return User.objects.get(phone_number__contains=phone)
    except User.DoesNotExist:
        return None
    except User.MultipleObjectsReturned:
        return User.objects.filter(phone_number__contains=phone).first()


def is_admin_phone(sender):
    """Check if sender is an admin phone number."""
    for admin_num in settings.WHATSAPP_ADMIN_NUMBERS:
        if sender.replace('+', '').endswith(admin_num.replace('+', '').lstrip('0')):
            return True
    return False


def is_agent_phone(sender):
    """Check if sender is an agent phone number."""
    user = get_user_by_phone(sender)
    return user and user.role == 'agent'


# ╔══════════════════════════════════════════════════════════╗
# ║              CUSTOMER COMMANDS                          ║
# ╚══════════════════════════════════════════════════════════╝

def cmd_help(sender):
    """Show help menu."""
    msg = "📋 *PrintHub Commands*\n\n"
    msg += "*Track <order_id>* - Check order status\n"
    msg += "*Track <email>* - View your orders\n"
    msg += "*My orders* - View your orders (if phone linked)\n"
    msg += "*Place order* - Get upload link\n"
    msg += "*Pricing* - See our rates\n"
    msg += "*Stations* - View locations\n"
    msg += "*Promo* - Check offers\n"
    msg += "*Pay <order_id>* - Payment instructions\n"
    msg += "*Receipt <order_id>* - Get receipt\n\n"
    
    if is_admin_phone(sender):
        msg += "🔐 *Admin Commands:*\n"
        msg += "*Revenue today* - Daily revenue\n"
        msg += "*Active orders* - Live board\n"
        msg += "*Pending payments* - Approvals needed\n"
        msg += "*Low stock* - Paper inventory\n"
        msg += "*Top agents* - Performance\n"
        msg += "*System status* - Pause/resume info\n"
        msg += "*Pause* / *Resume* - Control system\n"
        msg += "*Add expense <amount> <category>* - Log expense\n"
        msg += "*Broadcast <message>* - Send to all users\n"
    
    if is_agent_phone(sender):
        msg += "\n🖨️ *Agent Commands:*\n"
        msg += "*My earnings* - Commission summary\n"
        msg += "*My station* - Station details\n"
        msg += "*Ready to collect* - Orders at my station\n"
        msg += "*Update #123 to ready* - Quick status change\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_welcome(sender):
    """Send welcome message with current stats."""
    active_count = Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']).count()
    ready_count = Order.objects.filter(status='ready').count()
    
    announcement = Announcement.get_active()
    announcement_text = ""
    if announcement:
        announcement_text = f"\n📢 {announcement.message}\n"
    
    msg = f"*Welcome to PrintHub!* 🖨️{announcement_text}"
    msg += f"\n📊 Active: *{active_count}* orders"
    if ready_count > 0:
        msg += f" | ✅ Ready: *{ready_count}*"
    msg += "\n\nWhat would you like to do?"
    
    return send_interactive_buttons(sender, msg, ["Track Order", "Place Order", "Help"])


def cmd_track(sender, query):
    """Track order by ID or email."""
    query = query.strip()
    
    # Track by order ID
    if query.isdigit():
        order_id = int(query)
        try:
            order = Order.objects.select_related('station', 'client', 'delivery_zone').get(id=order_id)
            return send_order_details(sender, order)
        except Order.DoesNotExist:
            return send_whatsapp_message(sender, f"❌ Order *#{order_id}* not found.")
    
    # Track by email
    elif '@' in query:
        orders = Order.objects.filter(
            client__email__iexact=query
        ).select_related('station').order_by('-created_at')[:5]
        
        if not orders.exists():
            return send_whatsapp_message(sender, f"📭 No orders found for *{query}*.")
        
        reply = f"📚 Orders for *{query}*:\n\n"
        for i, order in enumerate(orders, 1):
            status_emoji = get_status_emoji(order.status)
            reply += f"{i}. #{order.id} - {status_emoji} {order.get_status_display()}\n"
            reply += f"   📄 {order.file_name[:30]}...\n"
            reply += f"   💰 {order.total_price:,.0f} UGX\n\n"
        
        reply += "_Reply with *Track <order_id>* for details._"
        return send_whatsapp_message(sender, reply)
    
    return send_whatsapp_message(sender, "❌ Please provide order ID (e.g., *Track 123*) or email (e.g., *Track student@email.com*).")


def cmd_my_orders(sender):
    """Show orders linked to the sender's phone number."""
    user = get_user_by_phone(sender)
    if not user:
        return send_whatsapp_message(sender, "❌ No account linked to this phone number.\n\nSend your email: *Track your@email.com*")
    
    orders = Order.objects.filter(client=user).select_related('station').order_by('-created_at')[:10]
    
    if not orders.exists():
        return send_whatsapp_message(sender, "📭 You have no orders yet.\n\nSend *Place order* to get started!")
    
    msg = f"📚 *{user.first_name or user.username}'s Orders*\n\n"
    for order in orders:
        status_emoji = get_status_emoji(order.status)
        priority = order.priority_info
        msg += f"#{order.id} - {status_emoji} {order.get_status_display()}"
        if priority['is_overdue']:
            msg += " ⛔"
        msg += f"\n   📄 {order.file_name[:25]}... | 💰 {order.total_price:,.0f} UGX\n"
        if order.station:
            msg += f"   📍 {order.station.name}\n"
        msg += "\n"
    
    msg += "_Reply with *Track <order_id>* for full details._"
    return send_whatsapp_message(sender, msg)


def send_order_details(sender, order):
    """Send detailed order information."""
    priority = order.priority_info
    status_emoji = get_status_emoji(order.status)
    priority_emoji = get_priority_emoji(priority['level'])
    
    msg = f"📋 *Order #{order.id}*\n\n"
    msg += f"📄 *File:* {order.file_name}\n"
    msg += f"📄 *Pages:* {order.page_count}"
    if order.is_color: msg += " 🎨 Color"
    if order.is_double_sided: msg += " | Double-sided"
    msg += "\n"
    
    msg += f"📊 *Status:* {status_emoji} {order.get_status_display()}\n"
    msg += f"⚡ *Priority:* {priority_emoji} {priority['display']}\n"
    
    if order.status not in ['pending', 'collected', 'cancelled']:
        msg += f"⏱ *Time Left:* {priority['time_display']}\n"
    
    if order.station:
        msg += f"📍 *Station:* {order.station.name}\n"
    
    if order.binding != 'none':
        msg += f"📚 *Binding:* {order.get_binding_display()}\n"
    
    if order.delivery_type == 'delivery':
        msg += "🚚 *Delivery:* Yes"
        if order.delivery_zone:
            msg += f" ({order.delivery_zone.name})"
        msg += "\n"
    else:
        msg += "🏢 *Pickup:* At station\n"
    
    msg += f"💰 *Total:* {order.total_price:,.0f} UGX\n"
    
    # Payment status
    payment = Payment.objects.filter(order=order).first()
    if payment:
        msg += f"💳 *Payment:* {payment.get_status_display()}\n"
        if payment.status == 'approved':
            msg += f"   Transaction: {payment.transaction_id}\n"
    elif order.status == 'pending':
        msg += f"⚠️ *Payment not yet made!*\n"
        msg += f"   Send *Pay {order.id}* for instructions.\n"
    
    # Timeline
    msg += "\n*Timeline:*\n"
    if order.created_at:
        msg += f"• Submitted: {order.created_at.strftime('%d %b, %I:%M %p')}\n"
    if order.paid_at:
        msg += f"• Paid: {order.paid_at.strftime('%d %b, %I:%M %p')}\n"
    if order.printing_at:
        msg += f"• Printing: {order.printing_at.strftime('%d %b, %I:%M %p')}\n"
    if order.ready_at:
        msg += f"• Ready: {order.ready_at.strftime('%d %b, %I:%M %p')}\n"
    if order.collected_at:
        msg += f"• Collected: {order.collected_at.strftime('%d %b, %I:%M %p')}\n"
    if order.cancelled_at:
        msg += f"• Cancelled: {order.cancelled_at.strftime('%d %b, %I:%M %p')}\n"
    
    msg += f"\n🔗 *Track online:* https://printlink.pythonanywhere.com/track/?order_id={order.id}"
    
    return send_whatsapp_message(sender, msg)


def cmd_place_order(sender):
    """Guide user to place a new order."""
    stations = Station.objects.filter(is_active=True)
    
    msg = "📤 *Place a New Order*\n\n"
    msg += "1. Go to: https://printlink.pythonanywhere.com/upload/\n"
    msg += "2. Upload your file (PDF, Word, PPT, images)\n"
    msg += "3. Choose options (color, binding, delivery)\n"
    msg += "4. Pay with MTN/Airtel Mobile Money\n"
    msg += "5. Pick up or get it delivered!\n\n"
    
    if stations.exists():
        msg += "📍 *Available Stations:*\n"
        for s in stations[:5]:
            msg += f"• {s.name}\n"
        msg += "\n"
    
    # Check for active discounts
    active_discounts = DiscountCode.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_until__gte=timezone.now()
    )
    if active_discounts.exists():
        msg += "🎫 *Active Promo Codes:*\n"
        for d in active_discounts[:3]:
            msg += f"• {d.code} - {d.description}\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_pricing(sender):
    """Show current pricing."""
    msg = "💰 *PrintHub Pricing*\n\n"
    msg += "• B&W: *200 UGX*/page\n"
    msg += "• Color: *300 UGX*/page\n"
    msg += "• Double-sided: Same price per side\n"
    msg += "• Spiral Binding: *1,000 UGX*\n"
    msg += "• Delivery: From *2,000 UGX*\n\n"
    msg += "💡 *Bulk orders (50+ pages):* Contact for quote\n"
    msg += f"📞 WhatsApp: {settings.WHATSAPP_BUSINESS_PHONE}\n"
    
    # Active discounts
    active_discounts = DiscountCode.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_until__gte=timezone.now()
    )
    if active_discounts.exists():
        msg += "\n🎫 *Active Promos:*\n"
        for d in active_discounts:
            remaining = d.max_uses - d.used_count if d.max_uses > 0 else "∞"
            msg += f"• *{d.code}*: {d.description}\n"
            msg += f"   ({remaining} uses left)\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_pay(sender, order_id):
    """Send payment instructions for an order."""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    
    if order.status != 'pending':
        return send_whatsapp_message(sender, f"⚠️ Order #{order.id} is already *{order.get_status_display()}*. Payment not needed.")
    
    from finances.models import MerchantSettings
    mtn = MerchantSettings.get_merchant('mtn')
    airtel = MerchantSettings.get_merchant('airtel')
    
    msg = f"💳 *Pay for Order #{order.id}*\n\n"
    msg += f"💰 Amount: *{order.total_price:,.0f} UGX*\n\n"
    
    if mtn:
        msg += f"📱 *MTN Mobile Money:*\n"
        msg += f"   Send to: *{mtn.merchant_phone}*\n"
        msg += f"   Name: *{mtn.merchant_name}*\n\n"
    
    if airtel:
        msg += f"📱 *Airtel Money:*\n"
        msg += f"   Send to: *{airtel.merchant_phone}*\n"
        msg += f"   Name: *{airtel.merchant_name}*\n\n"
    
    msg += "⚠️ *After payment:*\n"
    msg += f"Reply with your transaction ID\n"
    msg += f"Example: *Paid {order.id} TXN123456*\n\n"
    msg += "Or upload screenshot at:\n"
    msg += f"https://printlink.pythonanywhere.com/orders/{order.id}/pay/"
    
    return send_whatsapp_message(sender, msg)


def cmd_paid(sender, order_id, txn_id):
    """Record payment confirmation from customer."""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    
    if order.status != 'pending':
        return send_whatsapp_message(sender, f"⚠️ Order #{order.id} is already *{order.get_status_display()}*.")
    
    # Create pending payment record
    user = get_user_by_phone(sender)
    if not user:
        return send_whatsapp_message(sender, "❌ No account linked to your number. Please use email tracking.")
    
    payment = Payment.objects.create(
        order=order,
        user=user,
        amount=order.total_price,
        payment_method='mtn',  # Default, can be improved
        customer_phone=sender,
        transaction_id=txn_id,
        status='pending'
    )
    
    msg = f"✅ *Payment Recorded!*\n\n"
    msg += f"Order: *#{order.id}*\n"
    msg += f"Transaction: *{txn_id}*\n"
    msg += f"Status: *Pending Approval*\n\n"
    msg += "An admin will verify your payment shortly.\n"
    msg += f"You'll be notified when it's approved."
    
    # Notify admins
    for admin_num in settings.WHATSAPP_ADMIN_NUMBERS:
        send_whatsapp_message(admin_num, f"🔔 *New Payment*\n\nOrder: #{order.id}\nAmount: {order.total_price:,.0f} UGX\nTXN: {txn_id}\n\nReply *Approve {payment.id}* or *Reject {payment.id}*")
    
    return send_whatsapp_message(sender, msg)


def cmd_promo(sender):
    """Show active promotions."""
    msg = "🎉 *Current Promotions*\n\n"
    
    active_discounts = DiscountCode.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_until__gte=timezone.now()
    )
    
    if active_discounts.exists():
        for discount in active_discounts:
            remaining = discount.max_uses - discount.used_count if discount.max_uses > 0 else "∞"
            msg += f"🎫 *{discount.code}*\n"
            msg += f"   {discount.description}\n"
            msg += f"   {remaining} uses remaining\n"
            if discount.minimum_order > 0:
                msg += f"   Min order: {discount.minimum_order:,.0f} UGX\n"
            msg += f"   Valid until: {discount.valid_until.strftime('%d %b %Y')}\n\n"
    else:
        msg += "No active promotions at the moment.\n"
        msg += "Check back soon!\n\n"
    
    announcement = Announcement.get_active()
    if announcement:
        msg += f"📢 *Announcement:*\n{announcement.message}\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_stations(sender):
    """Show available stations."""
    stations = Station.objects.filter(is_active=True)
    
    if not stations.exists():
        return send_whatsapp_message(sender, "📍 No stations currently available.")
    
    msg = "📍 *PrintHub Stations*\n\n"
    for station in stations:
        msg += f"*{station.name}*\n"
        if hasattr(station, 'location') and station.location:
            msg += f"   📍 {station.location}\n"
        
        # Active agents at station
        agents = User.objects.filter(role='agent', station=station)
        if agents.exists():
            agent_names = ", ".join([a.first_name or a.username for a in agents[:3]])
            msg += f"   👤 Agent(s): {agent_names}\n"
        msg += "\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_receipt(sender, order_id):
    """Send receipt link for an order."""
    try:
        order = Order.objects.select_related('client').get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    
    msg = f"🧾 *Receipt - Order #{order.id}*\n\n"
    msg += f"📄 {order.file_name}\n"
    msg += f"📄 {order.page_count} pages\n"
    msg += f"💰 Total: {order.total_price:,.0f} UGX\n"
    msg += f"📊 Status: {order.get_status_display()}\n\n"
    msg += f"🔗 View full receipt:\n"
    msg += f"https://printlink.pythonanywhere.com/orders/{order.id}/receipt/"
    
    return send_whatsapp_message(sender, msg)


# ╔══════════════════════════════════════════════════════════╗
# ║                ADMIN COMMANDS                           ║
# ╚══════════════════════════════════════════════════════════╝

def cmd_admin_revenue(sender):
    """Show revenue summary."""
    today = timezone.now().date()
    
    # Today's revenue
    today_orders = Order.objects.filter(created_at__date=today)
    today_revenue = today_orders.aggregate(
        total=Sum('total_price'),
        profit=Sum('profit'),
        count=Count('id')
    )
    
    # This week
    week_start = timezone.now() - timedelta(days=7)
    week_orders = Order.objects.filter(created_at__gte=week_start)
    week_revenue = week_orders.aggregate(
        total=Sum('total_price'),
        profit=Sum('profit'),
        count=Count('id')
    )
    
    # Payments today
    today_payments = Payment.objects.filter(created_at__date=today)
    payment_summary = today_payments.aggregate(
        approved=Sum('amount', filter=Q(status='approved')),
        pending=Sum('amount', filter=Q(status='pending')),
        count=Count('id')
    )
    
    msg = f"📊 *Revenue Report*\n\n"
    msg += f"*Today:*\n"
    msg += f"• Revenue: {today_revenue['total'] or 0:,.0f} UGX\n"
    msg += f"• Profit: {today_revenue['profit'] or 0:,.0f} UGX\n"
    msg += f"• Orders: {today_revenue['count'] or 0}\n\n"
    
    msg += f"*This Week:*\n"
    msg += f"• Revenue: {week_revenue['total'] or 0:,.0f} UGX\n"
    msg += f"• Orders: {week_revenue['count'] or 0}\n\n"
    
    msg += f"*Payments Today:*\n"
    msg += f"• Approved: {payment_summary['approved'] or 0:,.0f} UGX\n"
    msg += f"• Pending: {payment_summary['pending'] or 0:,.0f} UGX\n"
    msg += f"• Total Transactions: {payment_summary['count'] or 0}\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_admin_active_orders(sender):
    """Show active orders (live board)."""
    active = Order.objects.filter(
        status__in=['paid', 'printing', 'in_transit', 'ready']
    ).select_related('station', 'client').order_by('-created_at')
    
    if not active.exists():
        return send_whatsapp_message(sender, "✅ No active orders.")
    
    msg = f"🖨️ *Active Orders ({active.count()})*\n\n"
    for order in active[:15]:
        priority = order.priority_info
        msg += f"#{order.id} - {get_status_emoji(order.status)} {order.get_status_display()}"
        if priority['is_overdue']:
            msg += " ⛔ OVERDUE"
        msg += f"\n   📄 {order.file_name[:20]}... | ⏱ {priority['time_display']}"
        if order.station:
            msg += f" | 📍 {order.station.name}"
        msg += "\n\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_admin_pending_payments(sender):
    """Show pending payment approvals."""
    pending = Payment.objects.filter(status='pending').select_related('order', 'user').order_by('-created_at')[:10]
    
    if not pending.exists():
        return send_whatsapp_message(sender, "✅ No pending payments.")
    
    msg = f"💳 *Pending Approvals ({pending.count()})*\n\n"
    for p in pending:
        msg += f"Payment #{p.id}\n"
        msg += f"   Order: #{p.order.id}\n"
        msg += f"   Amount: {p.amount:,.0f} UGX\n"
        msg += f"   Method: {p.get_payment_method_display()}\n"
        msg += f"   TXN: {p.transaction_id}\n"
        msg += f"   Customer: {p.user.username}\n\n"
        msg += f"   Reply: *Approve {p.id}* or *Reject {p.id}*\n\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_admin_approve_payment(sender, payment_id):
    """Approve a payment."""
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Payment #{payment_id} not found.")
    
    user = get_user_by_phone(sender)
    if payment.approve(approved_by=user):
        # Notify customer
        if payment.user.phone_number:
            send_whatsapp_message(
                payment.user.phone_number,
                f"✅ Your payment of {payment.amount:,.0f} UGX for Order #{payment.order.id} has been *APPROVED*!\n\n"
                f"Your order is now being processed. Track it: *Track {payment.order.id}*"
            )
        return send_whatsapp_message(sender, f"✅ Payment #{payment.id} approved! Customer notified.")
    return send_whatsapp_message(sender, f"❌ Failed to approve payment #{payment.id}.")


def cmd_admin_reject_payment(sender, payment_id):
    """Reject a payment."""
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Payment #{payment_id} not found.")
    
    # Extract reason if provided (after "reject 123 reason text")
    reason = "Payment verification failed"
    
    user = get_user_by_phone(sender)
    if payment.reject(rejected_by=user, reason=reason):
        if payment.user.phone_number:
            send_whatsapp_message(
                payment.user.phone_number,
                f"❌ Your payment of {payment.amount:,.0f} UGX for Order #{payment.order.id} was *NOT APPROVED*.\n"
                f"Reason: {reason}\n\n"
                f"Please try again or contact support."
            )
        return send_whatsapp_message(sender, f"❌ Payment #{payment.id} rejected. Customer notified.")
    return send_whatsapp_message(sender, f"❌ Failed to reject payment #{payment.id}.")


def cmd_admin_low_stock(sender):
    """Check paper inventory for low stock."""
    low_stock = PaperInventory.objects.filter(
        quantity__lte=models.F('low_stock_threshold'),
        is_active=True
    )
    
    if not low_stock.exists():
        return send_whatsapp_message(sender, "✅ All paper stocks are sufficient.")
    
    msg = "⚠️ *Low Stock Alert!*\n\n"
    for item in low_stock:
        status = item.stock_status
        if status == 'out_of_stock':
            msg += f"🔴 *{item.get_paper_type_display()}*\n"
            msg += f"   OUT OF STOCK!\n\n"
        else:
            msg += f"🟠 *{item.get_paper_type_display()}*\n"
            msg += f"   Remaining: {item.quantity} sheets\n"
            msg += f"   Threshold: {item.low_stock_threshold}\n"
            msg += f"   Last restocked: {item.last_restocked_at.strftime('%d %b %Y') if item.last_restocked_at else 'Never'}\n\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_admin_system_status(sender):
    """Show system pause/resume status."""
    settings_obj = SystemSettings.load()
    
    msg = "⚙️ *System Status*\n\n"
    msg += f"Status: {'⏸️ PAUSED' if settings_obj.is_paused else '▶️ RUNNING'}\n"
    
    if settings_obj.is_paused:
        msg += f"Reason: {settings_obj.pause_reason}\n"
        if settings_obj.pause_started_at:
            duration = timezone.now() - settings_obj.pause_started_at
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            msg += f"Paused for: {hours}h {minutes}m\n"
    
    msg += f"Total paused time: {settings_obj.total_paused_seconds / 3600:.1f} hours\n\n"
    
    # Active orders affected
    active = Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']).count()
    overdue = sum(1 for o in Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']) if o.is_overdue)
    msg += f"Active orders: {active}\n"
    msg += f"Overdue orders: {overdue}\n\n"
    
    if settings_obj.is_paused:
        msg += "Send *Resume* to restart the system."
    else:
        msg += "Send *Pause <reason>* to pause the system."
    
    return send_whatsapp_message(sender, msg)


def cmd_admin_pause(sender, reason=""):
    """Pause the system."""
    settings_obj = SystemSettings.load()
    
    if settings_obj.is_paused:
        return send_whatsapp_message(sender, "⚠️ System is already paused.")
    
    settings_obj.is_paused = True
    settings_obj.pause_reason = reason or "Paused by admin via WhatsApp"
    settings_obj.pause_started_at = timezone.now()
    settings_obj.save()
    
    return send_whatsapp_message(sender, f"⏸️ System PAUSED.\nReason: {settings_obj.pause_reason}")


def cmd_admin_resume(sender):
    """Resume the system."""
    settings_obj = SystemSettings.load()
    
    if not settings_obj.is_paused:
        return send_whatsapp_message(sender, "⚠️ System is already running.")
    
    if settings_obj.pause_started_at:
        settings_obj.total_paused_seconds += (timezone.now() - settings_obj.pause_started_at).total_seconds()
    settings_obj.is_paused = False
    settings_obj.pause_started_at = None
    settings_obj.save()
    
    return send_whatsapp_message(sender, "▶️ System RESUMED. Timers are now running.")


def cmd_admin_top_agents(sender):
    """Show top performing agents."""
    top = AgentEarning.get_top_agents(limit=5)
    
    if not top:
        return send_whatsapp_message(sender, "No agent data available.")
    
    msg = "🏆 *Top Agents*\n\n"
    for i, agent in enumerate(top, 1):
        medal = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][i-1]
        name = agent.get('agent__first_name') or agent.get('agent__username', 'Unknown')
        msg += f"{medal} *{name}*\n"
        msg += f"   Earnings: {agent['total_earnings']:,.0f} UGX\n"
        msg += f"   Orders: {agent['orders_count']}\n"
        msg += f"   Average: {agent['avg_commission']:,.0f} UGX/order\n\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_admin_add_expense(sender, amount, category='other'):
    """Quick expense logging."""
    try:
        amount = float(amount)
        if amount <= 0:
            return send_whatsapp_message(sender, "❌ Amount must be positive.")
        
        user = get_user_by_phone(sender)
        expense = Expense.objects.create(
            category=category if category in dict(Expense.EXPENSE_CATEGORIES) else 'other',
            amount=Decimal(str(amount)),
            description=f"Added via WhatsApp by {user.username if user else 'admin'}",
            created_by=user
        )
        
        return send_whatsapp_message(
            sender,
            f"✅ Expense recorded!\n\n"
            f"ID: #{expense.id}\n"
            f"Amount: {amount:,.0f} UGX\n"
            f"Category: {expense.get_category_display()}"
        )
    except ValueError:
        return send_whatsapp_message(sender, "❌ Invalid amount. Example: *Add expense 50000 paper*")


def cmd_admin_broadcast(sender, message):
    """Broadcast message to all users with phone numbers (USE WITH CAUTION)."""
    users = User.objects.filter(phone_number__isnull=False).exclude(phone_number='')
    
    sent_count = 0
    for user in users[:50]:  # Limit to 50 to prevent abuse
        try:
            send_whatsapp_message(user.phone_number, f"📢 *PrintHub Announcement*\n\n{message}")
            sent_count += 1
        except Exception:
            pass
    
    return send_whatsapp_message(sender, f"📢 Broadcast sent to {sent_count} users.")


# ╔══════════════════════════════════════════════════════════╗
# ║                AGENT COMMANDS                           ║
# ╚══════════════════════════════════════════════════════════╝

def cmd_agent_earnings(sender):
    """Show agent's earnings."""
    user = get_user_by_phone(sender)
    if not user or user.role != 'agent':
        return send_whatsapp_message(sender, "❌ Agent account not found.")
    
    summary = AgentEarning.get_agent_summary(user)
    
    msg = f"💰 *Your Earnings*\n\n"
    msg += f"Total Earned: {summary['total_earned'] or 0:,.0f} UGX\n"
    msg += f"Total Paid: {summary['total_paid'] or 0:,.0f} UGX\n"
    msg += f"Pending: {summary['total_pending'] or 0:,.0f} UGX\n"
    msg += f"Total Orders: {summary['orders_count'] or 0}\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_agent_station(sender):
    """Show agent's station details."""
    user = get_user_by_phone(sender)
    if not user or user.role != 'agent':
        return send_whatsapp_message(sender, "❌ Agent account not found.")
    
    if not user.station:
        return send_whatsapp_message(sender, "⚠️ You are not assigned to any station.")
    
    station = user.station
    
    # Orders at this station
    station_orders = Order.objects.filter(
        station=station,
        status__in=['paid', 'printing', 'in_transit', 'ready']
    )
    ready_orders = station_orders.filter(status='ready')
    
    msg = f"📍 *Your Station: {station.name}*\n\n"
    if hasattr(station, 'location'):
        msg += f"Location: {station.location}\n"
    msg += f"Active Orders: {station_orders.count()}\n"
    msg += f"Ready for Pickup: {ready_orders.count()}\n\n"
    
    if ready_orders.exists():
        msg += "*Ready Orders:*\n"
        for order in ready_orders[:5]:
            msg += f"• #{order.id} - {order.file_name[:20]}...\n"
            msg += f"  Client: {order.client.username}\n"
    
    return send_whatsapp_message(sender, msg)


def cmd_agent_update_status(sender, order_id, new_status):
    """Agent updates order status."""
    user = get_user_by_phone(sender)
    if not user or user.role != 'agent':
        return send_whatsapp_message(sender, "❌ Agent access required.")
    
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    
    if order.station != user.station:
        return send_whatsapp_message(sender, "❌ This order is not at your station.")
    
    valid_statuses = ['printing', 'in_transit', 'ready', 'collected']
    if new_status not in valid_statuses:
        return send_whatsapp_message(sender, f"❌ Invalid status. Use: {', '.join(valid_statuses)}")
    
    from orders.utils import apply_order_status_change
    if apply_order_status_change(order, new_status, user):
        return send_whatsapp_message(sender, f"✅ Order #{order.id} updated to *{order.get_status_display()}*")
    return send_whatsapp_message(sender, f"❌ Failed to update Order #{order.id}")


# ╔══════════════════════════════════════════════════════════╗
# ║              MAIN MESSAGE ROUTER                        ║
# ╚══════════════════════════════════════════════════════════╝

def handle_incoming_message(sender, message_text):
    """Route incoming message to appropriate handler."""
    text = message_text.strip()
    text_lower = text.lower()
    
    # Parse commands with arguments
    parts = text.split()
    command = parts[0].lower() if parts else ""
    
    # ═══════════════════════════════════════════════
    # Universal commands
    # ═══════════════════════════════════════════════
    
    if command in ['hi', 'hello', 'hey', 'start', 'menu']:
        return cmd_welcome(sender)
    
    if command in ['help', 'commands']:
        return cmd_help(sender)
    
    if command in ['track', 'status'] and len(parts) >= 2:
        return cmd_track(sender, ' '.join(parts[1:]))
    
    if text_lower in ['my orders', 'myorders', 'orders']:
        return cmd_my_orders(sender)
    
    if text_lower in ['place order', 'place_order', 'new order', 'upload', 'print']:
        return cmd_place_order(sender)
    
    if text_lower in ['pricing', 'price', 'prices', 'cost', 'rates']:
        return cmd_pricing(sender)
    
    if text_lower in ['stations', 'location', 'locations', 'where']:
        return cmd_stations(sender)
    
    if text_lower in ['promo', 'promos', 'promotion', 'discount', 'offer', 'offers', 'hec10']:
        return cmd_promo(sender)
    
    if command in ['pay', 'payment'] and len(parts) >= 2 and parts[1].isdigit():
        return cmd_pay(sender, parts[1])
    
    if command in ['paid', 'paidfor'] and len(parts) >= 3:
        return cmd_paid(sender, parts[1], ' '.join(parts[2:]))
    
    if command in ['receipt', 'invoice'] and len(parts) >= 2 and parts[1].isdigit():
        return cmd_receipt(sender, parts[1])
    
    # Track by email (if contains @)
    if '@' in text_lower:
        return cmd_track(sender, text_lower)
    
    # Track by number (if all digits)
    if text.isdigit():
        return cmd_track(sender, text)
    
    # ═══════════════════════════════════════════════
    # Admin commands
    # ═══════════════════════════════════════════════
    
    if is_admin_phone(sender):
        if text_lower in ['revenue', 'revenue today', 'sales', 'sales today']:
            return cmd_admin_revenue(sender)
        
        if text_lower in ['active', 'active orders', 'live', 'board']:
            return cmd_admin_active_orders(sender)
        
        if text_lower in ['pending payments', 'pending', 'approvals']:
            return cmd_admin_pending_payments(sender)
        
        if command == 'approve' and len(parts) >= 2 and parts[1].isdigit():
            return cmd_admin_approve_payment(sender, parts[1])
        
        if command == 'reject' and len(parts) >= 2 and parts[1].isdigit():
            return cmd_admin_reject_payment(sender, parts[1])
        
        if text_lower in ['low stock', 'lowstock', 'stock', 'paper']:
            return cmd_admin_low_stock(sender)
        
        if text_lower in ['system', 'system status', 'status check']:
            return cmd_admin_system_status(sender)
        
        if command == 'pause':
            reason = ' '.join(parts[1:]) if len(parts) > 1 else ''
            return cmd_admin_pause(sender, reason)
        
        if command == 'resume':
            return cmd_admin_resume(sender)
        
        if text_lower in ['top agents', 'topagents', 'agents']:
            return cmd_admin_top_agents(sender)
        
        if command in ['add', 'expense'] and len(parts) >= 3:
            try:
                amount = parts[2] if parts[1] == 'expense' else parts[1]
                category = parts[3] if len(parts) >= 4 else 'other'
                return cmd_admin_add_expense(sender, amount, category)
            except ValueError:
                return send_whatsapp_message(sender, "❌ Format: *Add expense <amount> <category>*")
        
        if command == 'broadcast' and len(parts) >= 2:
            return cmd_admin_broadcast(sender, ' '.join(parts[1:]))
    
    # ═══════════════════════════════════════════════
    # Agent commands
    # ═══════════════════════════════════════════════
    
    if is_agent_phone(sender):
        if text_lower in ['my earnings', 'myearnings', 'earnings']:
            return cmd_agent_earnings(sender)
        
        if text_lower in ['my station', 'mystation', 'station']:
            return cmd_agent_station(sender)
        
        if text_lower in ['ready to collect', 'ready orders', 'tocollect']:
            user = get_user_by_phone(sender)
            if user and user.station:
                ready = Order.objects.filter(station=user.station, status='ready')
                msg = f"✅ *Ready Orders ({ready.count()})*\n\n"
                for o in ready[:10]:
                    msg += f"#{o.id} - {o.file_name[:20]}... | {o.client.username}\n"
                return send_whatsapp_message(sender, msg)
        
        if command == 'update' and len(parts) >= 4:
            if parts[1].startswith('#') or parts[1].isdigit():
                order_id = parts[1].replace('#', '')
                if order_id.isdigit() and parts[2] == 'to':
                    return cmd_agent_update_status(sender, order_id, parts[3])
    
    # ═══════════════════════════════════════════════
    # Fallback
    # ═══════════════════════════════════════════════
    
    return send_whatsapp_message(
        sender,
        "I didn't understand that.\n\n"
        "Here's what I can do:\n"
        "📋 *Track <order_id>* - Check order\n"
        "📋 *Track <email>* - Your orders\n"
        "🛒 *Place order* - Upload link\n"
        "💰 *Pricing* - See rates\n"
        "📍 *Stations* - Locations\n"
        "🎫 *Promo* - Discounts\n\n"
        "Type *Help* for full menu."
    )


# ╔══════════════════════════════════════════════════════════╗
# ║              WEBHOOK ENDPOINT                           ║
# ╚══════════════════════════════════════════════════════════╝

@csrf_exempt
def webhook_view(request):
    """WhatsApp Cloud API webhook."""
    
    # GET: Webhook verification
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)
    
    # POST: Incoming messages
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        try:
            entries = body.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    
                    for msg in value.get("messages", []):
                        sender = msg.get("from", "")
                        msg_type = msg.get("type", "")
                        
                        if msg_type == "text":
                            text = msg.get("text", {}).get("body", "")
                            if sender and text:
                                handle_incoming_message(sender, text)
                        
                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            if interactive.get("type") == "button_reply":
                                button_id = interactive.get("button_reply", {}).get("id", "")
                                if sender and button_id:
                                    handle_incoming_message(sender, button_id)
                        
                        elif msg_type in ["image", "document"]:
                            if sender:
                                send_whatsapp_message(
                                    sender,
                                    "📎 I received your file. To print, upload at:\n"
                                    "https://printlink.pythonanywhere.com/upload/\n\n"
                                    "Pay with MTN/Airtel. Reply *Pricing* for rates."
                                )
        
        except Exception as e:
            print(f"WhatsApp webhook error: {e}")
        
        return JsonResponse({"status": "ok"})
    
    return HttpResponse("Method not allowed", status=405)


def health_check(request):
    """Health check endpoint."""
    return JsonResponse({
        "status": "healthy",
        "service": "PrintHub WhatsApp Bot",
        "version": "2.0.0",
        "features": [
            "order_tracking", "payment_processing", "admin_controls",
            "agent_management", "inventory_alerts", "broadcast_messaging"
        ],
        "timestamp": timezone.now().isoformat()
    })
