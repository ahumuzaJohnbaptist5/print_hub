import re
import os
import magic
from decimal import Decimal
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Q, Sum, Count

from orders.models import Order, SystemSettings, Announcement
from stations.models import Station
from payments.models import Payment
from finances.models import DiscountCode, MerchantSettings, AgentEarning
from .models import AssistantDraft


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def format_response(text, suggestions=None, data=None, response_type="text", status=200):
    """Standard response format for the frontend."""
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
    }


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
            return format_response("Please type a message.", status=400)

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
        if command in ['hi', 'hello', 'hey', 'start', 'menu', 'greetings', 'good morning', 'good afternoon']:
            return self._handle_welcome(user)

        if command in ['help', 'commands', 'what can you do', '?']:
            return self._handle_help(user)

        # ─── ORDER TRACKING ────────────────────────────────────
        order_id = extract_order_id(text_lower)
        if order_id:
            return self._handle_track_order(user, order_id)

        if command in ['track', 'status'] and len(parts) >= 2:
            try:
                oid = int(parts[1].replace('#', ''))
                return self._handle_track_order(user, oid)
            except ValueError:
                pass

        # ─── MY ORDERS ─────────────────────────────────────────
        if text_lower in ['my orders', 'myorders', 'orders', 'order history', 'my print jobs']:
            return self._handle_my_orders(user)

        if text_lower in ['summary', 'order summary', 'stats']:
            return self._handle_summary(user)

        # ─── FILTERED ORDERS ──────────────────────────────────
        if text_lower in ['pending orders', 'pending']:
            return self._handle_filtered_orders(user, 'pending')
        if text_lower in ['ready orders', 'ready']:
            return self._handle_filtered_orders(user, 'ready')
        if text_lower in ['completed orders', 'collected', 'completed']:
            return self._handle_filtered_orders(user, 'collected')

        # ─── PRICING ───────────────────────────────────────────
        if text_lower in ['pricing', 'price', 'prices', 'cost', 'rates', 'how much', 'price quote']:
            return self._handle_pricing(message)

        # ─── STATIONS ──────────────────────────────────────────
        if text_lower in ['stations', 'location', 'locations', 'where', 'station', 'pickup']:
            return self._handle_stations()

        # ─── DISCOUNTS ─────────────────────────────────────────
        if text_lower in ['discount', 'promo', 'coupon', 'offer', 'offers', 'promotions', 'promo code']:
            return self._handle_discounts()

        # ─── NEW ORDER / UPLOAD ──────────────────────────────
        if text_lower in ['new order', 'place order', 'upload', 'order now', 'start order', 'create order']:
            return self._handle_new_order(user)

        # ─── PAYMENT HELP ──────────────────────────────────────
        if 'pay' in text_lower or 'payment' in text_lower:
            if order_id:
                return self._handle_payment_help(user, order_id)
            return self._handle_payment_help(user)

        # ─── RECEIPT ───────────────────────────────────────────
        if command in ['receipt', 'invoice'] and len(parts) >= 2:
            try:
                oid = int(parts[1].replace('#', ''))
                return self._handle_receipt(user, oid)
            except ValueError:
                pass

        # ─── MY STATUS ─────────────────────────────────────────
        if text_lower in ['my status', 'my profile', 'who am i', 'account']:
            return self._handle_my_status(user)

        # ─── CANCEL ORDER ──────────────────────────────────────
        if command in ['cancel', 'cancel order'] and order_id:
            return self._handle_cancel_order(user, order_id)

        # ─── AGENT COMMANDS ────────────────────────────────────
        if is_agent(user):
            if text_lower in ['my station', 'mystation']:
                return self._handle_agent_station(user)
            if text_lower in ['earnings', 'my earnings', 'commission']:
                return self._handle_agent_earnings(user)
            if text_lower in ['ready orders', 'ready for pickup']:
                return self._handle_agent_ready_orders(user)
            if command == 'update' and len(parts) >= 4 and parts[2] == 'to':
                try:
                    oid = int(parts[1].replace('#', ''))
                    return self._handle_agent_update(user, oid, parts[3])
                except ValueError:
                    pass

        # ─── ADMIN COMMANDS ────────────────────────────────────
        if is_admin(user):
            if text_lower in ['revenue', 'sales', 'today revenue']:
                return self._handle_admin_revenue()
            if text_lower in ['active', 'active orders', 'live']:
                return self._handle_admin_active()
            if text_lower in ['pending payments', 'approvals']:
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
            if text_lower in ['stock', 'low stock', 'paper']:
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
                msg += f"✅ *Ready:* {summary['ready']}\n"
            if summary['pending'] > 0:
                msg += f"⏳ *Pending:* {summary['pending']}\n"
            msg += "\n"
        else:
            msg += "📭 You don't have any orders yet.\n\n"

        msg += "What would you like to do?"

        suggestions = ["My orders", "Pricing", "New order", "Track order", "Stations"]

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
        msg += "| *Discounts* | See active promotions |\n"
        msg += "| *Pay #id* | Get payment instructions |\n"
        msg += "| *Receipt #id* | Get order receipt |\n"
        msg += "| *Cancel #id* | Cancel pending order |\n"

        if is_admin(user):
            msg += "\n🔐 *Admin:* Revenue, Active, Approve, Reject, Stock, Pause, Resume\n"
        if is_agent(user):
            msg += "\n🖨️ *Agent:* My station, Earnings, Ready orders, Update #id to status\n"

        return format_response(msg, suggestions=["My orders", "Pricing", "New order"])

    def _handle_track_order(self, user, order_id):
        """Track a specific order - user-scoped."""
        try:
            if is_admin(user):
                order = Order.objects.select_related('station', 'delivery_zone', 'client').get(id=order_id)
            else:
                order = Order.objects.select_related('station', 'delivery_zone').get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(
                f"❌ Order #{order_id} not found.",
                suggestions=["My orders", "Track another"]
            )

        priority = order.priority_info
        emoji = get_status_emoji(order.status)

        msg = f"📋 *Order #{order.id}*\n\n"
        msg += f"📄 *File:* {order.file_name}\n"
        msg += f"📄 *Pages:* {order.page_count}"
        if order.is_color:
            msg += " 🎨 Color"
        if order.is_double_sided:
            msg += " | Double-sided"
        msg += "\n"
        msg += f"📊 *Status:* {emoji} {order.get_status_display()}\n"

        if order.status not in ['pending', 'collected', 'cancelled']:
            msg += f"⏱ *Time left:* {priority['time_display']}\n"
            if priority['is_overdue']:
                msg += "⚠️ *This order is overdue.*\n"

        if order.station:
            msg += f"📍 *Station:* {order.station.name}\n"
        if order.binding != 'none':
            msg += f"📚 *Binding:* {order.get_binding_display()}\n"

        msg += f"💰 *Total:* {order.total_price:,.0f} UGX\n\n"

        # Timeline
        msg += "*Timeline:*\n"
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

        suggestions = []
        if order.status == 'pending':
            suggestions.append(f"Pay #{order.id}")
        suggestions.append("My orders")
        suggestions.append("Track another")

        return format_response(msg, suggestions=suggestions, response_type="order_details")

    def _handle_my_orders(self, user):
        """Show user's recent orders."""
        orders = Order.objects.filter(client=user).order_by('-created_at')[:10]

        if not orders.exists():
            return format_response(
                "📭 *No orders yet.*\n\nSend *New order* to get started!",
                suggestions=["New order", "Pricing", "Stations"]
            )

        summary = get_user_orders_summary(user)

        msg = f"📚 *Your Orders* ({summary['total']} total)\n\n"

        # Show summary bar
        if summary['ready'] > 0:
            msg += f"✅ Ready: {summary['ready']}  "
        if summary['pending'] > 0:
            msg += f"⏳ Pending: {summary['pending']}  "
        if summary['in_progress'] > 0:
            msg += f"🔄 In progress: {summary['in_progress']}  "
        if summary['completed'] > 0:
            msg += f"📦 Completed: {summary['completed']}"
        msg += "\n\n"

        # Recent orders
        msg += "*Recent:*\n"
        for order in orders[:5]:
            emoji = get_status_emoji(order.status)
            msg += f"#{order.id} {emoji} {order.get_status_display()}"
            if order.status == 'ready':
                msg += " ✅"
            msg += f" | {order.total_price:,.0f} UGX\n"

        msg += "\n*Type Track #id for details.*"

        suggestions = [f"Track #{orders[0].id}", "New order", "Pricing"]
        if summary['ready'] > 0:
            suggestions.insert(0, "Ready orders")

        return format_response(msg, suggestions=suggestions, response_type="order_list")

    def _handle_summary(self, user):
        """Show order summary stats."""
        summary = get_user_orders_summary(user)

        msg = f"📊 *Order Summary*\n\n"
        msg += f"📋 Total: {summary['total']}\n"
        msg += f"⏳ Pending: {summary['pending']}\n"
        msg += f"🔄 In Progress: {summary['in_progress']}\n"
        msg += f"✅ Ready: {summary['ready']}\n"
        msg += f"📦 Completed: {summary['completed']}\n"

        return format_response(msg, suggestions=["My orders", "New order"])

    def _handle_filtered_orders(self, user, status):
        """Show orders filtered by status."""
        orders = Order.objects.filter(client=user, status=status).order_by('-created_at')[:10]

        status_label = dict(Order.STATUS_CHOICES).get(status, status.title())

        if not orders.exists():
            return format_response(f"📭 No {status_label} orders.")

        msg = f"📋 *{status_label} Orders*\n\n"
        for order in orders:
            emoji = get_status_emoji(order.status)
            msg += f"#{order.id} {emoji} {order.file_name[:30]}\n"
            msg += f"   {order.total_price:,.0f} UGX | {order.created_at.strftime('%d %b')}\n\n"

        suggestions = ["My orders", "Track #{orders[0].id}"] if orders.exists() else ["My orders"]

        return format_response(msg, suggestions=suggestions)

    # ══════════════════════════════════════════════════════════
    # HANDLERS - INFORMATION
    # ══════════════════════════════════════════════════════════

    def _handle_pricing(self, message):
        """Show pricing information."""
        # Check if user wants a quote
        quote_match = re.search(r'(\d+)\s*(?:pages?|pg|p)\s*(color|colour|b&w|bw)?', message, re.IGNORECASE)
        if quote_match:
            pages = int(quote_match.group(1))
            is_color = quote_match.group(2) and quote_match.group(2).lower() in ['color', 'colour']
            return self._handle_price_quote(pages, is_color)

        msg = "💰 *PrintHub Pricing*\n\n"
        msg += "| Service | Price |\n"
        msg += "|---------|-------|\n"
        msg += "| B&W Printing | *200 UGX*/page |\n"
        msg += "| Color Printing | *300 UGX*/page |\n"
        msg += "| Double-sided | Same as 1 page (2 per sheet) |\n"
        msg += "| Spiral Binding | *1,000 UGX* |\n"
        msg += "| Passport Photo | *1,000 UGX*/photo |\n"
        msg += "| Scanning | *200 UGX*/page |\n"
        msg += "| Delivery | From *2,000 UGX* |\n"

        # Show active discounts
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

        return format_response(msg, suggestions=["New order", "Stations", "Discounts"])

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

        msg = f"💰 *Price Quote*\n\n"
        msg += f"📄 {pages} pages"
        if is_color:
            msg += " 🎨 Color"
        else:
            msg += " ⚫ B&W"
        msg += f"\n📊 {effective} effective pages\n"
        msg += f"💵 *Total: {total:,.0f} UGX*\n\n"
        msg += "Add binding or double-sided for different pricing."

        return format_response(msg, suggestions=["New order", "Pricing"])

    def _handle_stations(self):
        """Show station locations."""
        stations = Station.objects.filter(is_active=True)

        if not stations.exists():
            return format_response("📍 No stations available at the moment.")

        msg = "📍 *PrintHub Stations*\n\n"
        for s in stations:
            msg += f"🏢 *{s.name}*\n"
            if hasattr(s, 'location_description') and s.location_description:
                msg += f"   {s.location_description}\n"
            # Count active orders
            active_orders = Order.objects.filter(
                station=s,
                status__in=['paid', 'printing', 'in_transit', 'ready']
            ).count()
            if active_orders > 0:
                msg += f"   📊 {active_orders} active orders\n"
            msg += "\n"

        return format_response(msg, suggestions=["New order", "Pricing"])

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
                "🎫 No active promotions at the moment.\n\nCheck back later!",
                suggestions=["Pricing", "New order"]
            )

        msg = "🎫 *Active Promotions*\n\n"
        for d in discounts:
            remaining = d.max_uses - d.used_count if d.max_uses > 0 else "∞"
            msg += f"*{d.code}*\n"
            msg += f"   {d.description}\n"
            msg += f"   {d.get_discount_type_display()}: {d.discount_value}%"
            if d.minimum_order > 0:
                msg += f" | Min. order: {d.minimum_order:,.0f} UGX"
            msg += f"\n   Remaining: {remaining} uses\n\n"

        return format_response(msg, suggestions=["Pricing", "New order"])

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
        msg += f"🎭 Role: {user.role.title()}\n\n"

        msg += "📚 *Order Stats:*\n"
        msg += f"• Total: {summary['total']}\n"
        msg += f"• Pending: {summary['pending']}\n"
        msg += f"• In Progress: {summary['in_progress']}\n"
        msg += f"• Ready: {summary['ready']}\n"
        msg += f"• Completed: {summary['completed']}\n"

        if is_agent(user) and user.station:
            msg += f"\n📍 *Station:* {user.station.name}"

        return format_response(msg, suggestions=["My orders", "New order"])

    def _handle_payment_help(self, user, order_id=None):
        """Help with payments."""
        if order_id:
            try:
                order = Order.objects.get(id=order_id, client=user)
                if order.status != 'pending':
                    return format_response(
                        f"⚠️ Order #{order_id} is already *{order.get_status_display()}*.",
                        suggestions=["My orders"]
                    )
                return self._show_payment_instructions(user, order)
            except Order.DoesNotExist:
                return format_response(f"❌ Order #{order_id} not found.")

        # Check for pending orders
        pending_orders = Order.objects.filter(client=user, status='pending')

        if pending_orders.exists():
            msg = f"💳 You have {pending_orders.count()} pending order(s).\n\n"
            msg += "*Send Pay #id for instructions.*\n\n"
            for o in pending_orders[:3]:
                msg += f"• #{o.id}: {o.total_price:,.0f} UGX\n"
            suggestions = [f"Pay #{o.id}" for o in pending_orders[:3]]
            suggestions.append("My orders")
            return format_response(msg, suggestions=suggestions)

        msg = "💳 *Payment Help*\n\n"
        msg += "1. Place an order first\n"
        msg += "2. Send *Pay #id* for instructions\n"
        msg += "3. Pay via MTN or Airtel\n"
        msg += "4. Submit your transaction ID"

        return format_response(msg, suggestions=["New order", "Pricing"])

    def _show_payment_instructions(self, user, order):
        """Show payment instructions for an order."""
        mtn = MerchantSettings.get_merchant('mtn')
        airtel = MerchantSettings.get_merchant('airtel')

        msg = f"💳 *Pay for Order #{order.id}*\n\n"
        msg += f"💰 Amount: *{order.total_price:,.0f} UGX*\n\n"

        if mtn:
            msg += f"📱 *MTN MoMo:*\n"
            msg += f"   Number: {mtn.merchant_phone}\n"
            msg += f"   Name: {mtn.merchant_name}\n\n"

        if airtel:
            msg += f"📱 *Airtel Money:*\n"
            msg += f"   Number: {airtel.merchant_phone}\n"
            msg += f"   Name: {airtel.merchant_name}\n\n"

        msg += "📝 *After payment:*\n"
        msg += f"Send: *Paid {order.id} <transaction_id>*"

        return format_response(msg, suggestions=[f"Paid {order.id} TXN123", "My orders"])

    def _handle_receipt(self, user, order_id):
        """Show receipt for an order."""
        try:
            order = Order.objects.get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found.")

        msg = f"🧾 *Receipt - Order #{order.id}*\n\n"
        msg += f"📄 {order.file_name}\n"
        msg += f"📄 {order.page_count} pages"
        if order.is_color:
            msg += " 🎨 Color"
        msg += "\n"
        msg += f"💰 Total: {order.total_price:,.0f} UGX\n"
        msg += f"📊 Status: {order.get_status_display()}\n"
        msg += f"📅 {order.created_at.strftime('%d %b %Y, %I:%M %p')}\n\n"
        msg += f"🔗 https://printlink.pythonanywhere.com/orders/{order.id}/receipt/"

        return format_response(msg, suggestions=["My orders", f"Pay #{order.id}"])

    def _handle_cancel_order(self, user, order_id):
        """Cancel a pending order."""
        try:
            order = Order.objects.get(id=order_id, client=user)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found.")

        if order.status not in ['pending', 'paid']:
            return format_response(
                f"❌ Order #{order_id} cannot be cancelled. It's already *{order.get_status_display()}*.",
                suggestions=["My orders"]
            )

        order.status = 'cancelled'
        order.cancellation_reason = 'Cancelled via Assistant'
        order.cancelled_at = timezone.now()
        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

        return format_response(
            f"✅ Order #{order.id} has been cancelled.",
            suggestions=["My orders", "New order"]
        )

    # ══════════════════════════════════════════════════════════
    # HANDLERS - NEW ORDER
    # ══════════════════════════════════════════════════════════

    def _handle_new_order(self, user):
        """Help user start a new order."""
        # Check for existing draft
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
        msg += "📎 Or upload at: printlink.pythonanywhere.com/upload/"

        return format_response(msg, suggestions=["Upload file", "Pricing", "Stations"])

    # ══════════════════════════════════════════════════════════
    # HANDLERS - AGENT
    # ══════════════════════════════════════════════════════════

    def _handle_agent_station(self, user):
        """Show agent's station info."""
        if not user.station:
            return format_response("❌ You haven't been assigned to a station yet.")

        station = user.station
        active = Order.objects.filter(
            station=station,
            status__in=['paid', 'printing', 'in_transit', 'ready']
        ).count()
        ready = Order.objects.filter(station=station, status='ready').count()
        today = Order.objects.filter(station=station, created_at__date=timezone.now().date()).count()

        msg = f"📍 *{station.name}*\n\n"
        msg += f"📊 Active: {active}\n"
        msg += f"✅ Ready: {ready}\n"
        msg += f"📋 Today: {today}\n"

        return format_response(msg, suggestions=["Ready orders", "My earnings"])

    def _handle_agent_earnings(self, user):
        """Show agent's earnings."""
        summary = AgentEarning.get_agent_summary(user)

        msg = f"💰 *My Earnings*\n\n"
        msg += f"📊 Total Earned: {summary['total_earned'] or 0:,.0f} UGX\n"
        msg += f"💳 Paid: {summary['total_paid'] or 0:,.0f} UGX\n"
        msg += f"⏳ Pending: {summary['total_pending'] or 0:,.0f} UGX\n"
        msg += f"📋 Orders: {summary['orders_count'] or 0}\n"

        return format_response(msg, suggestions=["My station", "Ready orders"])

    def _handle_agent_ready_orders(self, user):
        """Show orders ready for pickup at agent's station."""
        if not user.station:
            return format_response("❌ No station assigned.")

        orders = Order.objects.filter(station=user.station, status='ready').order_by('-created_at')[:10]

        if not orders.exists():
            return format_response("✅ No ready orders at your station.")

        msg = f"✅ *Ready Orders* ({orders.count()})\n\n"
        for o in orders:
            msg += f"#{o.id} | {o.client.username}\n"
            msg += f"   {o.file_name[:30]} | {o.total_price:,.0f} UGX\n\n"

        return format_response(msg, suggestions=["My station", "My earnings"])

    def _handle_agent_update(self, user, order_id, new_status):
        """Update order status (agent only)."""
        if not user.station:
            return format_response("❌ No station assigned.")

        try:
            order = Order.objects.get(id=order_id, station=user.station)
        except Order.DoesNotExist:
            return format_response(f"❌ Order #{order_id} not found at your station.")

        valid_statuses = ['pending', 'paid', 'printing', 'in_transit', 'ready', 'collected', 'cancelled']
        if new_status not in valid_statuses:
            return format_response(f"❌ Invalid status. Options: {', '.join(valid_statuses)}")

        from orders.utils import apply_order_status_change
        if apply_order_status_change(order, new_status, user):
            return format_response(
                f"✅ Order #{order.id} updated to *{order.get_status_display()}*",
                suggestions=["My station", "Ready orders"]
            )

        return format_response("❌ Failed to update status.")

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
        msg += f"💰 Total: {data['total'] or 0:,.0f} UGX\n"
        msg += f"📋 Orders: {data['count'] or 0}\n"
        msg += f"📈 Profit: {data['profit'] or 0:,.0f} UGX\n"
        msg += f"⏳ Pending Payments: {pending}\n"

        return format_response(msg, suggestions=["Active orders", "Pending payments"])

    def _handle_admin_active(self):
        """Show active orders."""
        orders = Order.objects.filter(
            status__in=['paid', 'printing', 'in_transit', 'ready']
        ).select_related('station')[:15]

        if not orders.exists():
            return format_response("✅ No active orders.")

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

        return format_response(msg, suggestions=["Refresh", "Pending payments"])

    def _handle_admin_pending_payments(self):
        """Show pending payments."""
        payments = Payment.objects.filter(status='pending').select_related('order', 'user')[:10]

        if not payments.exists():
            return format_response("✅ No pending payments.")

        msg = f"💳 *Pending Payments* ({payments.count()})\n\n"
        for p in payments:
            msg += f"#{p.id} | Order #{p.order.id} | {p.user.username}\n"
            msg += f"   {p.amount:,.0f} UGX | TXN: {p.transaction_id}\n"
            msg += f"   *Approve {p.id}* or *Reject {p.id}*\n\n"

        return format_response(msg, suggestions=["Approve 123", "Reject 123"])

    def _handle_admin_approve(self, user, payment_id):
        """Approve a payment."""
        try:
            payment = Payment.objects.get(id=payment_id, status='pending')
        except Payment.DoesNotExist:
            return format_response(f"❌ Payment #{payment_id} not found or already processed.")

        if payment.approve(approved_by=user):
            msg = f"✅ Payment #{payment.id} approved!\n"
            msg += f"Order #{payment.order.id} is now PAID."
            return format_response(msg, suggestions=["Pending payments", "Active orders"])
        return format_response("❌ Failed to approve payment.")

    def _handle_admin_reject(self, user, payment_id):
        """Reject a payment."""
        try:
            payment = Payment.objects.get(id=payment_id, status='pending')
        except Payment.DoesNotExist:
            return format_response(f"❌ Payment #{payment_id} not found or already processed.")

        if payment.reject(rejected_by=user, reason="Rejected via Assistant"):
            msg = f"❌ Payment #{payment.id} rejected."
            return format_response(msg, suggestions=["Pending payments"])
        return format_response("❌ Failed to reject payment.")

    def _handle_admin_stock(self):
        """Check low stock."""
        from finances.models import PaperInventory
        from django.db.models import F

        low = PaperInventory.objects.filter(
            quantity__lte=F('low_stock_threshold'),
            is_active=True
        )

        if not low.exists():
            return format_response("✅ All paper stocks are sufficient.")

        msg = "⚠️ *Low Stock Alerts*\n\n"
        for item in low:
            msg += f"• {item.get_paper_type_display()}: {item.quantity} sheets\n"
            msg += f"  Threshold: {item.low_stock_threshold}\n\n"

        return format_response(msg, suggestions=["Stock overview"])

    def _handle_admin_pause(self, reason):
        """Pause the system."""
        system = SystemSettings.load()
        if system.is_paused:
            return format_response("⚠️ System is already paused.")

        system.is_paused = True
        system.pause_reason = reason or "Paused via Assistant"
        system.pause_started_at = timezone.now()
        system.save()

        return format_response(f"⏸️ System PAUSED.\nReason: {system.pause_reason}\n\nSend *Resume* to restart.")

    def _handle_admin_resume(self):
        """Resume the system."""
        system = SystemSettings.load()
        if not system.is_paused:
            return format_response("⚠️ System is already running.")

        if system.pause_started_at:
            system.total_paused_seconds += (timezone.now() - system.pause_started_at).total_seconds()
        system.is_paused = False
        system.pause_started_at = None
        system.save()

        return format_response("▶️ System RESUMED.")

    # ══════════════════════════════════════════════════════════
    # HANDLERS - FALLBACK
    # ══════════════════════════════════════════════════════════

    def _handle_fallback(self, user, message):
        """Smart fallback for unrecognized messages."""
        text_lower = message.lower()

        # Check if it's a question
        if any(word in text_lower for word in ['what', 'how', 'when', 'where', 'why', 'who']):
            return format_response(
                "I can help with:\n\n"
                "• Tracking orders (*Track #123*)\n"
                "• Viewing your orders (*My orders*)\n"
                "• Pricing information (*Pricing*)\n"
                "• Station locations (*Stations*)\n"
                "• Starting a new order (*New order*)\n\n"
                "What would you like to know?",
                suggestions=["My orders", "Pricing", "New order"]
            )

        # Check if it's a simple yes/no
        if text_lower in ['yes', 'yep', 'yeah', 'ok', 'okay', 'sure']:
            return format_response(
                "Great! What would you like to do?\n\n"
                "• *My orders* - View your orders\n"
                "• *Pricing* - Check rates\n"
                "• *New order* - Start printing",
                suggestions=["My orders", "Pricing", "New order"]
            )

        if text_lower in ['no', 'nope', 'nah', 'not now']:
            return format_response(
                "No problem. Let me know if you need anything else!\n"
                "Type *Help* to see all commands.",
                suggestions=["Help", "My orders", "Pricing"]
            )

        # Generic fallback
        return format_response(
            "I can help with these things:\n\n"
            "📋 *Track #id* - Check order status\n"
            "📚 *My orders* - View your orders\n"
            "💰 *Pricing* - See printing rates\n"
            "📤 *New order* - Start a print job\n\n"
            "Type *Help* for all commands.",
            suggestions=["Help", "My orders", "Pricing", "New order"]
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
            return format_response("❌ No file provided.", status=400)

        # Validate size
        if file_obj.size > 10 * 1024 * 1024:
            return format_response(
                "❌ File too large. Max 10MB.",
                status=400
            )

        # Validate extension
        ext = os.path.splitext(file_obj.name)[1].lower()
        allowed = {'.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg', '.pptx'}
        if ext not in allowed:
            return format_response(
                f"❌ File type '{ext}' not allowed.\n\nSupported: {', '.join(sorted(allowed))}",
                status=400
            )

        # Validate MIME type
        try:
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
                    f"❌ Invalid file content. Detected: {mime}",
                    status=400
                )
        except Exception:
            pass  # Fallback: allow if magic fails

        # Save to draft (user-scoped)
        draft, created = AssistantDraft.objects.get_or_create(user=user)

        # Delete old file
        if draft.file:
            try:
                draft.file.delete(save=False)
            except Exception:
                pass

        draft.file = file_obj
        draft.file_name = file_obj.name
        draft.save()

        # Estimate pages
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

        suggestions = ["Confirm", f"Order {estimated_pages}", "Cancel"]

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
            return format_response("🗑️ File removed from draft.")
        except AssistantDraft.DoesNotExist:
            return format_response("No draft file to delete.", status=404)
