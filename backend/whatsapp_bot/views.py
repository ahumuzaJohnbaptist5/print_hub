import json
import re
import requests
import os
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from orders.models import Order, SystemSettings, DeliveryZone, Announcement
from stations.models import Station
from payments.models import Payment
from finances.models import (
    PaperInventory, CommissionRate, AgentEarning,
    DiscountCode, Expense, FinancialRecord, MerchantSettings
)
from notifications.models import Notification

User = get_user_model()

# ══════════════════════════════════════════════════════════════
# WHATSAPP CLOUD API HELPERS
# ══════════════════════════════════════════════════════════════

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


def download_media(media_id):
    """Download media file from WhatsApp."""
    # Get media URL
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        media_info = response.json()
        media_url = media_info.get("url", "")

        # Download the actual file
        if media_url:
            file_response = requests.get(media_url, headers=headers)
            return file_response.content, media_info.get("mime_type", "")
    except Exception:
        pass
    return None, None


# ══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════

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
    phone = phone.replace('+', '').strip()
    if len(phone) == 9:
        phone = '256' + phone
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


def is_group_chat(sender):
    """Check if sender ID is a group chat."""
    return '@g.us' in sender or '@broadcast' in sender


def get_group_id(sender):
    """Extract group ID from sender."""
    return sender.split('@')[0] if '@' in sender else sender


def is_command(text):
    """Check if a message is a bot command."""
    text_lower = text.lower().strip()
    commands = [
        'hi', 'hello', 'hey', 'start', 'menu', 'help', 'commands',
        'track', 'status', 'my orders', 'myorders', 'orders',
        'place order', 'place_order', 'new order', 'upload', 'print',
        'pricing', 'price', 'prices', 'cost', 'rates',
        'stations', 'location', 'locations', 'where',
        'promo', 'promos', 'discount', 'offer', 'offers', 'hec10',
        'pay', 'payment', 'paid', 'paidfor', 'receipt', 'invoice',
        'order ', 'revenue', 'active', 'pending',
        'approve', 'reject', 'low stock', 'system', 'status',
        'pause', 'resume', 'top agents', 'agents',
        'add', 'expense', 'broadcast',
        'my earnings', 'earnings', 'my station', 'mystation',
        'ready to collect', 'ready orders', 'update',
    ]
    return any(text_lower.startswith(cmd) for cmd in commands)


def alert_admin(message):
    """Send alert to all admin numbers."""
    for admin_num in settings.WHATSAPP_ADMIN_NUMBERS:
        send_whatsapp_message(admin_num, message)


# ══════════════════════════════════════════════════════════════
# ORDER DRAFT SYSTEM
# ══════════════════════════════════════════════════════════════

# Store draft orders in memory (reset on server restart)
# In production, use a Django model or cache
DRAFT_ORDERS = {}


