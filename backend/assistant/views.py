import re
from decimal import Decimal
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q, Sum, Count, F

from orders.models import Order, SystemSettings, Announcement
from stations.models import Station
from payments.models import Payment
from finances.models import DiscountCode, PaperInventory, AgentEarning, Expense
from .models import AssistantDraft

# ══════════════════════════════════════════════════════════════
# HELPERS & FORMATTING
# ══════════════════════════════════════════════════════════════

def format_response(text, data=None, response_type="text", status=200):
    """Standard JSON response for the frontend chat widget."""
    return Response({
        "type": response_type,
        "text": text,
        "data": data or {}
    }, status=status)

def is_admin(user):
    """🔒 SECURITY FIX: Replaces easily spoofed phone number checks."""
    return user.is_staff or getattr(user, 'role', '') in ['admin', 'superadmin']

def is_agent(user):
    return getattr(user, 'role', '') == 'agent'

def get_status_emoji(status):
    emoji_map = {
        'pending': '⏳', 'paid': '💳', 'printing': '🖨️',
        'in_transit': '🚚', 'ready': '✅', 'collected': '📦', 'cancelled': '❌'
    }
    return emoji_map.get(status, '📋')

# ══════════════════════════════════════════════════════════════
# MAIN CHAT ENDPOINT
# ══════════════════════════════════════════════════════════════

