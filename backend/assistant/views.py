import re
import os
import urllib.parse
from decimal import Decimal
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.conf import settings

from orders.models import Order, SystemSettings, Announcement
from stations.models import Station
from payments.models import Payment
from finances.models import DiscountCode, MerchantSettings, AgentEarning
from accounts.models import CustomUser
from .models import AssistantDraft


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def format_response(text, suggestions=None, data=None, response_type="text", status=200):
    """Standard response format with structured data for rich UI."""
    return Response({
        "type": response_type,
        "text": text,
        "data": data or {},
        "suggestions": suggestions or []
    }, status=status)


def get_status_emoji(status):
    emoji_map = {
        'pending': '⏳', 'paid': '💳', 'printing': '🖨️',
        'in_transit': '🚚', 'ready': '✅', 'collected': '📦',
        'cancelled': '❌'
    }
    return emoji_map.get(status, '📋')


def get_status_color(status):
    color_map = {
        'pending': '#f59e0b',
        'paid': '#3b82f6',
        'printing': '#8b5cf6',
        'in_transit': '#f97316',
        'ready': '#22c55e',
        'collected': '#6b7280',
        'cancelled': '#ef4444'
    }
    return color_map.get(status, '#6b7280')


def is_admin(user):
    return user.is_staff or getattr(user, 'role', '') in ['admin', 'superadmin']


def is_agent(user):
    return getattr(user, 'role', '') == 'agent'