def cmd_order(sender, *args):
    """Create an order via WhatsApp chat.

    Examples:
        Order 45 pages Color Spiral Pickup
        Order 20 B&W Staple Delivery
        Order 100 pages
    """
    text = ' '.join(args)

    # Parse order details
    page_count = None
    is_color = False
    is_double_sided = False
    binding = 'none'
    delivery_type = 'pickup'
    discount_code = None

    for i, arg in enumerate(args):
        arg_lower = arg.lower()

        # Page count
        if arg.isdigit():
            page_count = int(arg)

        # Color/B&W
        elif arg_lower in ['color', 'colored', 'colour']:
            is_color = True
        elif arg_lower in ['b&w', 'bw', 'black', 'mono']:
            is_color = False

        # Double-sided
        elif arg_lower in ['double', 'double-sided', 'duplex']:
            is_double_sided = True
        elif arg_lower in ['single', 'single-sided', 'simplex']:
            is_double_sided = False

        # Binding
        elif arg_lower in ['spiral', 'spiral_binding']:
            binding = 'spiral'
        elif arg_lower in ['staple', 'stapled']:
            binding = 'staple'
        elif arg_lower in ['none', 'nobinding', 'no_binding']:
            binding = 'none'

        # Delivery/Pickup
        elif arg_lower in ['delivery', 'deliver']:
            delivery_type = 'delivery'
        elif arg_lower in ['pickup', 'pick', 'collect']:
            delivery_type = 'pickup'

        # Discount code
        elif arg_lower.upper() in ['HEC10', 'PRINT5', 'NEWUSER']:
            discount_code = arg_lower.upper()

    if not page_count or page_count < 1:
        return send_whatsapp_message(sender,
            "📝 *Create an Order*\n\n"
            "Send: *Order <pages> <color/b&w> <binding> <pickup/delivery>*\n\n"
            "Examples:\n"
            "• *Order 45 Color Spiral Pickup*\n"
            "• *Order 20 B&W Staple Delivery*\n"
            "• *Order 100 pages Double-sided*\n\n"
            "You can also add a promo code:\n"
            "• *Order 50 Color Spiral Pickup HEC10*"
        )

    # Calculate price
    delivery_fee = 0  # Will be set when station/zone is chosen
    total, effective_pages, price_per_page = Order.compute_price(
        page_count, is_color, is_double_sided, binding, delivery_fee
    )

    # Apply discount if valid
    discount_amount = Decimal('0.00')
    if discount_code:
        try:
            discount = DiscountCode.objects.get(code=discount_code, is_active=True)
            if discount.is_valid and total >= discount.minimum_order:
                if discount.discount_type == 'percentage':
                    discount_amount = (Decimal(str(total)) * discount.discount_value) / Decimal('100.00')
                else:
                    discount_amount = discount.discount_value
                total -= float(discount_amount)
        except DiscountCode.DoesNotExist:
            pass

    # Store as draft
    draft_id = str(int(timezone.now().timestamp()))
    DRAFT_ORDERS[draft_id] = {
        'sender': sender,
        'page_count': page_count,
        'is_color': is_color,
        'is_double_sided': is_double_sided,
        'binding': binding,
        'delivery_type': delivery_type,
        'discount_code': discount_code,
        'discount_amount': float(discount_amount),
        'total': total,
        'effective_pages': effective_pages,
        'station_id': None,
        'file': None,
        'file_name': None,
        'created_at': timezone.now(),
    }

    # Build confirmation message
    msg = f"📋 *Order Summary*\n\n"
    msg += f"📄 Pages: *{page_count}*"
    if is_double_sided:
        msg += f" ({effective_pages} sheets)"
    msg += "\n"
    msg += f"🎨 Type: *{'Color' if is_color else 'B&W'}*\n"
    msg += f"📚 Binding: *{Order(dict(binding=binding)).get_binding_display()}*\n"
    msg += f"📍 Method: *{'Delivery 🚚' if delivery_type == 'delivery' else 'Pickup 🏢'}*\n"
    msg += f"💰 Price per page: *{price_per_page} UGX*\n"

    if discount_amount > 0:
        msg += f"🎫 Discount ({discount_code}): *-{discount_amount:,.0f} UGX*\n"

    msg += f"💵 *Total: {total:,.0f} UGX*\n\n"

    # Show stations
    stations = Station.objects.filter(is_active=True)
    if stations.exists() and delivery_type == 'pickup':
        msg += "*Pick a station:*\n"
        for i, s in enumerate(stations[:5], 1):
            msg += f"{i}. {s.name}\n"
        msg += "\nReply with the station number or name.\n"

    msg += "📎 *Next:* Send your file (PDF, DOCX, image)\n"
    msg += "Or type *Confirm* to place the order now.\n"
    msg += "Type *Cancel* to discard this order."

    return send_whatsapp_message(sender, msg)


def confirm_draft_order(sender):
    """Confirm and create a draft order."""
    # Find the user's draft
    draft = None
    draft_id = None
    for did, d in DRAFT_ORDERS.items():
        if d['sender'] == sender:
            draft = d
            draft_id = did
            break

    if not draft:
        return send_whatsapp_message(sender, "❌ No pending order. Send *Order <pages>* to start.")

    # Get or create user
    user = get_user_by_phone(sender)
    if not user:
        # Create a temporary note
        user_note = f"WhatsApp customer: {sender}"
        # We need a user to create an order
        return send_whatsapp_message(sender,
            "⚠️ *Account Required*\n\n"
            "Create a free account to place orders:\n"
            "https://printlink.pythonanywhere.com/register/\n\n"
            "It takes 30 seconds! After registering, come back and type *Confirm*."
        )

    # Create the order
    try:
        order = Order.objects.create(
            client=user,
            station_id=draft.get('station_id'),
            file=draft.get('file'),
            file_name=draft.get('file_name', f"WhatsApp Order - {draft['page_count']} pages"),
            page_count=draft['page_count'],
            is_color=draft['is_color'],
            is_double_sided=draft.get('is_double_sided', False),
            binding=draft['binding'],
            delivery_type=draft['delivery_type'],
            status='pending',
            notes=f"Ordered via WhatsApp\nPages: {draft['page_count']}\n"
                  f"Color: {'Yes' if draft['is_color'] else 'No'}\n"
                  f"Binding: {draft['binding']}\n"
        )

        # Clean up draft
        del DRAFT_ORDERS[draft_id]

        msg = f"✅ *Order #{order.id} Created!*\n\n"
        msg += f"📄 {order.file_name}\n"
        msg += f"📄 {order.page_count} pages"
        if order.is_color: msg += " 🎨 Color"
        if order.is_double_sided: msg += " | Double-sided"
        msg += "\n"
        if order.binding != 'none':
            msg += f"📚 {order.get_binding_display()}\n"
        msg += f"💰 Total: *{order.total_price:,.0f} UGX*\n\n"

        if not draft.get('file'):
            msg += "⚠️ *File needed!* Send your document here or upload at:\n"
            msg += "https://printlink.pythonanywhere.com/upload/\n\n"

        msg += f"💳 To pay, send: *Pay {order.id}*\n"
        msg += f"📋 Track: *Track {order.id}*"

        # Notify admins
        alert_admin(f"🆕 *New WhatsApp Order!*\nOrder: #{order.id}\nUser: {user.username}\n"
                    f"Pages: {order.page_count}\nTotal: {order.total_price:,.0f} UGX")

        return send_whatsapp_message(sender, msg)

    except Exception as e:
        return send_whatsapp_message(sender, f"❌ Error creating order: {str(e)}")