class AssistantChatView(APIView):
    """
    Main router for the web bot.
    Frontend sends POST {"message": "Track 123"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()
        user = request.user
        
        if not message:
            return format_response("Please type a message.", status=400)

        parts = message.split()
        command = parts[0].lower() if parts else ""
        text_lower = message.lower()

        # ═══ ORDER CREATION ═══
        if command == 'order' and len(parts) >= 2:
            return self.handle_order_intent(user, parts[1:])

        if text_lower in ['confirm', 'yes', 'done']:
            return self.confirm_draft_order(user)

        if text_lower in ['cancel', 'cancel order', 'discard']:
            return self.cancel_draft(user)

        # ═══ UNIVERSAL COMMANDS ═══
        if command in ['hi', 'hello', 'hey', 'start', 'menu']:
            return self.cmd_welcome(user)

        if command in ['help', 'commands']:
            return self.cmd_help(user)

        if command in ['track', 'status'] and len(parts) >= 2:
            return self.cmd_track(user, ' '.join(parts[1:]))

        if text_lower in ['my orders', 'myorders', 'orders']:
            return self.cmd_my_orders(user)

        if text_lower in ['pricing', 'price', 'prices', 'cost', 'rates']:
            return self.cmd_pricing()
            
        if text_lower in ['stations', 'location', 'locations', 'where']:
            return self.cmd_stations()

        # ═══ ADMIN COMMANDS ═══
        if is_admin(user):
            if text_lower in ['revenue', 'sales']: return self.cmd_admin_revenue()
            if text_lower in ['pause']: return self.cmd_admin_pause(user, ' '.join(parts[1:]))
            if text_lower in ['resume']: return self.cmd_admin_resume()

        # ═══ FALLBACK ═══
        return format_response(
            "I didn't understand.\n\n"
            "📝 *Order <pages>* - Create order\n"
            "📋 *Track <id>* - Check order\n"
            "💰 *Pricing* - See rates\n"
            "Type *Help* for all commands."
        )

    # --- Intent Handlers ---

    def handle_order_intent(self, user, args):
        page_count = None
        is_color = False
        is_double_sided = False
        binding = 'none'
        delivery_type = 'pickup'

        for arg in args:
            arg_lower = arg.lower()
            if arg.isdigit(): page_count = int(arg)
            elif arg_lower in ['color', 'colored']: is_color = True
            elif arg_lower in ['b&w', 'bw', 'black']: is_color = False
            elif arg_lower in ['double', 'duplex']: is_double_sided = True
            elif arg_lower in ['spiral']: binding = 'spiral'
            elif arg_lower in ['staple']: binding = 'staple'
            elif arg_lower in ['delivery']: delivery_type = 'delivery'

        if not page_count or page_count < 1:
            return format_response("📝 *Create an Order*\n\nExample: *Order 45 Color Spiral Pickup*")

        # Calculate price (Assuming Order.compute_price exists as in your old code)
        delivery_fee = 0 
        total, effective_pages, price_per_page = Order.compute_price(
            page_count, is_color, is_double_sided, binding, delivery_fee
        )

        # 🔒 SECURITY FIX: Save to Database instead of RAM
        draft, _ = AssistantDraft.objects.update_or_create(
            user=user,
            defaults={
                'page_count': page_count,
                'is_color': is_color,
                'is_double_sided': is_double_sided,
                'binding': binding,
                'delivery_type': delivery_type,
                'file': None, # Reset file if starting new order
                'file_name': None
            }
        )

        msg = f"📋 *Order Summary*\n\n"
        msg += f"📄 Pages: *{page_count}*\n"
        msg += f"🎨 Type: *{'Color' if is_color else 'B&W'}*\n"
        msg += f"💵 *Total: {total:,.0f} UGX*\n\n"
        msg += "📎 *Next:* Upload your file using the attachment button, then type *Confirm*."
        
        return format_response(msg, data={"draft_id": draft.id, "total": total}, response_type="draft_summary")

    def confirm_draft_order(self, user):
        try:
            draft = AssistantDraft.objects.get(user=user)
        except AssistantDraft.DoesNotExist:
            return format_response("❌ No pending order. Send *Order <pages>* to start.")

        if not draft.page_count:
            return format_response("❌ Draft is incomplete.")

        # Create the actual order
        order = Order.objects.create(
            client=user,
            station_id=draft.station_id,
            file=draft.file,
            file_name=draft.file_name or f"Web Order - {draft.page_count} pages",
            page_count=draft.page_count,
            is_color=draft.is_color,
            is_double_sided=draft.is_double_sided,
            binding=draft.binding,
            delivery_type=draft.delivery_type,
            status='pending',
        )

        # Clean up draft
        draft.delete()

        msg = f"✅ *Order #{order.id} Created!*\n\n"
        msg += f"💰 Total: *{order.total_price:,.0f} UGX*\n\n"
        msg += f"💳 To pay, go to your Orders page or type *Pay {order.id}*."
        
        return format_response(msg, data={"order_id": order.id}, response_type="order_success")

    def cancel_draft(self, user):
        deleted, _ = AssistantDraft.objects.filter(user=user).delete()
        if deleted:
            return format_response("❌ Order cancelled.")
        return format_response("No pending order to cancel.")

    def cmd_welcome(self, user):
        announcement = Announcement.get_active()
        ann_text = f"\n📢 {announcement.message}\n" if announcement else ""
        msg = f"*Welcome to PrintHub!* 🖨️{ann_text}\nWhat would you like to do?"
        return format_response(msg, response_type="welcome", data={"quick_replies": ["Order Now", "Track Order", "Pricing"]})

    def cmd_track(self, user, query):
        query = query.strip()
        if query.isdigit():
            qs = Order.objects.select_related('station', 'client', 'delivery_zone')
            
            # 🔒 BOLA/IDOR FIX: Non-admins can ONLY track their own orders
            if not is_admin(user):
                qs = qs.filter(client=user)
                
            try:
                order = qs.get(id=int(query))
                msg = f"📋 *Order #{order.id}*\n"
                msg += f"📊 Status: {get_status_emoji(order.status)} {order.get_status_display()}\n"
                msg += f"💰 Total: {order.total_price:,.0f} UGX\n"
                return format_response(msg, data={"order_id": order.id, "status": order.status}, response_type="order_details")
            except Order.DoesNotExist:
                # 🔒 SECURITY FIX: Generic message prevents attackers from guessing valid Order IDs
                return format_response("❌ Order not found or you don't have permission to view it.")
                
        return format_response("❌ Use *Track 123*")

    def cmd_my_orders(self, user):
        orders = Order.objects.filter(client=user).order_by('-created_at')[:5]
        if not orders.exists():
            return format_response("📭 No orders yet. Send *Order <pages>* to start!")
            
        msg = f"📚 *Your Recent Orders*\n\n"
        for order in orders:
            msg += f"#{order.id} - {get_status_emoji(order.status)} {order.get_status_display()} | {order.total_price:,.0f} UGX\n"
        return format_response(msg, response_type="order_list")

    def cmd_pricing(self):
        msg = "💰 *PrintHub Pricing*\n\n• B&W: *200 UGX*/page\n• Color: *300 UGX*/page\n• Spiral Binding: *1,000 UGX*"
        return format_response(msg)

    def cmd_stations(self):
        stations = Station.objects.filter(is_active=True)
        msg = "📍 *PrintHub Stations*\n\n"
        for s in stations:
            msg += f"• *{s.name}*\n"
        return format_response(msg)
        
    def cmd_help(self, user):
        msg = "📋 *PrintHub Commands*\n\n*Order <pages>*\n*Track <id>*\n*My orders*\n*Pricing*"
        if is_admin(user): msg += "\n\n🔐 *Admin:* Revenue, Pause, Resume"
        return format_response(msg)

    # --- Admin Commands ---
    def cmd_admin_revenue(self):
        today_rev = Order.objects.filter(created_at__date=timezone.now().date()).aggregate(total=Sum('total_price'))
        return format_response(f"📊 *Today's Revenue:* {today_rev['total'] or 0:,.0f} UGX")

    def cmd_admin_pause(self, user, reason):
        s = SystemSettings.load()
        s.is_paused = True
        s.pause_reason = reason or "Paused via Web Assistant"
        s.save()
        return format_response("⏸️ System PAUSED.")

    def cmd_admin_resume(self):
        s = SystemSettings.load()
        s.is_paused = False
        s.save()
        return format_response("▶️ System RESUMED.")


# ══════════════════════════════════════════════════════════════
# FILE UPLOAD ENDPOINT
# ══════════════════════════════════════════════════════════════

class AssistantUploadView(APIView):
    """
    🔒 SSRF FIX: Replaces requests.get(media_url). 
    The frontend uploads the file directly via multipart/form-data.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return format_response("❌ No file provided.", status=400)
            
        # Basic file validation
        if file_obj.size > 10 * 1024 * 1024: # 10MB limit
            return format_response("❌ File too large. Max 10MB.", status=400)

        draft, _ = AssistantDraft.objects.get_or_create(user=user)
        draft.file = file_obj
        draft.file_name = file_obj.name
        draft.save()
        
        msg = f"✅ *File Received!*\n\n📄 {file_obj.name}\n\nType *Confirm* to place your order."
        return format_response(msg, response_type="file_success")