def extract_order_id(text):
    """Extract order ID from natural language."""
    patterns = [
        r'#?(\d{1,6})',
        r'order\s*#?\s*(\d{1,6})',
        r'track\s*#?\s*(\d{1,6})',
        r'status\s*#?\s*(\d{1,6})',
        r'pay\s*#?\s*(\d{1,6})',
        r'receipt\s*#?\s*(\d{1,6})',
        r'cancel\s*#?\s*(\d{1,6})',
        r'reorder\s*#?\s*(\d{1,6})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def get_user_orders_summary(user):
    """Safe, aggregated order stats for the user."""
    orders = Order.objects.filter(client=user)
    return {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'ready': orders.filter(status='ready').count(),
        'in_progress': orders.filter(status__in=['paid', 'printing', 'in_transit']).count(),
        'completed': orders.filter(status='collected').count(),
        'cancelled': orders.filter(status='cancelled').count(),
    }


def format_order_card(order):
    """Format a single order as structured data for rich rendering."""
    priority = order.priority_info
    return {
        'id': order.id,
        'file_name': order.file_name,
        'page_count': order.page_count,
        'is_color': order.is_color,
        'is_double_sided': order.is_double_sided,
        'binding': order.get_binding_display() if order.binding != 'none' else None,
        'status': order.status,
        'status_display': order.get_status_display(),
        'status_color': get_status_color(order.status),
        'status_emoji': get_status_emoji(order.status),
        'total_price': f"{order.total_price:,.0f}",
        'station': order.station.name if order.station else None,
        'delivery_type': order.get_delivery_type_display(),
        'time_left': priority['time_display'] if order.status not in ['pending', 'collected', 'cancelled'] else None,
        'is_overdue': priority['is_overdue'] if order.status not in ['pending', 'collected', 'cancelled'] else False,
        'created_at': order.created_at.strftime('%d %b %Y, %I:%M %p'),
        'paid_at': order.paid_at.strftime('%d %b %Y, %I:%M %p') if order.paid_at else None,
        'printing_at': order.printing_at.strftime('%d %b %Y, %I:%M %p') if order.printing_at else None,
        'ready_at': order.ready_at.strftime('%d %b %Y, %I:%M %p') if order.ready_at else None,
        'collected_at': order.collected_at.strftime('%d %b %Y, %I:%M %p') if order.collected_at else None,
    }


def get_user_draft(user):
    """Get or create a draft for the user."""
    draft, created = AssistantDraft.objects.get_or_create(user=user)
    return draft


def reset_draft(draft):
    """Reset draft to empty state."""
    draft.page_count = None
    draft.is_color = False
    draft.is_double_sided = False
    draft.binding = 'none'
    draft.delivery_type = 'pickup'
    draft.station_id = None
    draft.discount_code = None
    if draft.file:
        try:
            draft.file.delete(save=False)
        except Exception:
            pass
    draft.file = None
    draft.file_name = None
    draft.save()
    return draft


def get_draft_summary(draft):
    """Get a summary of the draft for display."""
    if not draft.page_count:
        return None
    
    total, effective, per_page = Order.compute_price(
        draft.page_count,
        draft.is_color,
        draft.is_double_sided,
        draft.binding,
        0
    )
    
    station_name = None
    if draft.station_id:
        try:
            station = Station.objects.get(id=draft.station_id)
            station_name = station.name
        except Station.DoesNotExist:
            pass
    
    return {
        'pages': draft.page_count,
        'is_color': draft.is_color,
        'is_double_sided': draft.is_double_sided,
        'binding': draft.binding,
        'delivery_type': draft.delivery_type,
        'station': station_name,
        'total': total,
        'effective_pages': effective,
        'per_page': per_page,
        'has_file': bool(draft.file),
        'file_name': draft.file_name,
    }


# ══════════════════════════════════════════════════════════════
# WHATSAPP / CONTACT HELPERS
# ══════════════════════════════════════════════════════════════

def get_whatsapp_link(number, message=None):
    """Generate WhatsApp link with optional pre-filled message."""
    clean_number = number.replace('+', '').replace(' ', '').replace('-', '')
    if message:
        encoded_msg = urllib.parse.quote(message)
        return f"https://wa.me/{clean_number}?text={encoded_msg}"
    return f"https://wa.me/{clean_number}"


def get_user_station_agent(user):
    """Get the agent assigned to the user's preferred station."""
    if user.station:
        agent = CustomUser.objects.filter(
            role='agent',
            station=user.station,
            is_active=True
        ).exclude(phone_number__isnull=True).exclude(phone_number='').first()
        if agent:
            return agent
    
    recent_order = Order.objects.filter(
        client=user,
        station__isnull=False
    ).order_by('-created_at').first()
    
    if recent_order and recent_order.station:
        agent = CustomUser.objects.filter(
            role='agent',
            station=recent_order.station,
            is_active=True
        ).exclude(phone_number__isnull=True).exclude(phone_number='').first()
        if agent:
            return agent
    
    orders_with_station = Order.objects.filter(
        client=user,
        station__isnull=False
    ).values('station').distinct()
    
    for order_station in orders_with_station:
        agent = CustomUser.objects.filter(
            role='agent',
            station_id=order_station['station'],
            is_active=True
        ).exclude(phone_number__isnull=True).exclude(phone_number='').first()
        if agent:
            return agent
    
    return None


def get_available_admin():
    """Get the first available admin or fallback number."""
    admin = CustomUser.objects.filter(
        Q(role='admin') | Q(is_staff=True),
        phone_number__isnull=False,
        is_active=True
    ).exclude(phone_number='').first()
    
    if admin:
        return admin.phone_number
    
    return getattr(settings, 'WHATSAPP_BUSINESS_PHONE', '+256791046296')


def get_default_whatsapp_number():
    """Get default WhatsApp number from settings."""
    return getattr(settings, 'WHATSAPP_BUSINESS_PHONE', '+256791046296')


# ══════════════════════════════════════════════════════════════
# MAIN CHAT VIEW
# ══════════════════════════════════════════════════════════════

class AssistantChatView(APIView):
    """Main chatbot endpoint - read-only, user-scoped."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()
        context_path = request.data.get('context', '')
        user = request.user

        if not message:
            return format_response(
                "📝 Please type a message. I'm here to help with orders, pricing, and more!",
                suggestions=["Help", "My orders", "Pricing"]
            )

        text_lower = message.lower()
        parts = message.split()
        command = parts[0].lower() if parts else ""

        # ─── CHECK SYSTEM PAUSE ───────────────────────────────
        system = SystemSettings.load()
        if system.is_paused and not is_admin(user):
            return format_response(
                f"⚠️ *System is currently paused.*\n\nReason: {system.pause_reason or 'Maintenance in progress.'}\n\nWe'll be back online shortly!",
                suggestions=["When will it be back?"]
            )

        # ─── GREETINGS ──────────────────────────────────────────
        if command in ['hi', 'hello', 'hey', 'start', 'menu', 'greetings', 'good morning', 'good afternoon', 'good evening']:
            return self._handle_welcome(user)

        if command in ['help', 'commands', 'what can you do', '?', 'help me']:
            return self._handle_help(user)

        # ─── TALK TO HUMAN ──────────────────────────────────────
        if text_lower in ['human', 'agent', 'talk to human', 'talk to agent', 'support', 
                          'help me', 'real person', 'live agent', 'human agent', 'person',
                          'contact', 'contact support', 'customer service']:
            return self._handle_talk_to_human(user, message)
        
        if text_lower in ['my agent', 'station agent', 'contact agent']:
            return self._handle_station_agent(user, message)
        
        if text_lower in ['admin', 'contact admin', 'support admin']:
            return self._handle_admin_contact(user, message)
        
        if 'whatsapp' in text_lower or 'whatsapp group' in text_lower:
            return self._handle_whatsapp_info(user)

        # ─── ORDER CREATION FLOW ──────────────────────────────
        if text_lower in ['i want to print', 'i need to print', 'print', 'start order', 'create order', 'start printing']:
            return self._handle_start_order(user)
        
        if text_lower in ['draft', 'my draft', 'show draft', 'view draft']:
            return self._handle_show_draft(user)
        
        if text_lower in ['clear draft', 'reset draft', 'delete draft', 'clear']:
            return self._handle_clear_draft(user)
        
        if text_lower in ['confirm', 'place order', 'submit order', 'confirm order']:
            return self._handle_confirm_order(user)
        
        if text_lower in ['edit', 'change', 'edit draft']:
            return self._handle_edit_draft(user, message)

        # ─── ORDER TEMPLATES ──────────────────────────────────
        if text_lower in ['templates', 'saved orders', 'my templates']:
            return self._handle_list_templates(user)
        
        if command == 'save' and len(parts) >= 2 and parts[1].lower() == 'template':
            name = ' '.join(parts[2:]) if len(parts) > 2 else None
            return self._handle_save_template(user, name)
        
        if command == 'use' and len(parts) >= 2:
            return self._handle_use_template(user, ' '.join(parts[1:]))

        # ─── SET ORDER OPTIONS ─────────────────────────────────
        if command in ['pages', 'page'] and len(parts) >= 2:
            try:
                pages = int(parts[1])
                return self._handle_set_pages(user, pages)
            except ValueError:
                pass
        
        if 'color' in text_lower and not any(x in text_lower for x in ['discount', 'station', 'location']):
            return self._handle_set_color(user, True)
        
        if 'b&w' in text_lower or 'bw' in text_lower:
            return self._handle_set_color(user, False)
        
        if 'double' in text_lower or 'two-sided' in text_lower:
            return self._handle_set_double_sided(user, True)
        
        if 'single' in text_lower:
            return self._handle_set_double_sided(user, False)
        
        if 'spiral' in text_lower:
            return self._handle_set_binding(user, 'spiral')
        if 'staple' in text_lower:
            return self._handle_set_binding(user, 'staple')
        if 'no binding' in text_lower or 'no binding' in text_lower:
            return self._handle_set_binding(user, 'none')
        
        if 'pickup' in text_lower:
            return self._handle_set_delivery(user, 'pickup')
        if 'delivery' in text_lower:
            return self._handle_set_delivery(user, 'delivery')

        # ─── REORDER ──────────────────────────────────────────
        if command in ['reorder', 'reprint'] and len(parts) >= 2:
            try:
                oid = int(parts[1].replace('#', ''))
                return self._handle_reorder(user, oid)
            except ValueError:
                pass

        # ─── ORDER TRACKING ────────────────────────────────────
        order_id = extract_order_id(text_lower)
        if order_id:
            return self._handle_track_order(user, order_id)

        if command in ['track', 'status', 'check'] and len(parts) >= 2:
            try:
                oid = int(parts[1].replace('#', ''))
                return self._handle_track_order(user, oid)
            except ValueError:
                pass

        # ─── MY ORDERS ─────────────────────────────────────────
        if text_lower in ['my orders', 'myorders', 'orders', 'order history', 'my print jobs', 'my prints', 'my jobs']:
            return self._handle_my_orders(user)

        if text_lower in ['summary', 'order summary', 'stats', 'statistics']:
            return self._handle_summary(user)

        # ─── FILTERED ORDERS ──────────────────────────────────
        if text_lower in ['pending orders', 'pending', 'pending order']:
            return self._handle_filtered_orders(user, 'pending')
        if text_lower in ['ready orders', 'ready', 'ready for pickup']:
            return self._handle_filtered_orders(user, 'ready')
        if text_lower in ['completed orders', 'collected', 'completed', 'done']:
            return self._handle_filtered_orders(user, 'collected')
        if text_lower in ['printing orders', 'printing', 'in progress']:
            return self._handle_filtered_orders(user, 'printing')

        # ─── PRICING ───────────────────────────────────────────
        if text_lower in ['pricing', 'price', 'prices', 'cost', 'rates', 'how much', 'price quote', 'quote']:
            return self._handle_pricing(message)

        # ─── STATIONS ──────────────────────────────────────────
        if text_lower in ['stations', 'location', 'locations', 'where', 'station', 'pickup', 'pick up', 
                          'pickup locations', 'where can i pick up', 'find stations']:
            return self._handle_stations()

        # ─── DISCOUNTS ─────────────────────────────────────────
        if text_lower in ['discount', 'promo', 'coupon', 'offer', 'offers', 'promotions', 'promo code', 'discounts']:
            return self._handle_discounts()

        # ─── NEW ORDER / UPLOAD ──────────────────────────────
        if text_lower in ['new order', 'place order', 'upload', 'order now', 'new orders', 'place orders']:
            return self._handle_new_order(user)

        # ─── PAYMENT HELP ──────────────────────────────────────
        if 'pay' in text_lower or 'payment' in text_lower:
            if order_id:
                return self._handle_payment_help(user, order_id)
            return self._handle_payment_help(user)

        # ─── RECEIPT ───────────────────────────────────────────
        if command in ['receipt', 'invoice', 'bill'] and len(parts) >= 2:
            try:
                oid = int(parts[1].replace('#', ''))
                return self._handle_receipt(user, oid)
            except ValueError:
                pass

        # ─── MY STATUS ─────────────────────────────────────────
        if text_lower in ['my status', 'my profile', 'who am i', 'account', 'profile']:
            return self._handle_my_status(user)

        # ─── CANCEL ORDER ──────────────────────────────────────
        if command in ['cancel', 'cancel order', 'delete order'] and order_id:
            return self._handle_cancel_order(user, order_id)

        # ─── ORDER CREATION (Simple) ──────────────────────────
        if command == 'order' and len(parts) >= 2:
            try:
                pages = int(parts[1])
                return self._handle_simple_order(user, pages, parts[2:])
            except ValueError:
                pass

        # ─── AGENT COMMANDS ────────────────────────────────────
        if is_agent(user):
            if text_lower in ['my station', 'mystation', 'station info']:
                return self._handle_agent_station(user)
            if text_lower in ['earnings', 'my earnings', 'commission', 'money']:
                return self._handle_agent_earnings(user)
            if text_lower in ['ready orders', 'ready for pickup']:
                return self._handle_agent_ready_orders(user)
            if command == 'update' and len(parts) >= 4 and parts[2] in ['to', 'as']:
                try:
                    oid = int(parts[1].replace('#', ''))
                    return self._handle_agent_update(user, oid, parts[3])
                except ValueError:
                    pass

        # ─── ADMIN COMMANDS ────────────────────────────────────
        if is_admin(user):
            if text_lower in ['revenue', 'sales', 'today revenue', 'earnings']:
                return self._handle_admin_revenue()
            if text_lower in ['active', 'active orders', 'live', 'live board']:
                return self._handle_admin_active()
            if text_lower in ['pending payments', 'approvals', 'payments']:
                return self._handle_admin_pending_payments()
            if command == 'approve' and len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    return self._handle_admin_approve(user, pid)
                except ValueError:
                    pass
            if command == 'reject' and len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    return self._handle_admin_reject(user, pid)
                except ValueError:
                    pass
            if text_lower in ['stock', 'low stock', 'paper', 'inventory']:
                return self._handle_admin_stock()
            if command == 'pause' and len(parts) >= 2:
                return self._handle_admin_pause(' '.join(parts[1:]))
            if command == 'resume':
                return self._handle_admin_resume()

        # ─── FALLBACK ──────────────────────────────────────────
        return self._handle_fallback(user, message)

    # ══════════════════════════════════════════════════════════
    # HANDLERS - ORDER MANAGEMENT
    # ══════════════════════════════════════════════════════════

    def _handle_welcome(self, user):
        """Personalized welcome with order stats."""
        name = user.first_name or user.username
        announcement = Announcement.get_active()
        ann_text = f"\n📢 {announcement.message}" if announcement else ""

        summary = get_user_orders_summary(user)

        msg = f"👋 *Welcome back, {name}!*{ann_text}\n\n"

        if summary['total'] > 0:
            msg += f"📊 *Your orders:* {summary['total']} total\n"
            if summary['ready'] > 0:
                msg += f"✅ *Ready:* {summary['ready']} — _Ready for pickup!_\n"
            if summary['pending'] > 0:
                msg += f"⏳ *Pending:* {summary['pending']} — _Awaiting payment or approval_\n"
            if summary['in_progress'] > 0:
                msg += f"🔄 *In Progress:* {summary['in_progress']} — _Being printed_\n"
            if summary['completed'] > 0:
                msg += f"📦 *Completed:* {summary['completed']} — _Collected_\n"
            msg += "\n"
        else:
            msg += "📭 You don't have any orders yet. Let's get you started!\n\n"

        msg += "What would you like to do?"

        suggestions = ["My orders", "Pricing", "New order", "Track order", "Stations", "Start order"]

        return format_response(msg, suggestions=suggestions, response_type="welcome")

    def _handle_help(self, user):
        """Show all available commands."""
        msg = "📋 *PrintHub Commands*\n\n"
        msg += "| Command | What it does |\n"
        msg += "|---------|--------------|\n"
        msg += "| *My orders* | View your order history |\n"
        msg += "| *Track #id* | Check order status |\n"
        msg += "| *Pricing* | See printing rates |\n"
        msg += "| *Stations* | Find pickup locations |\n"
        msg += "| *New order* | Start a print job |\n"
        msg += "| *Start order* | Step-by-step order creation |\n"
        msg += "| *Draft* | View your draft order |\n"
        msg += "| *Confirm* | Place your draft order |\n"
        msg += "| *Templates* | See saved order templates |\n"
        msg += "| *Reorder #id* | Duplicate a past order |\n"
        msg += "| *Discounts* | See active promotions |\n"
        msg += "| *Pay #id* | Get payment instructions |\n"
        msg += "| *Receipt #id* | Get order receipt |\n"
        msg += "| *Cancel #id* | Cancel pending order |\n"
        msg += "| *Human* | Talk to a real person |\n"

        if is_admin(user):
            msg += "\n🔐 *Admin Commands:*\n"
            msg += "• *Revenue* - Today's earnings\n"
            msg += "• *Active* - Live orders\n"
            msg += "• *Approve #id* - Approve payment\n"
            msg += "• *Reject #id* - Reject payment\n"
            msg += "• *Stock* - Paper inventory alerts\n"
            msg += "• *Pause reason* - Pause system\n"
            msg += "• *Resume* - Resume system\n"

        if is_agent(user):
            msg += "\n🖨️ *Agent Commands:*\n"
            msg += "• *My station* - Your station info\n"
            msg += "• *Earnings* - Your commissions\n"
            msg += "• *Ready orders* - Ready for pickup\n"
            msg += "• *Update #id to status* - Change order status\n"

        return format_response(msg, suggestions=["My orders", "Pricing", "New order", "Start order", "Human"])

    def _handle_track_order(self, user, order_id):
        """Track a specific order with rich data."""
        try:
            if is_admin(user):
                order = Order.objects.select_related('station', 'delivery_zone', 'client').get(id=order_id)
            else:
                order = Order.objects.select_related('station', 'delivery_zone').get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(
                f"❌ Order #{order_id} not found. Double-check the ID and try again.",
                suggestions=["My orders", "Track another"]
            )

        order_data = format_order_card(order)
        
        msg = f"📋 *Order #{order.id}*\n\n"
        msg += f"📄 *File:* {order.file_name}\n"
        msg += f"📄 *Pages:* {order.page_count}"
        if order.is_color:
            msg += " 🎨 Color"
        if order.is_double_sided:
            msg += " | Double-sided"
        msg += "\n"
        msg += f"📊 *Status:* {order_data['status_emoji']} {order_data['status_display']}\n"

        if order.status not in ['pending', 'collected', 'cancelled']:
            msg += f"⏱ *Time left:* {order_data['time_left']}\n"
            if order_data['is_overdue']:
                msg += "⚠️ *This order is overdue.* Please contact support.\n"

        if order.station:
            msg += f"📍 *Station:* {order.station.name}\n"
        if order.binding != 'none':
            msg += f"📚 *Binding:* {order.get_binding_display()}\n"

        msg += f"💰 *Total:* {order_data['total_price']} UGX\n\n"

        msg += "*📅 Timeline:*\n"
        if order.created_at:
            msg += f"• Submitted: {order.created_at.strftime('%d %b, %I:%M %p')}\n"
        if order.paid_at:
            msg += f"• 💳 Paid: {order.paid_at.strftime('%d %b, %I:%M %p')}\n"
        if order.printing_at:
            msg += f"• 🖨️ Printing: {order.printing_at.strftime('%d %b, %I:%M %p')}\n"
        if order.ready_at:
            msg += f"• ✅ Ready: {order.ready_at.strftime('%d %b, %I:%M %p')}\n"
        if order.collected_at:
            msg += f"• 📦 Collected: {order.collected_at.strftime('%d %b, %I:%M %p')}\n"

        suggestions = []
        if order.status == 'pending':
            suggestions.append(f"Pay #{order.id}")
        suggestions.append("My orders")
        suggestions.append("Track another")
        suggestions.append("Reorder #" + str(order.id))
        suggestions.append("Human")

        return format_response(
            msg,
            data={'type': 'order', **order_data},
            suggestions=suggestions,
            response_type="order_details"
        )

    def _handle_my_orders(self, user):
        """Show user's recent orders."""
        orders = Order.objects.filter(client=user).order_by('-created_at')[:10]

        if not orders.exists():
            return format_response(
                "📭 *No orders yet.*\n\nReady to start? Send *Start order* to get started, or check out *Pricing* to see our rates!",
                suggestions=["Start order", "Pricing", "Stations"]
            )

        summary = get_user_orders_summary(user)
        order_list = [format_order_card(o) for o in orders]

        msg = f"📚 *Your Orders* ({summary['total']} total)\n\n"

        stats = []
        if summary['ready'] > 0:
            stats.append(f"✅ Ready: {summary['ready']}")
        if summary['pending'] > 0:
            stats.append(f"⏳ Pending: {summary['pending']}")
        if summary['in_progress'] > 0:
            stats.append(f"🔄 In progress: {summary['in_progress']}")
        if summary['completed'] > 0:
            stats.append(f"📦 Completed: {summary['completed']}")
        if summary['cancelled'] > 0:
            stats.append(f"❌ Cancelled: {summary['cancelled']}")
        msg += " | ".join(stats) + "\n\n"

        msg += "*Recent:*\n"
        for order in orders[:5]:
            emoji = get_status_emoji(order.status)
            msg += f"#{order.id} {emoji} {order.get_status_display()}"
            if order.status == 'ready':
                msg += " ✅"
            msg += f" | {order.total_price:,.0f} UGX\n"
            msg += f"   📄 {order.file_name[:40]}\n"

        msg += "\n*Type Track #id for details.*"

        suggestions = [f"Track #{orders[0].id}", "Start order", "Pricing"]
        if summary['ready'] > 0:
            suggestions.insert(0, "Ready orders")
        suggestions.append("Human")

        return format_response(
            msg,
            data={'type': 'order_list', 'orders': order_list, 'summary': summary},
            suggestions=suggestions,
            response_type="order_list"
        )

    def _handle_summary(self, user):
        """Show order summary stats."""
        summary = get_user_orders_summary(user)

        msg = f"📊 *Order Summary*\n\n"
        msg += f"📋 Total: *{summary['total']}*\n"
        msg += f"⏳ Pending: *{summary['pending']}*\n"
        msg += f"🔄 In Progress: *{summary['in_progress']}*\n"
        msg += f"✅ Ready: *{summary['ready']}*\n"
        msg += f"📦 Completed: *{summary['completed']}*\n"
        msg += f"❌ Cancelled: *{summary['cancelled']}*\n"

        if summary['ready'] > 0:
            msg += f"\n🎉 You have {summary['ready']} order(s) ready for pickup!"
        elif summary['pending'] > 0:
            msg += f"\n💳 You have {summary['pending']} order(s) pending payment."
        elif summary['total'] == 0:
            msg += "\n📭 You haven't placed any orders yet."

        return format_response(msg, suggestions=["My orders", "Start order", "Pricing"])

    def _handle_filtered_orders(self, user, status):
        """Show orders filtered by status."""
        orders = Order.objects.filter(client=user, status=status).order_by('-created_at')[:10]
        status_label = dict(Order.STATUS_CHOICES).get(status, status.title())
        emoji = get_status_emoji(status)

        if not orders.exists():
            return format_response(f"📭 No {status_label} orders.")
        
        msg = f"{emoji} *{status_label} Orders* ({orders.count()})\n\n"
        for order in orders:
            msg += f"#{order.id} | {order.file_name[:30]}\n"
            msg += f"   💰 {order.total_price:,.0f} UGX | 📅 {order.created_at.strftime('%d %b')}\n"
            if order.station:
                msg += f"   📍 {order.station.name}\n"
            msg += "\n"

        suggestions = ["My orders", f"Track #{orders[0].id}"] if orders.exists() else ["My orders"]
        return format_response(msg, suggestions=suggestions, response_type="filtered_orders")

    # ══════════════════════════════════════════════════════════
    # HANDLERS - INFORMATION
    # ══════════════════════════════════════════════════════════

    def _handle_pricing(self, message):
        """Show pricing information."""
        quote_match = re.search(r'(\d+)\s*(?:pages?|pg|p)\s*(color|colour|b&w|bw)?', message, re.IGNORECASE)
        if quote_match:
            pages = int(quote_match.group(1))
            is_color = quote_match.group(2) and quote_match.group(2).lower() in ['color', 'colour']
            return self._handle_price_quote(pages, is_color)

        prices = [
            {'name': 'B&W Printing', 'price': '200 UGX/page'},
            {'name': 'Color Printing', 'price': '300 UGX/page'},
            {'name': 'Double-sided', 'price': '2 pages per sheet (same price)'},
            {'name': 'Spiral Binding', 'price': '1,000 UGX'},
            {'name': 'Passport Photo', 'price': '1,000 UGX/photo'},
            {'name': 'Scanning', 'price': '200 UGX/page'},
            {'name': 'Delivery', 'price': 'From 2,000 UGX'},
        ]

        msg = "💰 *PrintHub Pricing*\n\n"
        msg += "| Service | Price |\n"
        msg += "|---------|-------|\n"
        for p in prices:
            msg += f"| {p['name']} | *{p['price']}* |\n"

        now = timezone.now()
        discounts = DiscountCode.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        )

        if discounts.exists():
            msg += "\n🎫 *Active Promotions:*\n"
            for d in discounts[:3]:
                remaining = d.max_uses - d.used_count if d.max_uses > 0 else "∞"
                msg += f"• *{d.code}* - {d.description}\n"
                msg += f"  {remaining} uses left\n"

        return format_response(
            msg,
            data={'type': 'pricing', 'prices': prices, 'discounts': [d.code for d in discounts]},
            suggestions=["Start order", "Stations", "Discounts"],
            response_type="pricing"
        )

    def _handle_price_quote(self, pages, is_color=False):
        """Calculate a price quote."""
        from orders.models import Order
        total, effective, per_page = Order.compute_price(
            page_count=pages,
            is_color=is_color,
            is_double_sided=False,
            binding='none',
            delivery_fee=0
        )

        color_text = "🎨 Color" if is_color else "⚫ B&W"
        msg = f"💰 *Price Quote*\n\n"
        msg += f"📄 {pages} pages ({color_text})\n"
        msg += f"📊 Effective pages: {effective}\n"
        msg += f"💵 *Total: {total:,.0f} UGX*\n\n"
        msg += "_Add binding (+1,000 UGX) or double-sided for different pricing._"

        return format_response(msg, suggestions=["Start order", "Pricing"])

    def _handle_stations(self):
        """Show station locations."""
        stations = Station.objects.filter(is_active=True)

        if not stations.exists():
            return format_response(
                "📍 No stations available at the moment.\n\nPlease check back later or contact support.",
                suggestions=["Help", "Start order", "Human"]
            )

        station_data = []
        msg = "📍 *PrintHub Stations*\n\n"
        for s in stations:
            active_orders = Order.objects.filter(
                station=s,
                status__in=['paid', 'printing', 'in_transit', 'ready']
            ).count()
            
            station_data.append({
                'name': s.name,
                'active_orders': active_orders,
                'location': getattr(s, 'location_description', '')
            })
            
            msg += f"🏢 *{s.name}*\n"
            if hasattr(s, 'location_description') and s.location_description:
                msg += f"   📍 {s.location_description}\n"
            if active_orders > 0:
                msg += f"   📊 {active_orders} active orders\n"
            msg += "\n"

        return format_response(
            msg,
            data={'type': 'stations', 'stations': station_data},
            suggestions=["Start order", "Pricing", "Human"],
            response_type="stations"
        )

    def _handle_discounts(self):
        """Show active discounts."""
        now = timezone.now()
        discounts = DiscountCode.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        )

        if not discounts.exists():
            return format_response(
                "🎫 *No active promotions at the moment.*\n\nCheck back later for deals, or ask about student discounts!",
                suggestions=["Pricing", "Start order"]
            )

        msg = "🎫 *Active Promotions*\n\n"
        for d in discounts:
            remaining = d.max_uses - d.used_count if d.max_uses > 0 else "∞"
            msg += f"*{d.code}*\n"
            msg += f"   {d.description}\n"
            msg += f"   Type: {d.get_discount_type_display()}: {d.discount_value}%"
            if d.minimum_order > 0:
                msg += f" | Min. order: {d.minimum_order:,.0f} UGX"
            msg += f"\n   Uses left: {remaining}\n\n"

        return format_response(msg, suggestions=["Pricing", "Start order"])

    # ══════════════════════════════════════════════════════════
    # HANDLERS - ORDER CREATION FLOW
    # ══════════════════════════════════════════════════════════

    def _handle_start_order(self, user):
        """Start the order creation flow."""
        draft = get_user_draft(user)
        
        if draft.page_count:
            summary = get_draft_summary(draft)
            if summary:
                msg = "📝 *You have a draft order in progress!*\n\n"
                msg += f"📄 Pages: {summary['pages']}\n"
                msg += f"🎨 {'Color' if summary['is_color'] else 'B&W'}\n"
                if summary['is_double_sided']:
                    msg += "📄 Double-sided\n"
                if summary['binding'] != 'none':
                    msg += f"📚 {summary['binding'].title()}\n"
                if summary['station']:
                    msg += f"📍 {summary['station']}\n"
                msg += f"💰 Total: {summary['total']:,.0f} UGX\n\n"
                msg += "What would you like to do?\n"
                msg += "• *Confirm* - Place order\n"
                msg += "• *Edit* - Change options\n"
                msg += "• *Clear* - Start over"
                return format_response(
                    msg,
                    suggestions=["Confirm", "Edit", "Clear", "Upload file"],
                    data={'draft': summary}
                )
        
        reset_draft(draft)
        
        msg = "📤 *Start a New Order*\n\n"
        msg += "Let's create your print order step by step.\n\n"
        msg += "1️⃣ *How many pages?*\n"
        msg += "   Reply with: `20 pages` or just `20`\n\n"
        msg += "2️⃣ *Color or B&W?*\n"
        msg += "   Reply with: `Color` or `B&W`\n\n"
        msg += "3️⃣ *Single or double-sided?*\n"
        msg += "   Reply with: `Single` or `Double`\n\n"
        msg += "4️⃣ *Binding?*\n"
        msg += "   Reply with: `Spiral`, `Staple`, or `No binding`\n\n"
        msg += "5️⃣ *Pickup or delivery?*\n"
        msg += "   Reply with: `Pickup` or `Delivery`\n\n"
        msg += "You can also use the quick command:\n"
        msg += "*Order 20 Color Double Spiral Pickup*\n\n"
        msg += "Or use a template: *Use template <name>*"
        
        return format_response(
            msg,
            suggestions=["20 pages", "Color", "B&W", "Pickup"],
            response_type="order_start"
        )

    def _handle_show_draft(self, user):
        """Show current draft."""
        draft = get_user_draft(user)
        summary = get_draft_summary(draft)
        
        if not summary:
            return format_response(
                "📭 You don't have a draft order.\n\nStart one with *Start order* or *I want to print*",
                suggestions=["Start order", "New order", "Templates"]
            )
        
        msg = "📝 *Your Draft Order*\n\n"
        msg += f"📄 Pages: *{summary['pages']}*\n"
        msg += f"🎨 Type: *{'Color' if summary['is_color'] else 'B&W'}*\n"
        if summary['is_double_sided']:
            msg += "📄 Double-sided\n"
        if summary['binding'] != 'none':
            msg += f"📚 Binding: *{summary['binding'].title()}*\n"
        if summary['station']:
            msg += f"📍 Station: *{summary['station']}*\n"
        msg += f"📦 Delivery: *{summary['delivery_type'].title()}*\n"
        if summary['has_file']:
            msg += f"📎 File: *{summary['file_name']}*\n"
        msg += f"💰 Estimated Total: *{summary['total']:,.0f} UGX*\n\n"
        
        if not summary['has_file']:
            msg += "⚠️ *File missing!* Upload using the 📎 button.\n\n"
        
        msg += "What would you like to do?\n"
        msg += "• *Confirm* - Place order\n"
        msg += "• *Edit* - Change options\n"
        msg += "• *Clear* - Start over\n"
        msg += "• *Save template <name>* - Save for later"
        
        suggestions = ["Confirm", "Edit", "Clear"]
        if not summary['has_file']:
            suggestions.insert(0, "Upload file")
        suggestions.append("Save template")
        
        return format_response(
            msg,
            suggestions=suggestions,
            data={'draft': summary},
            response_type="draft_summary"
        )

    def _handle_clear_draft(self, user):
        """Clear the draft."""
        draft = get_user_draft(user)
        reset_draft(draft)
        return format_response(
            "🗑️ Draft cleared.\n\nStart a new one with *Start order*",
            suggestions=["Start order", "New order"]
        )

    def _handle_set_pages(self, user, pages):
        """Set pages in draft."""
        if pages < 1:
            return format_response("❌ Pages must be at least 1.")
        if pages > 1000:
            return format_response("⚠️ Maximum 1000 pages per order.")
        
        draft = get_user_draft(user)
        draft.page_count = pages
        draft.save()
        
        summary = get_draft_summary(draft)
        msg = f"✅ Pages set to *{pages}*\n\n"
        if summary:
            msg += f"💰 Estimated Total: *{summary['total']:,.0f} UGX*\n\n"
        msg += "Next: Set color or binding, or *Confirm* to place order."
        
        return format_response(
            msg,
            suggestions=["Color", "B&W", "Double", "Confirm"]
        )

    def _handle_set_color(self, user, is_color):
        """Set color in draft."""
        draft = get_user_draft(user)
        draft.is_color = is_color
        draft.save()
        
        color_text = "Color 🎨" if is_color else "B&W ⚫"
        msg = f"✅ Type set to *{color_text}*\n\n"
        
        summary = get_draft_summary(draft)
        if summary and summary['pages']:
            msg += f"💰 Estimated Total: *{summary['total']:,.0f} UGX*\n\n"
        msg += "Next: Set binding or *Confirm* to place order."
        
        return format_response(
            msg,
            suggestions=["Spiral", "Staple", "No binding", "Confirm"]
        )

    def _handle_set_double_sided(self, user, is_double):
        """Set double-sided in draft."""
        draft = get_user_draft(user)
        draft.is_double_sided = is_double
        draft.save()
        
        text = "Double-sided 📄" if is_double else "Single-sided 📄"
        msg = f"✅ Set to *{text}*\n\n"
        
        summary = get_draft_summary(draft)
        if summary and summary['pages']:
            msg += f"💰 Estimated Total: *{summary['total']:,.0f} UGX*\n\n"
        msg += "Next: Set binding or *Confirm* to place order."
        
        return format_response(
            msg,
            suggestions=["Spiral", "Staple", "No binding", "Confirm"]
        )

    def _handle_set_binding(self, user, binding):
        """Set binding in draft."""
        if binding not in ['none', 'staple', 'spiral']:
            return format_response("❌ Invalid binding. Options: Spiral, Staple, No binding")
        
        draft = get_user_draft(user)
        draft.binding = binding
        draft.save()
        
        binding_text = dict(Order.BINDING_CHOICES).get(binding, binding.title())
        msg = f"✅ Binding set to *{binding_text}*\n\n"
        
        summary = get_draft_summary(draft)
        if summary and summary['pages']:
            msg += f"💰 Estimated Total: *{summary['total']:,.0f} UGX*\n\n"
        msg += "Next: Choose station or *Confirm* to place order."
        
        stations = Station.objects.filter(is_active=True)
        suggestions = ["Confirm"]
        if stations.exists():
            for s in stations[:2]:
                suggestions.append(s.name)
        
        return format_response(
            msg,
            suggestions=suggestions
        )

    def _handle_set_delivery(self, user, delivery_type):
        """Set delivery type in draft."""
        if delivery_type not in ['pickup', 'delivery']:
            return format_response("❌ Invalid. Options: Pickup, Delivery")
        
        draft = get_user_draft(user)
        draft.delivery_type = delivery_type
        draft.save()
        
        text = "Pickup 🏢" if delivery_type == 'pickup' else "Delivery 🚚"
        msg = f"✅ Set to *{text}*\n\n"
        
        summary = get_draft_summary(draft)
        if summary and summary['pages']:
            msg += f"💰 Estimated Total: *{summary['total']:,.0f} UGX*\n\n"
        
        if delivery_type == 'delivery':
            msg += "📍 Please specify a delivery zone or address."
        else:
            msg += "📍 Choose a station or *Confirm* to place order."
        
        stations = Station.objects.filter(is_active=True)
        suggestions = ["Confirm"]
        if stations.exists():
            for s in stations[:2]:
                suggestions.append(s.name)
        
        return format_response(
            msg,
            suggestions=suggestions
        )

    def _handle_edit_draft(self, user, message):
        """Edit draft options."""
        draft = get_user_draft(user)
        if not draft.page_count:
            return format_response("❌ No draft to edit. Start with *Start order*")
        
        msg = "✏️ *Edit Your Draft*\n\n"
        msg += "What would you like to change?\n\n"
        msg += "• *Pages X* - Change page count\n"
        msg += "• *Color* or *B&W* - Change type\n"
        msg += "• *Double* or *Single* - Change sides\n"
        msg += "• *Spiral*, *Staple*, or *No binding*\n"
        msg += "• *Pickup* or *Delivery*\n"
        msg += "• *Clear* - Start over\n\n"
        msg += "Or just tell me what to change!"
        
        return format_response(
            msg,
            suggestions=["Pages 10", "Color", "Double", "Spiral", "Pickup", "Clear"]
        )

    def _handle_confirm_order(self, user):
        """Confirm and place the order."""
        draft = get_user_draft(user)
        
        if not draft.page_count:
            return format_response(
                "❌ No draft to confirm.\n\nStart with *Start order* or *I want to print*",
                suggestions=["Start order"]
            )
        
        if not draft.file:
            return format_response(
                "⚠️ *File missing!*\n\nUpload your document using the 📎 button below.\n\nThen type *Confirm* again.",
                suggestions=["Upload file"]
            )
        
        summary = get_draft_summary(draft)
        
        try:
            order = Order.objects.create(
                client=user,
                station_id=draft.station_id,
                file=draft.file,
                file_name=draft.file_name or f"Draft Order - {draft.page_count} pages",
                page_count=draft.page_count,
                is_color=draft.is_color,
                is_double_sided=draft.is_double_sided,
                binding=draft.binding,
                delivery_type=draft.delivery_type,
                status='pending',
                notes=f"Ordered via Assistant\nPages: {draft.page_count}\n"
                      f"Color: {'Yes' if draft.is_color else 'No'}\n"
                      f"Binding: {draft.binding}\n"
                      f"Delivery: {draft.delivery_type}"
            )
            
            order.calculate_price()
            order.save()
            
            reset_draft(draft)
            
            msg = f"✅ *Order #{order.id} Created!*\n\n"
            msg += f"📄 File: {order.file_name}\n"
            msg += f"📄 Pages: {order.page_count}"
            if order.is_color:
                msg += " 🎨 Color"
            if order.is_double_sided:
                msg += " | Double-sided"
            msg += "\n"
            if order.binding != 'none':
                msg += f"📚 Binding: {order.get_binding_display()}\n"
            if order.station:
                msg += f"📍 Station: {order.station.name}\n"
            msg += f"💰 Total: *{order.total_price:,.0f} UGX*\n\n"
            msg += "📝 *Next steps:*\n"
            msg += "1. Go to payment: *Pay #{}*\n".format(order.id)
            msg += "2. Track your order: *Track #{}*".format(order.id)
            
            try:
                from notifications.models import Notification
                admins = CustomUser.objects.filter(role='admin')
                for admin in admins:
                    Notification.create_notification(
                        user=admin,
                        notification_type='order_status',
                        title='New Order via Assistant',
                        message=f'Order #{order.id} placed by {user.username}',
                        link=f'/orders/admin-dashboard/'
                    )
            except Exception:
                pass
            
            return format_response(
                msg,
                suggestions=[f"Pay #{order.id}", f"Track #{order.id}", "My orders", "Start order"],
                data={'type': 'order', **format_order_card(order)},
                response_type="order_created"
            )
            
        except Exception as e:
            return format_response(f"❌ Error creating order: {str(e)}\n\nPlease try again or contact support.", suggestions=["Human"])

    # ══════════════════════════════════════════════════════════
    # HANDLERS - ORDER TEMPLATES
    # ══════════════════════════════════════════════════════════

    def _handle_list_templates(self, user):
        """List saved order templates."""
        try:
            from .models import OrderTemplate
            templates = OrderTemplate.objects.filter(user=user)
        except ImportError:
            return format_response(
                "📭 Templates are being set up.\n\nPlease check back soon!",
                suggestions=["Start order"]
            )
        
        if not templates.exists():
            return format_response(
                "📭 *No saved templates.*\n\nSave a draft as a template with:\n*Save template <name>*\n\nExample: *Save template Assignment*",
                suggestions=["Start order"]
            )
        
        msg = "📋 *Your Order Templates*\n\n"
        for t in templates[:5]:
            msg += f"• *{t.name}* - {t.pages} pages"
            if t.is_color:
                msg += " Color"
            msg += "\n"
            if t.binding != 'none':
                msg += f"  📚 {t.binding}\n"
            msg += "\n"
        
        msg += "Use a template with:\n*Use template <name>*"
        
        return format_response(
            msg,
            suggestions=[f"Use template {templates[0].name}" if templates.exists() else None, "Start order"]
        )

    def _handle_save_template(self, user, name):
        """Save current draft as a template."""
        if not name:
            return format_response("❌ Please provide a name: *Save template Assignment*")
        
        draft = get_user_draft(user)
        if not draft.page_count:
            return format_response("❌ No draft to save. Create one with *Start order*")
        
        try:
            from .models import OrderTemplate
            template, created = OrderTemplate.objects.update_or_create(
                user=user,
                name=name[:50],
                defaults={
                    'pages': draft.page_count,
                    'is_color': draft.is_color,
                    'is_double_sided': draft.is_double_sided,
                    'binding': draft.binding,
                    'delivery_type': draft.delivery_type,
                }
            )
        except ImportError:
            return format_response(
                "❌ Templates are being set up.\n\nPlease check back soon!",
                suggestions=["Start order"]
            )
        
        if created:
            msg = f"✅ Template *{name}* saved!"
        else:
            msg = f"✅ Template *{name}* updated!"
        
        msg += "\n\nUse it with: *Use template {}*".format(name)
        
        return format_response(msg, suggestions=["Use template {}".format(name), "My orders"])

    def _handle_use_template(self, user, name):
        """Use a saved template."""
        try:
            from .models import OrderTemplate
            template = OrderTemplate.objects.get(user=user, name=name)
        except (ImportError, OrderTemplate.DoesNotExist):
            return format_response(f"❌ Template *{name}* not found.\n\n*Templates* to see saved ones.")
        
        draft = get_user_draft(user)
        draft.page_count = template.pages
        draft.is_color = template.is_color
        draft.is_double_sided = template.is_double_sided
        draft.binding = template.binding
        draft.delivery_type = template.delivery_type
        draft.save()
        
        summary = get_draft_summary(draft)
        
        msg = f"✅ Template *{name}* loaded!\n\n"
        msg += f"📄 Pages: {summary['pages']}\n"
        msg += f"🎨 {'Color' if summary['is_color'] else 'B&W'}\n"
        if summary['is_double_sided']:
            msg += "📄 Double-sided\n"
        if summary['binding'] != 'none':
            msg += f"📚 {summary['binding'].title()}\n"
        msg += f"💰 Total: {summary['total']:,.0f} UGX\n\n"
        msg += "Upload your file and type *Confirm* to place the order."
        
        return format_response(
            msg,
            suggestions=["Upload file", "Confirm", "Edit", "Clear"],
            data={'draft': summary}
        )

    # ══════════════════════════════════════════════════════════
    # HANDLERS - REORDER
    # ══════════════════════════════════════════════════════════

    def _handle_reorder(self, user, order_id):
        """Create a new order from a past order."""
        try:
            old_order = Order.objects.get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found.", suggestions=["My orders"])
        
        draft = get_user_draft(user)
        draft.page_count = old_order.page_count
        draft.is_color = old_order.is_color
        draft.is_double_sided = old_order.is_double_sided
        draft.binding = old_order.binding
        draft.delivery_type = old_order.delivery_type
        draft.station_id = old_order.station_id
        draft.save()
        
        summary = get_draft_summary(draft)
        
        msg = f"🔄 *Reordering Order #{order_id}*\n\n"
        msg += f"📄 Pages: {summary['pages']}\n"
        msg += f"🎨 {'Color' if summary['is_color'] else 'B&W'}\n"
        if summary['is_double_sided']:
            msg += "📄 Double-sided\n"
        if summary['binding'] != 'none':
            msg += f"📚 {summary['binding'].title()}\n"
        if summary['station']:
            msg += f"📍 {summary['station']}\n"
        msg += f"💰 Total: {summary['total']:,.0f} UGX\n\n"
        msg += "Upload your new file and type *Confirm* to place the order."
        
        return format_response(
            msg,
            suggestions=["Upload file", "Confirm", "Edit", "Clear"]
        )

    def _handle_new_order(self, user):
        """Help user start a new order."""
        try:
            draft = AssistantDraft.objects.get(user=user)
            if draft.page_count:
                msg = "📝 *You have a draft order!*\n\n"
                msg += f"📄 Pages: {draft.page_count}\n"
                msg += f"🎨 {'Color' if draft.is_color else 'B&W'}\n"
                if draft.file:
                    msg += f"📎 File: {draft.file_name}\n"
                msg += "\n*Type Confirm* to place it, or *Cancel* to discard."
                return format_response(msg, suggestions=["Confirm", "Cancel", "Start over"])
        except AssistantDraft.DoesNotExist:
            pass

        msg = "📤 *Start a New Order*\n\n"
        msg += "1️⃣ Upload your file (📎 button below)\n"
        msg += "2️⃣ Type *Order <pages>*\n"
        msg += "3️⃣ Choose your options\n"
        msg += "4️⃣ Complete payment\n\n"
        msg += "📎 Or upload at: www.printhubug.com/upload/"

        return format_response(msg, suggestions=["Upload file", "Pricing", "Stations", "Human", "Start order"])

    # ══════════════════════════════════════════════════════════
    # HANDLERS - TALK TO HUMAN
    # ══════════════════════════════════════════════════════════

    def _handle_talk_to_human(self, user, message=""):
        """Show options for talking to a human."""
        has_station_agent = get_user_station_agent(user) is not None
        has_admin = CustomUser.objects.filter(
            Q(role='admin') | Q(is_staff=True),
            phone_number__isnull=False,
            is_active=True
        ).exclude(phone_number='').exists()
        
        has_order = Order.objects.filter(
            client=user,
            status__in=['pending', 'ready', 'paid', 'printing', 'in_transit']
        ).exists()
        
        msg = "📞 *Talk to a Human*\n\n"
        msg += "Choose who you'd like to contact:\n\n"
        
        options = []
        
        if has_station_agent:
            agent = get_user_station_agent(user)
            station_name = agent.station.name if agent and agent.station else "your station"
            options.append({
                'id': 'agent',
                'label': '🏢 Station Agent',
                'desc': f'Contact the agent at {station_name}',
            })
        elif has_order:
            options.append({
                'id': 'agent',
                'label': '🏢 Station Agent',
                'desc': 'Contact the agent at your pickup station',
            })
        
        if has_admin:
            options.append({
                'id': 'admin',
                'label': '👤 Admin / Support',
                'desc': 'Contact PrintHub support team',
            })
        else:
            options.append({
                'id': 'admin',
                'label': '👤 Admin / Support',
                'desc': 'Contact PrintHub support team',
            })
        
        options.append({
            'id': 'whatsapp',
            'label': '📱 WhatsApp Support',
            'desc': 'Chat with us directly on WhatsApp',
        })
        
        for i, opt in enumerate(options, 1):
            msg += f"{i}. {opt['label']}\n"
            msg += f"   _{opt['desc']}_\n\n"
        
        msg += "💬 *Reply with:*\n"
        msg += "• `Agent` - Contact your station agent\n"
        msg += "• `Admin` - Contact PrintHub support\n"
        msg += "• `WhatsApp` - Chat on WhatsApp\n"
        
        if has_order:
            msg += "\n📦 *Tip:* Include your order number for faster help!"
        
        suggestions = []
        if has_station_agent:
            suggestions.append("Agent")
        suggestions.append("Admin")
        suggestions.append("WhatsApp")
        suggestions.append("My orders")
        
        return format_response(
            msg,
            suggestions=suggestions,
            data={
                'type': 'contact_options',
                'has_agent': has_station_agent,
                'has_admin': has_admin,
            },
            response_type="contact_options"
        )

    def _handle_station_agent(self, user, message=""):
        """Get the station agent's contact info."""
        agent = get_user_station_agent(user)
        
        order_id = extract_order_id(message)
        order = None
        if order_id:
            try:
                order = Order.objects.get(id=order_id, client=user)
            except Order.DoesNotExist:
                pass
        
        context_msg = ""
        if order:
            context_msg = f"Order #{order.id} - {order.file_name}"
        else:
            recent = Order.objects.filter(client=user).order_by('-created_at').first()
            if recent:
                context_msg = f"Order #{recent.id} - {recent.file_name}"
            elif user.station:
                context_msg = f"Station: {user.station.name}"
        
        if agent and agent.phone_number:
            number = agent.phone_number
            station_name = agent.station.name if agent.station else "your station"
            agent_name = agent.get_full_name() or agent.username
            
            if context_msg:
                prefilled = f"Hi {agent_name}, I need help with {context_msg}. My username is {user.username}."
            else:
                prefilled = f"Hi {agent_name}, I need help with my printing. My username is {user.username}."
            
            wa_link = get_whatsapp_link(number, prefilled)
            
            msg = f"🏢 *Your Station Agent*\n\n"
            msg += f"👤 *Name:* {agent_name}\n"
            msg += f"📍 *Station:* {station_name}\n"
            msg += f"📱 *WhatsApp:* `{number}`\n\n"
            msg += f"🔗 [Click to chat]({wa_link})\n\n"
            
            if context_msg:
                msg += f"📝 *Context:* {context_msg}\n\n"
            
            msg += "_The agent knows your order details._"
            
            return format_response(
                msg,
                suggestions=["Open WhatsApp", "My orders", "Admin", "Help"],
                data={
                    'type': 'contact',
                    'contact_type': 'agent',
                    'name': agent_name,
                    'station': station_name,
                    'whatsapp_number': number,
                    'whatsapp_link': wa_link,
                    'prefilled_message': prefilled
                },
                response_type="contact"
            )
        
        fallback = get_default_whatsapp_number()
        if context_msg:
            prefilled = f"Hi PrintHub, I need help with {context_msg}. My username is {user.username}."
        else:
            prefilled = f"Hi PrintHub, I need help. My username is {user.username}."
        
        wa_link = get_whatsapp_link(fallback, prefilled)
        
        msg = f"🏢 *Station Agent*\n\n"
        msg += f"⚠️ No agent is currently assigned to your station.\n\n"
        msg += f"📱 *Fallback Support:* `{fallback}`\n"
        msg += f"🔗 [Click to chat]({wa_link})\n\n"
        msg += "_Our support team will assist you._"
        
        return format_response(
            msg,
            suggestions=["Open WhatsApp", "Admin", "My orders"],
            data={
                'type': 'contact',
                'contact_type': 'fallback',
                'whatsapp_number': fallback,
                'whatsapp_link': wa_link
            },
            response_type="contact"
        )

    def _handle_admin_contact(self, user, message=""):
        """Get admin contact info."""
        number = get_available_admin()
        
        order_id = extract_order_id(message)
        order = None
        if order_id:
            try:
                order = Order.objects.get(id=order_id, client=user)
            except Order.DoesNotExist:
                pass
        
        context_msg = ""
        if order:
            context_msg = f"Order #{order.id} - {order.file_name}"
        else:
            recent = Order.objects.filter(client=user).order_by('-created_at').first()
            if recent:
                context_msg = f"Order #{recent.id} - {recent.file_name}"
        
        if context_msg:
            prefilled = f"Hi PrintHub Support, I need help with {context_msg}. My username is {user.username}."
        else:
            prefilled = f"Hi PrintHub Support, I need help. My username is {user.username}."
        
        wa_link = get_whatsapp_link(number, prefilled)
        
        admin_online = CustomUser.objects.filter(
            Q(role='admin') | Q(is_staff=True),
            is_active=True
        ).count()
        
        msg = f"👤 *PrintHub Support*\n\n"
        msg += f"📱 *WhatsApp:* `{number}`\n"
        msg += f"🔗 [Click to chat]({wa_link})\n\n"
        
        if context_msg:
            msg += f"📝 *Context:* {context_msg}\n\n"
        
        if admin_online > 0:
            msg += f"👤 *{admin_online} support staff available*\n"
        msg += f"⏰ Response within 5-30 minutes"
        
        return format_response(
            msg,
            suggestions=["Open WhatsApp", "My orders", "Agent", "Help"],
            data={
                'type': 'contact',
                'contact_type': 'admin',
                'whatsapp_number': number,
                'whatsapp_link': wa_link,
                'prefilled_message': prefilled,
                'staff_online': admin_online
            },
            response_type="contact"
        )

    def _handle_whatsapp_info(self, user):
        """Show WhatsApp information."""
        number = get_available_admin()
        wa_link = get_whatsapp_link(number)
        
        msg = f"📱 *PrintHub WhatsApp Support*\n\n"
        msg += f"📞 Number: `{number}`\n"
        msg += f"🔗 [Click to chat]({wa_link})\n\n"
        msg += f"_Click the link to chat with us._\n\n"
        msg += "💡 We respond within 5-30 minutes during business hours."
        
        return format_response(
            msg,
            suggestions=["Open WhatsApp", "My orders", "Help", "Agent"],
            data={
                'type': 'contact',
                'contact_type': 'whatsapp',
                'whatsapp_number': number,
                'whatsapp_link': wa_link
            },
            response_type="contact"
        )

    # ══════════════════════════════════════════════════════════
    # HANDLERS - AGENT
    # ══════════════════════════════════════════════════════════

    def _handle_agent_station(self, user):
        """Show agent's station info."""
        if not user.station:
            return format_response(
                "❌ You haven't been assigned to a station yet.\n\nContact an admin to get set up.",
                suggestions=["Help", "Admin"]
            )

        station = user.station
        active = Order.objects.filter(
            station=station,
            status__in=['paid', 'printing', 'in_transit', 'ready']
        ).count()
        ready = Order.objects.filter(station=station, status='ready').count()
        today = Order.objects.filter(station=station, created_at__date=timezone.now().date()).count()

        msg = f"📍 *{station.name}*\n\n"
        msg += f"📊 Active orders: *{active}*\n"
        msg += f"✅ Ready for pickup: *{ready}*\n"
        msg += f"📋 Today's orders: *{today}*\n"

        if ready > 0:
            msg += f"\n🎯 *Action:* You have {ready} orders ready for pickup!"

        return format_response(msg, suggestions=["Ready orders", "My earnings", "My station", "Human"])

    def _handle_agent_earnings(self, user):
        """Show agent's earnings."""
        summary = AgentEarning.get_agent_summary(user)

        msg = f"💰 *My Earnings*\n\n"
        msg += f"📊 Total Earned: *{summary['total_earned'] or 0:,.0f} UGX*\n"
        msg += f"💳 Paid: *{summary['total_paid'] or 0:,.0f} UGX*\n"
        msg += f"⏳ Pending: *{summary['total_pending'] or 0:,.0f} UGX*\n"
        msg += f"📋 Orders processed: *{summary['orders_count'] or 0}*\n"

        if summary['total_pending'] and summary['total_pending'] > 0:
            msg += f"\n💡 {summary['total_pending']:,.0f} UGX pending payment from admin."

        return format_response(msg, suggestions=["My station", "Ready orders", "Human"])

    def _handle_agent_ready_orders(self, user):
        """Show orders ready for pickup at agent's station."""
        if not user.station:
            return format_response("❌ No station assigned.", suggestions=["My station", "Human"])

        orders = Order.objects.filter(station=user.station, status='ready').order_by('-created_at')[:10]

        if not orders.exists():
            return format_response(
                "✅ No ready orders at your station.\n\nCheck back later or ask customers to track their orders.",
                suggestions=["My station", "My earnings"]
            )

        msg = f"✅ *Ready Orders* ({orders.count()})\n\n"
        for o in orders:
            msg += f"#{o.id} | {o.client.username}\n"
            msg += f"   📄 {o.file_name[:35]}\n"
            msg += f"   💰 {o.total_price:,.0f} UGX | 📅 {o.created_at.strftime('%d %b')}\n\n"

        return format_response(msg, suggestions=["My station", "My earnings", "Human"])

    def _handle_agent_update(self, user, order_id, new_status):
        """Update order status (agent only)."""
        if not user.station:
            return format_response("❌ No station assigned.", suggestions=["My station", "Human"])

        try:
            order = Order.objects.get(id=order_id, station=user.station)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found at your station.", suggestions=["My station"])

        valid_statuses = ['pending', 'paid', 'printing', 'in_transit', 'ready', 'collected', 'cancelled']
        if new_status not in valid_statuses:
            return format_response(
                f"❌ Invalid status. Options: {', '.join(valid_statuses)}",
                suggestions=["My station", "Ready orders"]
            )

        from orders.utils import apply_order_status_change
        if apply_order_status_change(order, new_status, user):
            return format_response(
                f"✅ Order #{order.id} updated to *{order.get_status_display()}*",
                suggestions=["My station", "Ready orders", f"Update #{order.id} to ..."]
            )

        return format_response("❌ Failed to update status. Please try again.")

    # ══════════════════════════════════════════════════════════
    # HANDLERS - ADMIN
    # ══════════════════════════════════════════════════════════

    def _handle_admin_revenue(self):
        """Show today's revenue."""
        today = timezone.now().date()
        data = Order.objects.filter(created_at__date=today).aggregate(
            total=Sum('total_price'),
            count=Count('id'),
            profit=Sum('profit')
        )
        pending = Payment.objects.filter(status='pending').count()

        msg = f"📊 *Today's Revenue*\n\n"
        msg += f"💰 Total Revenue: *{data['total'] or 0:,.0f} UGX*\n"
        msg += f"📋 Orders: *{data['count'] or 0}*\n"
        msg += f"📈 Profit: *{data['profit'] or 0:,.0f} UGX*\n"
        msg += f"⏳ Pending Payments: *{pending}*\n"

        if pending > 0:
            msg += f"\n💡 {pending} payment(s) pending approval."

        return format_response(msg, suggestions=["Active orders", "Pending payments", "Human"])

    def _handle_admin_active(self):
        """Show active orders."""
        orders = Order.objects.filter(
            status__in=['paid', 'printing', 'in_transit', 'ready']
        ).select_related('station')[:15]

        if not orders.exists():
            return format_response(
                "✅ No active orders.\n\nEverything is quiet!",
                suggestions=["Revenue", "Pending payments"]
            )

        msg = f"🖨️ *Active Orders* ({orders.count()})\n\n"
        for o in orders[:10]:
            p = o.priority_info
            msg += f"#{o.id} {get_status_emoji(o.status)} {o.get_status_display()}"
            if p['is_overdue']:
                msg += " ⛔"
            msg += f" | ⏱ {p['time_display']}"
            if o.station:
                msg += f" | 📍 {o.station.name}"
            msg += "\n"

        return format_response(msg, suggestions=["Refresh", "Pending payments", "Revenue"])

    def _handle_admin_pending_payments(self):
        """Show pending payments."""
        payments = Payment.objects.filter(status='pending').select_related('order', 'user')[:10]

        if not payments.exists():
            return format_response("✅ No pending payments.\n\nAll payments are processed.", suggestions=["Revenue"])

        msg = f"💳 *Pending Payments* ({payments.count()})\n\n"
        for p in payments:
            msg += f"#{p.id} | Order #{p.order.id} | {p.user.username}\n"
            msg += f"   💰 {p.amount:,.0f} UGX | TXN: `{p.transaction_id}`\n"
            msg += f"   📱 {p.customer_phone}\n"
            msg += f"   *Approve {p.id}* or *Reject {p.id}*\n\n"

        return format_response(msg, suggestions=["Approve 123", "Reject 123", "Revenue"])

    def _handle_admin_approve(self, user, payment_id):
        """Approve a payment."""
        try:
            payment = Payment.objects.get(id=payment_id, status='pending')
        except Payment.DoesNotExist:
            return format_response(f"❌ Payment #{payment_id} not found or already processed.", suggestions=["Pending payments"])

        if payment.approve(approved_by=user):
            msg = f"✅ *Payment #{payment.id} Approved!*\n\n"
            msg += f"💳 {payment.amount:,.0f} UGX\n"
            msg += f"📦 Order #{payment.order.id} is now PAID.\n"
            msg += f"👤 {payment.user.username}\n\n"
            msg += "The customer will be notified."
            return format_response(msg, suggestions=["Pending payments", "Active orders", "Revenue"])
        return format_response("❌ Failed to approve payment.", suggestions=["Pending payments"])

    def _handle_admin_reject(self, user, payment_id):
        """Reject a payment."""
        try:
            payment = Payment.objects.get(id=payment_id, status='pending')
        except Payment.DoesNotExist:
            return format_response(f"❌ Payment #{payment_id} not found or already processed.", suggestions=["Pending payments"])

        if payment.reject(rejected_by=user, reason="Rejected via Assistant"):
            msg = f"❌ *Payment #{payment.id} Rejected*\n\n"
            msg += f"💳 {payment.amount:,.0f} UGX\n"
            msg += f"📦 Order #{payment.order.id}\n"
            msg += f"👤 {payment.user.username}\n\n"
            msg += "The customer will be notified."
            return format_response(msg, suggestions=["Pending payments"])
        return format_response("❌ Failed to reject payment.", suggestions=["Pending payments"])

    def _handle_admin_stock(self):
        """Check low stock."""
        from finances.models import PaperInventory
        from django.db.models import F

        low = PaperInventory.objects.filter(
            quantity__lte=F('low_stock_threshold'),
            is_active=True
        )

        if not low.exists():
            return format_response(
                "✅ All paper stocks are sufficient.\n\nNo alerts to report.",
                suggestions=["Revenue"]
            )

        msg = "⚠️ *Low Stock Alerts*\n\n"
        for item in low:
            msg += f"• {item.get_paper_type_display()}\n"
            msg += f"   📦 {item.quantity} sheets remaining\n"
            msg += f"   📊 Threshold: {item.low_stock_threshold}\n"
            msg += f"   📋 Status: {'🔴 Critical' if item.quantity < item.low_stock_threshold/2 else '🟡 Low'}\n\n"

        return format_response(msg, suggestions=["Revenue"])

    def _handle_admin_pause(self, reason):
        """Pause the system."""
        system = SystemSettings.load()
        if system.is_paused:
            return format_response("⚠️ System is already paused.", suggestions=["Resume"])

        system.is_paused = True
        system.pause_reason = reason or "Paused via Assistant"
        system.pause_started_at = timezone.now()
        system.save()

        return format_response(
            f"⏸️ *System PAUSED*\n\nReason: {system.pause_reason}\n\nSend *Resume* to restart.",
            suggestions=["Resume", "Active orders"]
        )

    def _handle_admin_resume(self):
        """Resume the system."""
        system = SystemSettings.load()
        if not system.is_paused:
            return format_response("⚠️ System is already running.", suggestions=["Pause"])

        if system.pause_started_at:
            system.total_paused_seconds += (timezone.now() - system.pause_started_at).total_seconds()
        system.is_paused = False
        system.pause_started_at = None
        system.save()

        return format_response("▶️ *System RESUMED*\n\nAll timers are now active.", suggestions=["Active orders", "Revenue"])

    # ══════════════════════════════════════════════════════════
    # HANDLERS - ACCOUNT & PAYMENTS
    # ══════════════════════════════════════════════════════════

    def _handle_my_status(self, user):
        """Show user's account status."""
        summary = get_user_orders_summary(user)

        msg = f"📊 *Your PrintHub Status*\n\n"
        msg += f"👤 *{user.first_name or user.username}*\n"
        msg += f"📧 {user.email}\n"
        if user.phone_number:
            msg += f"📱 {user.phone_number}\n"
        msg += f"🎭 Role: *{user.role.title()}*\n\n"

        msg += "📚 *Order Stats:*\n"
        msg += f"• Total: {summary['total']}\n"
        msg += f"• Pending: {summary['pending']}\n"
        msg += f"• In Progress: {summary['in_progress']}\n"
        msg += f"• Ready: {summary['ready']}\n"
        msg += f"• Completed: {summary['completed']}\n"

        if is_agent(user) and user.station:
            msg += f"\n📍 *Station:* {user.station.name}"

        return format_response(msg, suggestions=["My orders", "Start order", "Profile", "Human"])

    def _handle_payment_help(self, user, order_id=None):
        """Help with payments."""
        if order_id:
            try:
                order = Order.objects.get(id=order_id, client=user)
                if order.status != 'pending':
                    return format_response(
                        f"⚠️ Order #{order_id} is already *{order.get_status_display()}*.\n\nNo payment needed!",
                        suggestions=["My orders"]
                    )
                return self._show_payment_instructions(user, order)
            except Order.DoesNotExist:
                return format_response(f"❌ Order #{order_id} not found.", suggestions=["My orders"])

        pending_orders = Order.objects.filter(client=user, status='pending')

        if pending_orders.exists():
            msg = f"💳 *You have {pending_orders.count()} pending order(s).*\n\n"
            msg += "Send *Pay #id* for specific instructions.\n\n"
            for o in pending_orders[:3]:
                msg += f"• #{o.id}: {o.total_price:,.0f} UGX — {o.file_name[:30]}\n"
            suggestions = [f"Pay #{o.id}" for o in pending_orders[:3]]
            suggestions.append("My orders")
            return format_response(msg, suggestions=suggestions)

        msg = "💳 *Payment Help*\n\n"
        msg += "1️⃣ Place an order first (*Start order*)\n"
        msg += "2️⃣ Send *Pay #id* for instructions\n"
        msg += "3️⃣ Pay via MTN or Airtel Mobile Money\n"
        msg += "4️⃣ Submit your transaction ID\n\n"
        msg += "📱 Supported: MTN MoMo (*165#) and Airtel Money (*185#)"

        return format_response(msg, suggestions=["Start order", "Pricing", "Human"])

    def _show_payment_instructions(self, user, order):
        """Show payment instructions for an order."""
        mtn = MerchantSettings.get_merchant('mtn')
        airtel = MerchantSettings.get_merchant('airtel')

        msg = f"💳 *Pay for Order #{order.id}*\n\n"
        msg += f"💰 Amount: *{order.total_price:,.0f} UGX*\n"
        msg += f"📄 File: {order.file_name}\n\n"

        if mtn:
            msg += f"📱 *MTN MoMo:*\n"
            msg += f"   Number: `{mtn.merchant_phone}`\n"
            msg += f"   Name: {mtn.merchant_name}\n\n"

        if airtel:
            msg += f"📱 *Airtel Money:*\n"
            msg += f"   Number: `{airtel.merchant_phone}`\n"
            msg += f"   Name: {airtel.merchant_name}\n\n"

        msg += "📝 *After payment:*\n"
        msg += f"Send: *Paid {order.id} <transaction_id>*\n\n"
        msg += "_Your payment will be verified within 5-30 minutes._"

        return format_response(msg, suggestions=[f"Paid {order.id} TXN123", "My orders", "Human"])

    def _handle_receipt(self, user, order_id):
        """Show receipt for an order."""
        try:
            order = Order.objects.get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found.", suggestions=["My orders"])

        msg = f"🧾 *Receipt - Order #{order.id}*\n\n"
        msg += f"📄 {order.file_name}\n"
        msg += f"📄 {order.page_count} pages"
        if order.is_color:
            msg += " 🎨 Color"
        if order.is_double_sided:
            msg += " | Double-sided"
        msg += "\n"
        msg += f"💰 Total: *{order.total_price:,.0f} UGX*\n"
        msg += f"📊 Status: {get_status_emoji(order.status)} {order.get_status_display()}\n"
        if order.station:
            msg += f"📍 Station: {order.station.name}\n"
        msg += f"📅 {order.created_at.strftime('%d %b %Y, %I:%M %p')}\n\n"
        msg += f"🔗 View full receipt: https://www.printhubug.com/orders/{order.id}/receipt/"

        return format_response(msg, suggestions=["My orders", f"Pay #{order.id}", "Human"])

    def _handle_cancel_order(self, user, order_id):
        """Cancel a pending order."""
        try:
            order = Order.objects.get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found.", suggestions=["My orders"])

        if order.status not in ['pending', 'paid']:
            return format_response(
                f"❌ Order #{order_id} cannot be cancelled.\n\nIt's already *{order.get_status_display()}*.",
                suggestions=["My orders"]
            )

        order.status = 'cancelled'
        order.cancellation_reason = 'Cancelled via Assistant'
        order.cancelled_at = timezone.now()
        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

        return format_response(
            f"✅ Order #{order.id} has been cancelled successfully.\n\nIf you paid, a refund will be processed.",
            suggestions=["My orders", "Start order", "Human"]
        )

    def _handle_simple_order(self, user, pages, options):
        """Handle simple order creation (draft)."""
        is_color = 'color' in ' '.join(options).lower()
        is_double_sided = 'double' in ' '.join(options).lower()
        binding = 'spiral' if 'spiral' in ' '.join(options).lower() else 'none'
        delivery_type = 'delivery' if 'delivery' in ' '.join(options).lower() else 'pickup'

        draft, _ = AssistantDraft.objects.get_or_create(user=user)
        draft.page_count = pages
        draft.is_color = is_color
        draft.is_double_sided = is_double_sided
        draft.binding = binding
        draft.delivery_type = delivery_type
        draft.save()

        total, effective, per_page = Order.compute_price(
            pages, is_color, is_double_sided, binding, 0
        )

        msg = f"📝 *Order Draft Created*\n\n"
        msg += f"📄 Pages: *{pages}*"
        if is_double_sided:
            msg += f" ({effective} sheets)"
        msg += "\n"
        msg += f"🎨 Type: *{'Color' if is_color else 'B&W'}*\n"
        if binding != 'none':
            msg += f"📚 Binding: *{dict(Order.BINDING_CHOICES).get(binding, binding)}*\n"
        msg += f"📍 Delivery: *{dict(Order.DELIVERY_TYPE_CHOICES).get(delivery_type, delivery_type)}*\n"
        msg += f"💰 Estimate: *{total:,.0f} UGX*\n\n"
        msg += "📎 Upload your file using the 📎 button, then type *Confirm*."

        return format_response(
            msg,
            suggestions=["Upload file", "Confirm", "Cancel", "Human"],
            data={'draft': {'pages': pages, 'total': total}},
            response_type="draft_created"
        )

    # ══════════════════════════════════════════════════════════
    # HANDLERS - FALLBACK
    # ══════════════════════════════════════════════════════════

    def _handle_fallback(self, user, message):
        """Smart fallback for unrecognized messages."""
        text_lower = message.lower()

        if any(word in text_lower for word in ['what', 'how', 'when', 'where', 'why', 'who', 'can', 'could', 'would']):
            return format_response(
                "🤔 *I can help with these things:*\n\n"
                "📋 *Track #id* — Check order status\n"
                "📚 *My orders* — View your orders\n"
                "💰 *Pricing* — See printing rates\n"
                "📍 *Stations* — Find pickup locations\n"
                "📤 *Start order* — Create a new order\n"
                "📞 *Human* — Talk to a real person\n\n"
                "What would you like to know?",
                suggestions=["Help", "My orders", "Pricing", "Start order", "Human"]
            )

        if text_lower in ['yes', 'yep', 'yeah', 'ok', 'okay', 'sure', 'alright']:
            return format_response(
                "🎯 *Great!*\n\nWhat would you like to do?\n\n"
                "• *My orders* — View your orders\n"
                "• *Pricing* — Check rates\n"
                "• *Start order* — Create a new order\n"
                "• *Human* — Talk to support\n"
                "• *Help* — See all commands",
                suggestions=["My orders", "Pricing", "Start order", "Human"]
            )

        if text_lower in ['no', 'nope', 'nah', 'not now', 'later']:
            return format_response(
                "👍 No problem. I'm here whenever you need me!\n\n"
                "Type *Help* to see all commands, or *Human* to talk to support.",
                suggestions=["Help", "My orders", "Pricing", "Start order", "Human"]
            )

        if text_lower in ['thanks', 'thank you', 'thx', 'thank']:
            return format_response(
                "🎉 You're welcome! Happy to help.\n\n"
                "Is there anything else I can assist you with?",
                suggestions=["My orders", "Pricing", "Start order", "Help", "Human"]
            )

        return format_response(
            "🤖 *I can help with these things:*\n\n"
            "📋 *Track #id* — Check order status\n"
            "📚 *My orders* — View your orders\n"
            "💰 *Pricing* — See printing rates\n"
            "📍 *Stations* — Find pickup locations\n"
            "📤 *Start order* — Create a new order\n"
            "📞 *Human* — Talk to a real person\n\n"
            "Type *Help* for all commands.",
            suggestions=["Help", "My orders", "Pricing", "Start order", "Human"]
        )