def handle_file_upload(sender, media_id, media_type, file_name=None):
    """Save uploaded file to draft order."""
    # Find user's draft
    draft = None
    draft_id = None
    for did, d in DRAFT_ORDERS.items():
        if d['sender'] == sender:
            draft = d
            draft_id = did
            break

    if not draft:
        return send_whatsapp_message(sender,
            "📎 I received your file! But you haven't started an order yet.\n\n"
            "Send *Order <pages> <options>* first.\n"
            "Example: *Order 45 Color Spiral Pickup*\n\n"
            "Or upload directly at:\n"
            "https://printlink.pythonanywhere.com/upload/"
        )

    # Download the file
    file_content, mime_type = download_media(media_id)
    if not file_content:
        return send_whatsapp_message(sender, "❌ Failed to download file. Please try again or upload at the website.")

    # Determine file extension
    ext_map = {
        'application/pdf': '.pdf',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
    }
    ext = ext_map.get(mime_type, '.pdf')

    # Save to draft
    safe_filename = file_name or f"whatsapp_upload_{int(timezone.now().timestamp())}{ext}"
    draft['file_name'] = safe_filename
    draft['file'] = ContentFile(file_content, safe_filename)

    msg = f"✅ *File Received!*\n\n"
    msg += f"📄 {safe_filename}\n"
    msg += f"📦 Size: {len(file_content) // 1024} KB\n\n"
    msg += "Your order is ready. Type *Confirm* to place it.\n"
    msg += "Or type *Cancel* to start over."

    return send_whatsapp_message(sender, msg)


def cancel_draft(sender):
    """Cancel a draft order."""
    for did, d in list(DRAFT_ORDERS.items()):
        if d['sender'] == sender:
            del DRAFT_ORDERS[did]
            return send_whatsapp_message(sender, "❌ Order cancelled. Send *Order <pages>* to start a new one.")
    return send_whatsapp_message(sender, "No pending order to cancel.")


def handle_station_selection(sender, choice):
    """Handle station selection for draft order."""
    draft = None
    for d in DRAFT_ORDERS.values():
        if d['sender'] == sender:
            draft = d
            break

    if not draft:
        return None  # Not a station selection

    stations = Station.objects.filter(is_active=True)

    # Try by number
    station = None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < stations.count():
            station = stations[idx]
    else:
        # Try by name
        station = stations.filter(name__icontains=choice).first()

    if station:
        draft['station_id'] = station.id
        msg = f"✅ Station: *{station.name}*\n\n"
        msg += "📎 Now send your file or type *Confirm* to place your order."
        return send_whatsapp_message(sender, msg)

    return None


# ══════════════════════════════════════════════════════════════
# CUSTOMER COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════

def cmd_help(sender):
    msg = "📋 *PrintHub Commands*\n\n"
    msg += "*Order <pages> <color/b&w> <binding> <pickup/delivery>* - Create order\n"
    msg += "*Track <order_id>* - Check order status\n"
    msg += "*Track <email>* - View your orders\n"
    msg += "*My orders* - Your orders (if phone linked)\n"
    msg += "*Place order* - Get upload link\n"
    msg += "*Pricing* - See our rates\n"
    msg += "*Stations* - View locations\n"
    msg += "*Promo* - Check offers\n"
    msg += "*Pay <order_id>* - Payment instructions\n"
    msg += "*Receipt <order_id>* - Get receipt\n"

    if is_admin_phone(sender):
        msg += "\n🔐 *Admin:* Revenue, Active, Pending, Low stock, System, Pause, Resume, Top agents, Add expense, Broadcast\n"
        msg += "*Advert <message>* - Send advert to groups\n"
        msg += "*Advert schedule* - Show scheduled adverts\n"
    if is_agent_phone(sender):
        msg += "\n🖨️ *Agent:* My earnings, My station, Ready to collect, Update #id to status\n"

    return send_whatsapp_message(sender, msg)


def cmd_welcome(sender):
    active_count = Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']).count()
    ready_count = Order.objects.filter(status='ready').count()
    announcement = Announcement.get_active()
    announcement_text = f"\n📢 {announcement.message}\n" if announcement else ""

    msg = f"*Welcome to PrintHub!* 🖨️{announcement_text}"
    msg += f"\n📊 Active: *{active_count}* orders"
    if ready_count > 0:
        msg += f" | ✅ Ready: *{ready_count}*"
    msg += "\n\nWhat would you like to do?"
    return send_interactive_buttons(sender, msg, ["Order Now", "Track Order", "Help"])


def cmd_track(sender, query):
    query = query.strip()
    if query.isdigit():
        try:
            order = Order.objects.select_related('station', 'client', 'delivery_zone').get(id=int(query))
            return send_order_details(sender, order)
        except Order.DoesNotExist:
            return send_whatsapp_message(sender, f"❌ Order *#{query}* not found.")
    elif '@' in query:
        orders = Order.objects.filter(client__email__iexact=query).select_related('station').order_by('-created_at')[:5]
        if not orders.exists():
            return send_whatsapp_message(sender, f"📭 No orders for *{query}*.")
        reply = f"📚 Orders for *{query}*:\n\n"
        for i, order in enumerate(orders, 1):
            emoji = get_status_emoji(order.status)
            reply += f"{i}. #{order.id} - {emoji} {order.get_status_display()}\n"
            reply += f"   📄 {order.file_name[:30]}... | 💰 {order.total_price:,.0f} UGX\n\n"
        reply += "_Reply *Track <id>* for details._"
        return send_whatsapp_message(sender, reply)
    return send_whatsapp_message(sender, "❌ Use *Track 123* or *Track email@example.com*")


def cmd_my_orders(sender):
    user = get_user_by_phone(sender)
    if not user:
        return send_whatsapp_message(sender, "❌ No account linked. Send *Track your@email.com* instead.")
    orders = Order.objects.filter(client=user).select_related('station').order_by('-created_at')[:10]
    if not orders.exists():
        return send_whatsapp_message(sender, "📭 No orders yet. Send *Order <pages>* to start!")
    msg = f"📚 *{user.first_name or user.username}'s Orders*\n\n"
    for order in orders:
        emoji = get_status_emoji(order.status)
        priority = order.priority_info
        msg += f"#{order.id} - {emoji} {order.get_status_display()}"
        if priority['is_overdue']: msg += " ⛔"
        msg += f"\n   📄 {order.file_name[:25]}... | 💰 {order.total_price:,.0f} UGX\n"
        if order.station: msg += f"   📍 {order.station.name}\n"
        msg += "\n"
    return send_whatsapp_message(sender, msg)


def send_order_details(sender, order):
    priority = order.priority_info
    status_emoji = get_status_emoji(order.status)
    msg = f"📋 *Order #{order.id}*\n\n"
    msg += f"📄 *File:* {order.file_name}\n"
    msg += f"📄 *Pages:* {order.page_count}"
    if order.is_color: msg += " 🎨 Color"
    if order.is_double_sided: msg += " | Double-sided"
    msg += "\n"
    msg += f"📊 *Status:* {status_emoji} {order.get_status_display()}\n"
    msg += f"⚡ *Priority:* {priority['display']}\n"
    if order.status not in ['pending', 'collected', 'cancelled']:
        msg += f"⏱ *Time Left:* {priority['time_display']}\n"
    if order.station: msg += f"📍 *Station:* {order.station.name}\n"
    if order.binding != 'none': msg += f"📚 *Binding:* {order.get_binding_display()}\n"
    if order.delivery_type == 'delivery':
        msg += "🚚 *Delivery:* Yes"
        if order.delivery_zone: msg += f" ({order.delivery_zone.name})"
        msg += "\n"
    else:
        msg += "🏢 *Pickup:* At station\n"
    msg += f"💰 *Total:* {order.total_price:,.0f} UGX\n"
    payment = Payment.objects.filter(order=order).first()
    if payment:
        msg += f"💳 *Payment:* {payment.get_status_display()}\n"
    elif order.status == 'pending':
        msg += f"⚠️ *Payment pending!* Send *Pay {order.id}*\n"
    msg += "\n*Timeline:*\n"
    if order.created_at: msg += f"• Submitted: {order.created_at.strftime('%d %b, %I:%M %p')}\n"
    if order.paid_at: msg += f"• Paid: {order.paid_at.strftime('%d %b, %I:%M %p')}\n"
    if order.printing_at: msg += f"• Printing: {order.printing_at.strftime('%d %b, %I:%M %p')}\n"
    if order.ready_at: msg += f"• Ready: {order.ready_at.strftime('%d %b, %I:%M %p')}\n"
    if order.collected_at: msg += f"• Collected: {order.collected_at.strftime('%d %b, %I:%M %p')}\n"
    msg += f"\n🔗 https://printlink.pythonanywhere.com/track/?order_id={order.id}"
    return send_whatsapp_message(sender, msg)


def cmd_place_order(sender):
    stations = Station.objects.filter(is_active=True)
    msg = "📤 *Place a New Order*\n\n"
    msg += "🚀 *Quick way:* Send *Order <pages> <options>*\n"
    msg += "Example: *Order 45 Color Spiral Pickup*\n\n"
    msg += "📎 Or upload at:\n"
    msg += "https://printlink.pythonanywhere.com/upload/\n\n"
    if stations.exists():
        msg += "📍 *Stations:*\n"
        for s in stations[:5]:
            msg += f"• {s.name}\n"
    return send_whatsapp_message(sender, msg)