# ══════════════════════════════════════════════════════════════
# FILE UPLOAD VIEW
# ══════════════════════════════════════════════════════════════

class AssistantUploadView(APIView):
    """
    Secure file upload for the assistant.
    Files are stored in the user's draft (user-scoped).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        file_obj = request.FILES.get('file')

        if not file_obj:
            return format_response("❌ No file provided.\n\nPlease select a file to upload.", status=400)

        if file_obj.size > 10 * 1024 * 1024:
            return format_response(
                f"❌ File too large. Max 10MB.\n\nYour file is {(file_obj.size / 1024 / 1024):.1f}MB.",
                status=400
            )

        ext = os.path.splitext(file_obj.name)[1].lower()
        allowed = {'.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg', '.pptx'}
        if ext not in allowed:
            return format_response(
                f"❌ File type '{ext}' not allowed.\n\nSupported: {', '.join(sorted(allowed))}",
                status=400
            )

        try:
            import magic
            file_content = file_obj.read(1024)
            file_obj.seek(0)
            mime = magic.from_buffer(file_content, mime=True)

            allowed_mimes = {
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword',
                'text/plain',
                'image/png',
                'image/jpeg',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            }

            if mime not in allowed_mimes:
                return format_response(
                    f"❌ Invalid file content.\n\nDetected: {mime}\nPlease use a standard document format.",
                    status=400
                )
        except Exception:
            pass

        draft, created = AssistantDraft.objects.get_or_create(user=user)

        if draft.file:
            try:
                draft.file.delete(save=False)
            except Exception:
                pass

        draft.file = file_obj
        draft.file_name = file_obj.name
        draft.save()

        estimated_pages = 1
        if ext == '.pdf':
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(file_obj)
                estimated_pages = len(reader.pages)
                file_obj.seek(0)
            except Exception:
                pass

        msg = f"✅ *File Received!*\n\n"
        msg += f"📄 {file_obj.name}\n"
        msg += f"📦 {(file_obj.size / 1024):.1f} KB\n"
        if estimated_pages > 1:
            msg += f"📄 ~{estimated_pages} pages detected\n\n"
        else:
            msg += "\n"
        msg += "📝 *Next steps:*\n"
        msg += "1. Type *Order <pages>* to start\n"
        msg += "2. Or type *Confirm* to place order\n"
        msg += "3. Type *Cancel* to discard"

        suggestions = ["Confirm", f"Order {estimated_pages}", "Cancel", "Human"]

        return format_response(msg, suggestions=suggestions, response_type="file_success")

    def delete(self, request):
        """Delete draft file."""
        try:
            draft = AssistantDraft.objects.get(user=request.user)
            if draft.file:
                draft.file.delete(save=False)
            draft.file = None
            draft.file_name = None
            draft.save()
            return format_response("🗑️ File removed from draft.\n\nYou can upload a new one anytime.")
        except AssistantDraft.DoesNotExist:
            return format_response("No draft file to delete.", status=404)