def cmd_pricing(sender):
    msg = "💰 *PrintHub Pricing*\n\n"
    msg += "• B&W: *200 UGX*/page\n"
    msg += "• Color: *300 UGX*/page\n"
    msg += "• Spiral Binding: *1,000 UGX*\n"
    msg += "• Delivery: From *2,000 UGX*\n"
    active = DiscountCode.objects.filter(is_active=True, valid_from__lte=timezone.now(), valid_until__gte=timezone.now())
    if active.exists():
        msg += "\n🎫 *Active Promos:*\n"
        for d in active:
            msg += f"• *{d.code}* - {d.description}\n"
    return send_whatsapp_message(sender, msg)


def cmd_pay(sender, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    if order.status != 'pending':
        return send_whatsapp_message(sender, f"⚠️ Order is already *{order.get_status_display()}*.")
    mtn = MerchantSettings.get_merchant('mtn')
    airtel = MerchantSettings.get_merchant('airtel')
    msg = f"💳 *Pay for Order #{order.id}*\n\n"
    msg += f"💰 Amount: *{order.total_price:,.0f} UGX*\n\n"
    if mtn:
        msg += f"📱 *MTN:* {mtn.merchant_phone} ({mtn.merchant_name})\n\n"
    if airtel:
        msg += f"📱 *Airtel:* {airtel.merchant_phone} ({airtel.merchant_name})\n\n"
    msg += f"After payment: *Paid {order.id} TXN_ID*"
    return send_whatsapp_message(sender, msg)


def cmd_paid(sender, order_id, txn_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    user = get_user_by_phone(sender)
    if not user:
        return send_whatsapp_message(sender, "❌ No account linked.")
    payment = Payment.objects.create(order=order, user=user, amount=order.total_price,
        payment_method='mtn', customer_phone=sender, transaction_id=txn_id, status='pending')
    alert_admin(f"🔔 *New Payment*\nOrder: #{order.id}\nAmount: {order.total_price:,.0f} UGX\nTXN: {txn_id}\n\n*Approve {payment.id}* or *Reject {payment.id}*")
    return send_whatsapp_message(sender, f"✅ *Recorded!*\nOrder: #{order.id}\nTXN: {txn_id}\nStatus: Pending Approval")


def cmd_promo(sender):
    msg = "🎉 *Promotions*\n\n"
    discounts = DiscountCode.objects.filter(is_active=True, valid_from__lte=timezone.now(), valid_until__gte=timezone.now())
    if discounts.exists():
        for d in discounts:
            remaining = d.max_uses - d.used_count if d.max_uses > 0 else "∞"
            msg += f"🎫 *{d.code}* - {d.description}\n   {remaining} uses. Valid until {d.valid_until.strftime('%d %b')}\n\n"
    else:
        msg += "No active promotions.\n"
    return send_whatsapp_message(sender, msg)


def cmd_stations(sender):
    stations = Station.objects.filter(is_active=True)
    if not stations.exists():
        return send_whatsapp_message(sender, "📍 No stations available.")
    msg = "📍 *PrintHub Stations*\n\n"
    for s in stations:
        msg += f"*{s.name}*\n"
        if hasattr(s, 'location') and s.location: msg += f"   📍 {s.location}\n"
        msg += "\n"
    return send_whatsapp_message(sender, msg)


def cmd_receipt(sender, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    msg = f"🧾 *Receipt - Order #{order.id}*\n\n"
    msg += f"📄 {order.file_name}\n"
    msg += f"💰 Total: {order.total_price:,.0f} UGX\n"
    msg += f"📊 Status: {order.get_status_display()}\n\n"
    msg += f"🔗 https://printlink.pythonanywhere.com/orders/{order.id}/receipt/"
    return send_whatsapp_message(sender, msg)


# ══════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════

def cmd_admin_revenue(sender):
    today = timezone.now().date()
    today_rev = Order.objects.filter(created_at__date=today).aggregate(total=Sum('total_price'), profit=Sum('profit'), count=Count('id'))
    week_rev = Order.objects.filter(created_at__gte=timezone.now()-timedelta(days=7)).aggregate(total=Sum('total_price'), count=Count('id'))
    pay = Payment.objects.filter(created_at__date=today).aggregate(approved=Sum('amount', filter=Q(status='approved')), pending=Sum('amount', filter=Q(status='pending')))
    msg = f"📊 *Revenue*\n\n*Today:* {today_rev['total'] or 0:,.0f} UGX | {today_rev['count'] or 0} orders\n"
    msg += f"*Week:* {week_rev['total'] or 0:,.0f} UGX | {week_rev['count'] or 0} orders\n"
    msg += f"*Payments:* Approved: {pay['approved'] or 0:,.0f} | Pending: {pay['pending'] or 0:,.0f}"
    return send_whatsapp_message(sender, msg)


def cmd_admin_active_orders(sender):
    active = Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']).select_related('station')[:15]
    if not active.exists():
        return send_whatsapp_message(sender, "✅ No active orders.")
    msg = f"🖨️ *Active ({active.count()})*\n\n"
    for o in active:
        p = o.priority_info
        msg += f"#{o.id} - {get_status_emoji(o.status)} {o.get_status_display()}"
        if p['is_overdue']: msg += " ⛔"
        msg += f" | ⏱ {p['time_display']}"
        if o.station: msg += f" | 📍 {o.station.name}"
        msg += "\n"
    return send_whatsapp_message(sender, msg)


def cmd_admin_pending_payments(sender):
    pending = Payment.objects.filter(status='pending').select_related('order', 'user')[:10]
    if not pending.exists():
        return send_whatsapp_message(sender, "✅ No pending payments.")
    msg = f"💳 *Pending ({pending.count()})*\n\n"
    for p in pending:
        msg += f"#{p.id} | Order #{p.order.id} | {p.amount:,.0f} UGX | TXN: {p.transaction_id}\n*Approve {p.id}* or *Reject {p.id}*\n\n"
    return send_whatsapp_message(sender, msg)


def cmd_admin_approve(sender, payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Payment #{payment_id} not found.")
    user = get_user_by_phone(sender)
    if payment.approve(approved_by=user):
        if payment.user.phone_number:
            send_whatsapp_message(payment.user.phone_number, f"✅ Payment {payment.amount:,.0f} UGX for Order #{payment.order.id} *APPROVED*!")
        return send_whatsapp_message(sender, f"✅ Payment #{payment.id} approved!")
    return send_whatsapp_message(sender, "❌ Failed.")


def cmd_admin_reject(sender, payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Payment #{payment_id} not found.")
    user = get_user_by_phone(sender)
    if payment.reject(rejected_by=user, reason="Verification failed"):
        return send_whatsapp_message(sender, f"❌ Payment #{payment.id} rejected.")
    return send_whatsapp_message(sender, "❌ Failed.")


def cmd_admin_low_stock(sender):
    low = PaperInventory.objects.filter(quantity__lte=F('low_stock_threshold'), is_active=True)
    if not low.exists():
        return send_whatsapp_message(sender, "✅ All paper stocks sufficient.")
    msg = "⚠️ *Low Stock!*\n\n"
    for item in low:
        msg += f"• {item.get_paper_type_display()}: {item.quantity} sheets (threshold: {item.low_stock_threshold})\n"
    return send_whatsapp_message(sender, msg)


def cmd_admin_system_status(sender):
    s = SystemSettings.load()
    msg = f"⚙️ *System:* {'⏸️ PAUSED' if s.is_paused else '▶️ RUNNING'}\n"
    if s.is_paused: msg += f"Reason: {s.pause_reason}\n"
    active = Order.objects.filter(status__in=['paid', 'printing', 'in_transit', 'ready']).count()
    msg += f"Active: {active}\n"
    msg += "Send *Resume* to restart." if s.is_paused else "Send *Pause <reason>* to pause."
    return send_whatsapp_message(sender, msg)


def cmd_admin_pause(sender, reason=""):
    s = SystemSettings.load()
    if s.is_paused: return send_whatsapp_message(sender, "⚠️ Already paused.")
    s.is_paused = True
    s.pause_reason = reason or "Paused via WhatsApp"
    s.pause_started_at = timezone.now()
    s.save()
    return send_whatsapp_message(sender, f"⏸️ System PAUSED.")


def cmd_admin_resume(sender):
    s = SystemSettings.load()
    if not s.is_paused: return send_whatsapp_message(sender, "⚠️ Already running.")
    if s.pause_started_at:
        s.total_paused_seconds += (timezone.now() - s.pause_started_at).total_seconds()
    s.is_paused = False
    s.pause_started_at = None
    s.save()
    return send_whatsapp_message(sender, "▶️ System RESUMED.")


def cmd_admin_top_agents(sender):
    top = AgentEarning.get_top_agents(limit=5)
    if not top: return send_whatsapp_message(sender, "No data.")
    msg = "🏆 *Top Agents*\n\n"
    for i, a in enumerate(top, 1):
        name = a.get('agent__first_name') or a.get('agent__username', 'Unknown')
        msg += f"{i}. *{name}*: {a['total_earnings']:,.0f} UGX ({a['orders_count']} orders)\n"
    return send_whatsapp_message(sender, msg)


def cmd_admin_add_expense(sender, amount, category='other'):
    try:
        amount = float(amount)
        user = get_user_by_phone(sender)
        Expense.objects.create(category=category, amount=Decimal(str(amount)),
            description=f"Added via WhatsApp by {user.username if user else 'admin'}", created_by=user)
        return send_whatsapp_message(sender, f"✅ Expense: {amount:,.0f} UGX")
    except ValueError:
        return send_whatsapp_message(sender, "❌ Invalid amount. *Add expense 50000 paper*")


def cmd_admin_broadcast(sender, message):
    users = User.objects.filter(phone_number__isnull=False).exclude(phone_number='')[:50]
    sent = 0
    for u in users:
        try:
            send_whatsapp_message(u.phone_number, f"📢 *PrintHub*\n\n{message}")
            sent += 1
        except: pass
    return send_whatsapp_message(sender, f"📢 Sent to {sent} users.")


def cmd_admin_advert(sender, message):
    """Send advert to WhatsApp groups."""
    group_ids = getattr(settings, 'WHATSAPP_GROUP_IDS', [])
    if not group_ids:
        return send_whatsapp_message(sender, "❌ No groups configured. Add WHATSAPP_GROUP_IDS to settings.")
    sent = 0
    for gid in group_ids:
        try:
            send_whatsapp_message(gid, f"📢 *PrintHub Update*\n\n{message}\n\n📞 {settings.WHATSAPP_BUSINESS_PHONE}\n🌐 printlink.pythonanywhere.com")
            sent += 1
        except: pass
    return send_whatsapp_message(sender, f"📢 Advert sent to {sent} groups.")


# ══════════════════════════════════════════════════════════════
# AGENT COMMANDS
# ══════════════════════════════════════════════════════════════

def cmd_agent_earnings(sender):
    user = get_user_by_phone(sender)
    if not user: return send_whatsapp_message(sender, "❌ Not found.")
    summary = AgentEarning.get_agent_summary(user)
    msg = f"💰 *Earnings*\nTotal: {summary['total_earned'] or 0:,.0f} UGX\n"
    msg += f"Paid: {summary['total_paid'] or 0:,.0f}\nPending: {summary['total_pending'] or 0:,.0f}"
    return send_whatsapp_message(sender, msg)


def cmd_agent_station(sender):
    user = get_user_by_phone(sender)
    if not user or not user.station: return send_whatsapp_message(sender, "❌ No station.")
    s = user.station
    active = Order.objects.filter(station=s, status__in=['paid', 'printing', 'in_transit', 'ready']).count()
    ready = Order.objects.filter(station=s, status='ready').count()
    return send_whatsapp_message(sender, f"📍 *{s.name}*\nActive: {active} | Ready: {ready}")


def cmd_agent_update(sender, order_id, new_status):
    user = get_user_by_phone(sender)
    if not user: return send_whatsapp_message(sender, "❌ Not found.")
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return send_whatsapp_message(sender, f"❌ Order #{order_id} not found.")
    if order.station != user.station:
        return send_whatsapp_message(sender, "❌ Not your station.")
    from orders.utils import apply_order_status_change
    if apply_order_status_change(order, new_status, user):
        return send_whatsapp_message(sender, f"✅ Order #{order.id} → {order.get_status_display()}")
    return send_whatsapp_message(sender, "❌ Failed.")


# ══════════════════════════════════════════════════════════════
# MAIN MESSAGE ROUTER (WITH GROUP SUPPORT)
# ══════════════════════════════════════════════════════════════

def handle_incoming_message(sender, message_text, is_group=False):
    """Route incoming message to appropriate handler."""
    text = message_text.strip()
    text_lower = text.lower()
    parts = text.split()
    command = parts[0].lower() if parts else ""

    # ═══ IN GROUPS: Only respond to commands, stay quiet otherwise ═══
    if is_group:
        if is_command(text_lower):
            pass  # Continue to process
        else:
            return  # Stay silent, don't respond to casual chat

    # ═══ ORDER CREATION ═══
    if command == 'order' and len(parts) >= 2:
        return cmd_order(sender, *parts[1:])

    if text_lower in ['confirm', 'yes', 'done']:
        return confirm_draft_order(sender)

    if text_lower in ['cancel', 'cancel order', 'discard']:
        return cancel_draft(sender)

    # ═══ STATION SELECTION ═══
    # Check if user has a draft and is replying with station choice
    if len(parts) == 1 and text.isdigit() and 1 <= int(text) <= 10:
        result = handle_station_selection(sender, text)
        if result:
            return result

    # ═══ UNIVERSAL COMMANDS ═══
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

    if text_lower in ['promo', 'promos', 'discount', 'offer', 'offers', 'hec10']:
        return cmd_promo(sender)

    if command in ['pay', 'payment'] and len(parts) >= 2 and parts[1].isdigit():
        return cmd_pay(sender, parts[1])

    if command in ['paid', 'paidfor'] and len(parts) >= 3:
        return cmd_paid(sender, parts[1], ' '.join(parts[2:]))

    if command in ['receipt', 'invoice'] and len(parts) >= 2 and parts[1].isdigit():
        return cmd_receipt(sender, parts[1])

    if '@' in text_lower:
        return cmd_track(sender, text_lower)

    if text.isdigit():
        return cmd_track(sender, text)

    # ═══ ADMIN COMMANDS ═══
    if is_admin_phone(sender):
        if text_lower in ['revenue', 'revenue today', 'sales']:
            return cmd_admin_revenue(sender)
        if text_lower in ['active', 'active orders', 'live', 'board']:
            return cmd_admin_active_orders(sender)
        if text_lower in ['pending', 'pending payments', 'approvals']:
            return cmd_admin_pending_payments(sender)
        if command == 'approve' and len(parts) >= 2 and parts[1].isdigit():
            return cmd_admin_approve(sender, parts[1])
        if command == 'reject' and len(parts) >= 2 and parts[1].isdigit():
            return cmd_admin_reject(sender, parts[1])
        if text_lower in ['low stock', 'lowstock', 'stock', 'paper']:
            return cmd_admin_low_stock(sender)
        if text_lower in ['system', 'status']:
            return cmd_admin_system_status(sender)
        if command == 'pause':
            return cmd_admin_pause(sender, ' '.join(parts[1:]) if len(parts) > 1 else '')
        if command == 'resume':
            return cmd_admin_resume(sender)
        if text_lower in ['top agents', 'topagents', 'agents']:
            return cmd_admin_top_agents(sender)
        if command in ['add', 'expense'] and len(parts) >= 3:
            amount = parts[2] if parts[1] == 'expense' else parts[1]
            category = parts[3] if len(parts) > 3 else 'other'
            return cmd_admin_add_expense(sender, amount, category)
        if command == 'broadcast' and len(parts) >= 2:
            return cmd_admin_broadcast(sender, ' '.join(parts[1:]))
        if command == 'advert' and len(parts) >= 2:
            return cmd_admin_advert(sender, ' '.join(parts[1:]))

    # ═══ AGENT COMMANDS ═══
    if is_agent_phone(sender):
        if text_lower in ['my earnings', 'earnings']:
            return cmd_agent_earnings(sender)
        if text_lower in ['my station', 'mystation']:
            return cmd_agent_station(sender)
        if text_lower in ['ready to collect', 'ready orders']:
            user = get_user_by_phone(sender)
            if user and user.station:
                ready = Order.objects.filter(station=user.station, status='ready')[:10]
                msg = f"✅ *Ready ({ready.count()})*\n\n"
                for o in ready: msg += f"#{o.id} - {o.file_name[:20]}...\n"
                return send_whatsapp_message(sender, msg)
        if command == 'update' and len(parts) >= 4:
            order_id = parts[1].replace('#', '')
            if order_id.isdigit() and parts[2] == 'to':
                return cmd_agent_update(sender, order_id, parts[3])

    # ═══ FALLBACK ═══
    if not is_group:
        return send_whatsapp_message(sender,
            "I didn't understand.\n\n"
            "📝 *Order <pages>* - Create order\n"
            "📋 *Track <id>* - Check order\n"
            "💰 *Pricing* - See rates\n"
            "Type *Help* for all commands."
        )


# ══════════════════════════════════════════════════════════════
# WEBHOOK ENDPOINT
# ══════════════════════════════════════════════════════════════

@csrf_exempt
def webhook_view(request):
    """WhatsApp Cloud API webhook."""
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        try:
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for msg in value.get("messages", []):
                        sender = msg.get("from", "")
                        msg_type = msg.get("type", "")
                        is_group = is_group_chat(sender)

                        if msg_type == "text":
                            text = msg.get("text", {}).get("body", "")
                            if sender and text:
                                handle_incoming_message(sender, text, is_group)

                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            if interactive.get("type") == "button_reply":
                                button_id = interactive.get("button_reply", {}).get("id", "")
                                if sender and button_id:
                                    handle_incoming_message(sender, button_id, is_group)

                        elif msg_type in ["image", "document", "video"]:
                            media_id = None
                            file_name = None
                            if msg_type == "image":
                                media_id = msg.get("image", {}).get("id")
                                file_name = msg.get("image", {}).get("caption", "image.jpg")
                            elif msg_type == "document":
                                media_id = msg.get("document", {}).get("id")
                                file_name = msg.get("document", {}).get("filename", "document.pdf")
                            elif msg_type == "video":
                                media_id = msg.get("video", {}).get("id")
                                file_name = msg.get("video", {}).get("caption", "video.mp4")

                            if sender and media_id:
                                result = handle_file_upload(sender, media_id, msg_type, file_name)
                                if not result and not is_group:
                                    send_whatsapp_message(sender,
                                        "📎 File received! To print, send *Order <pages>* first.\n"
                                        "Or upload at: https://printlink.pythonanywhere.com/upload/"
                                    )

        except Exception as e:
            print(f"WhatsApp webhook error: {e}")

        return JsonResponse({"status": "ok"})
    return HttpResponse("Method not allowed", status=405)


def health_check(request):
    return JsonResponse({
        "status": "healthy",
        "service": "PrintHub WhatsApp Bot",
        "version": "3.0.0",
        "features": [
            "order_creation_via_chat", "group_chat_support", "file_uploads",
            "scheduled_adverts", "human_takeover", "payment_processing",
            "admin_controls", "agent_management", "inventory_alerts"
        ],
        "timestamp": timezone.now().isoformat()
    })
