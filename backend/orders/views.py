import os
import mimetypes
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse

from stations.models import Station

from .models import Order, SystemSettings
from .utils import apply_order_status_change, send_delayed_order_email

User = get_user_model()

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def _user_role(user):
    return getattr(user, 'role', None)


def _is_staff_role(user):
    return _user_role(user) in ('admin', 'agent')


def validate_upload_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        return f'Invalid file type. Allowed: {allowed}'
    if file.size > MAX_UPLOAD_SIZE:
        return 'File size exceeds 10MB limit.'
    return None


def _can_view_order(user, order):
    if _user_role(user) in ('admin', 'agent'):
        return True
    return order.client == user


@login_required
def dashboard_view(request):
    orders = Order.objects.filter(client=request.user).order_by('-created_at')
    return render(request, 'orders/dashboard.html', {'orders': orders})


def upload_view(request):
    stations = Station.objects.all()
    upload_error = None

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in or create an account to complete your upload.')
            return redirect('/auth/login/?next=/upload/')

        file = request.FILES.get('file')
        page_count = request.POST.get('page_count', 1)
        is_color = request.POST.get('is_color', 'False') == 'True'
        is_double_sided = request.POST.get('is_double_sided') == 'on'
        station_id = request.POST.get('station')

        if not file:
            upload_error = 'Please select a file.'
        else:
            upload_error = validate_upload_file(file)

        if upload_error:
            return render(request, 'orders/upload.html', {
                'stations': stations,
                'upload_error': upload_error,
            })

        station = Station.objects.filter(id=station_id).first() if station_id else None

        try:
            order = Order.objects.create(
                client=request.user,
                station=station,
                file=file,
                file_name=file.name,
                page_count=int(page_count),
                is_color=is_color,
                is_double_sided=is_double_sided,
                status='pending',
            )
            messages.success(
                request,
                f'Order submitted! Total: {order.total_price:,} UGX',
            )
            return redirect('dashboard')
        except Exception as e:
            upload_error = f'Error creating order: {str(e)}'
            return render(request, 'orders/upload.html', {
                'stations': stations,
                'upload_error': upload_error,
            })

    return render(request, 'orders/upload.html', {'stations': stations})


@login_required
def order_receipt_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if not _can_view_order(request.user, order):
        return HttpResponseForbidden('You do not have permission to view this receipt.')

    estimated_ready = order.estimated_ready_at()

    return render(request, 'orders/receipt.html', {
        'order': order,
        'estimated_ready': estimated_ready,
    })


def _build_order_queryset(request):
    qs = Order.objects.select_related('client', 'station').order_by('-created_at')

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    station_id = request.GET.get('station', '').strip()
    if station_id:
        qs = qs.filter(station_id=station_id)

    date_filter = request.GET.get('date', '').strip()
    now = timezone.now()
    if date_filter == 'today':
        qs = qs.filter(created_at__date=now.date())
    elif date_filter == 'week':
        qs = qs.filter(created_at__gte=now - timedelta(days=7))
    elif date_filter == 'month':
        qs = qs.filter(created_at__gte=now - timedelta(days=30))

    search = request.GET.get('search', '').strip()
    if search:
        if search.isdigit():
            qs = qs.filter(Q(id=int(search)) | Q(client__email__icontains=search))
        else:
            qs = qs.filter(
                Q(client__email__icontains=search)
                | Q(client__username__icontains=search)
                | Q(file_name__icontains=search)
            )

    return qs


def _order_summary_counts():
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        'total': Order.objects.count(),
        'pending': Order.objects.filter(status='pending').count(),
        'printing': Order.objects.filter(status='printing').count(),
        'ready': Order.objects.filter(status='ready').count(),
        'collected_today': Order.objects.filter(
            status='collected', collected_at__gte=today_start
        ).count(),
    }


@login_required
def admin_dashboard_view(request):
    if _user_role(request.user) != 'admin':
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'assign_agent':
            agent_id = request.POST.get('agent_id')
            station_id = request.POST.get('agent_station_id') or None
            agent = get_object_or_404(User, id=agent_id, role='agent')
            agent.station_id = station_id
            agent.save(update_fields=['station'])
            messages.success(request, f'Station updated for agent {agent.username}.')
            return redirect('admin_dashboard')

        if action == 'bulk_status':
            new_status = request.POST.get('bulk_status')
            order_ids = request.POST.getlist('order_ids')
            valid = ['printing', 'ready', 'collected']
            if new_status in valid and order_ids:
                for oid in order_ids:
                    order = Order.objects.filter(id=oid).first()
                    if order:
                        apply_order_status_change(order, new_status)
                messages.success(request, f'Updated {len(order_ids)} order(s) to {new_status}.')
            return redirect(request.get_full_path() or 'admin_dashboard')

    orders_qs = _build_order_queryset(request)
    summary = _order_summary_counts()
    paginator = Paginator(orders_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    agents = User.objects.filter(role='agent').select_related('station')
    stations = Station.objects.all()
    
    # NEW: Load system settings for the template
    system_settings = SystemSettings.load()

    active_filters = []
    for key, label in [
        ('status', 'Status'),
        ('station', 'Station'),
        ('date', 'Date'),
        ('search', 'Search'),
    ]:
        val = request.GET.get(key, '').strip()
        if val:
            active_filters.append({'key': key, 'value': val, 'label': label})

    return render(request, 'orders/admin_dashboard.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'summary': summary,
        'agents': agents,
        'stations': stations,
        'status_choices': Order.STATUS_CHOICES,
        'active_filters': active_filters,
        'filter_status': request.GET.get('status', ''),
        'filter_station': request.GET.get('station', ''),
        'filter_date': request.GET.get('date', ''),
        'filter_search': request.GET.get('search', ''),
        'total_filtered': orders_qs.count(),
        'system_settings': system_settings,  # <--- PASS TO TEMPLATE
    })


@login_required
def toggle_system_pause_view(request):
    """Allows Admin to pause or resume all order timers."""
    if _user_role(request.user) != 'admin':
        return HttpResponseForbidden("Admin access only.")
        
    sys_settings = SystemSettings.load()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'pause':
            if not sys_settings.is_paused:
                sys_settings.is_paused = True
                sys_settings.pause_reason = request.POST.get('reason', 'Unforeseen circumstances')
                sys_settings.pause_started_at = timezone.now()
                sys_settings.save()
                messages.success(request, "System timers PAUSED successfully.")
                
        elif action == 'resume':
            if sys_settings.is_paused:
                if sys_settings.pause_started_at:
                    sys_settings.total_paused_seconds += (timezone.now() - sys_settings.pause_started_at).total_seconds()
                sys_settings.is_paused = False
                sys_settings.pause_started_at = None
                sys_settings.save()
                messages.success(request, "System timers RESUMED successfully.")
                
    return redirect('admin_dashboard')


def is_agent_or_admin(user):
    """Helper to check if user is agent or admin"""
    return user.is_authenticated and (user.role == 'agent' or user.is_staff)


@login_required
@user_passes_test(is_agent_or_admin, login_url='login')
def agent_dashboard_view(request):
    """Agent dashboard with status updates, delay, cancel, and postpone actions"""
    if request.user.role == 'agent' and request.user.station:
        orders = Order.objects.filter(station=request.user.station).order_by('-created_at')
    else:
        orders = Order.objects.all().order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        
        if action == 'update_status':
            new_status = request.POST.get('status')
            order = get_object_or_404(Order, id=order_id)
            
            if apply_order_status_change(order, new_status, request.user):
                messages.success(request, f'Order #{order.id} updated to {order.get_status_display()}.')
            else:
                messages.info(request, f'Order #{order.id} status unchanged.')
        
        elif action == 'notify_delay':
            order = get_object_or_404(Order, id=order_id)
            reason = request.POST.get('delay_reason', '').strip()
            
            send_delayed_order_email(order, reason)
            messages.success(request, f'Delay notification sent for Order #{order.id}.')
            
        # NEW: Cancel Order Action
        elif action == 'cancel_order':
            order = get_object_or_404(Order, id=order_id)
            if order.status not in ['collected', 'cancelled']:
                order.status = 'cancelled'
                order.save(update_fields=['status'])
                messages.success(request, f'Order #{order.id} has been CANCELLED.')
            else:
                messages.error(request, 'Cannot cancel this order.')
                
        # NEW: Postpone Order Action
        elif action == 'postpone_order':
            order = get_object_or_404(Order, id=order_id)
            if order.status not in ['collected', 'cancelled']:
                try:
                    extra_minutes = int(request.POST.get('extra_minutes', 30))
                    if extra_minutes > 0:
                        order.postponed_minutes += extra_minutes
                        order.save(update_fields=['postponed_minutes'])
                        messages.success(request, f'Order #{order.id} postponed by {extra_minutes} minutes.')
                    else:
                        messages.error(request, 'Please enter a valid number of minutes.')
                except ValueError:
                    messages.error(request, 'Invalid number of minutes.')
            else:
                messages.error(request, 'Cannot postpone this order.')
        
        return redirect('agent_dashboard')

    return render(request, 'orders/agent_dashboard.html', {'orders': orders})


@login_required
def update_order_status_view(request, order_id):
    if not _is_staff_role(request.user):
        return HttpResponseForbidden('You do not have permission to update order status.')

    order = get_object_or_404(Order, id=order_id)

    if _user_role(request.user) == 'agent':
        if not request.user.station or order.station_id != request.user.station_id:
            return HttpResponseForbidden('You can only update orders for your assigned station.')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = ['pending', 'paid', 'printing', 'ready', 'collected', 'cancelled']
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status.')
            return redirect('dashboard')

        apply_order_status_change(order, new_status)
        messages.success(request, f'Order status updated to {new_status}.')

        if _user_role(request.user) == 'admin':
            return redirect('admin_dashboard')
        if _user_role(request.user) == 'agent':
            return redirect('agent_dashboard')
        return redirect('dashboard')

    return render(request, 'orders/update_status.html', {'order': order})


@login_required
def download_order_file_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    user = request.user

    if _user_role(user) not in ('admin', 'agent') and order.client != user:
        return HttpResponseForbidden('You do not have permission to download this file.')

    if not order.file:
        messages.error(request, 'File not found.')
        return redirect('dashboard')

    content_type, _ = mimetypes.guess_type(order.file_name)
    response = FileResponse(
        order.file.open('rb'),
        content_type=content_type or 'application/octet-stream',
    )
    response['Content-Disposition'] = f'attachment; filename="{order.file_name}"'
    return response


def _get_tracked_orders(order_id=None, email=None):
    if order_id:
        return Order.objects.filter(id=order_id).select_related('station', 'client')
    if email:
        return Order.objects.filter(
            client__email__iexact=email
        ).select_related('station', 'client').order_by('-created_at')
    return None


def order_track_view(request):
    orders = None
    lookup_error = None
    order_id = request.GET.get('order_id', '').strip() or request.POST.get('order_id', '').strip()
    email = request.GET.get('email', '').strip() or request.POST.get('email', '').strip()

    if order_id or email:
        if order_id:
            orders = _get_tracked_orders(order_id=order_id)
            if not orders.exists():
                lookup_error = 'No order found with that order ID.'
                orders = None
        elif email:
            orders = _get_tracked_orders(email=email)
            if not orders.exists():
                lookup_error = 'No orders found for that email address.'
                orders = None

    timeline_steps = [
        ('submitted', 'Submitted', 'created_at'),
        ('paid', 'Paid', 'paid_at'),
        ('printing', 'Printing', 'printing_at'),
        ('ready', 'Ready for Pickup', 'ready_at'),
        ('collected', 'Collected', 'collected_at'),
    ]

    order_timelines = []
    if orders:
        status_step_map = {'pending': 0, 'paid': 1, 'printing': 2, 'ready': 3, 'collected': 4}
        for order in orders:
            current_step = status_step_map.get(order.status, 0)
            steps = []
            for i, (key, label, ts_field) in enumerate(timeline_steps):
                ts = getattr(order, ts_field, None)
                if i < current_step:
                    state = 'completed'
                elif i == current_step:
                    state = 'current'
                else:
                    state = 'future'
                steps.append({
                    'key': key,
                    'label': label,
                    'timestamp': ts,
                    'state': state,
                })
            order_timelines.append({
                'order': order,
                'steps': steps,
                'estimated_ready': order.estimated_ready_at(),
                'progress_width': int(current_step / (len(timeline_steps) - 1) * 100) if len(timeline_steps) > 1 else 0,
            })

    return render(request, 'orders/track.html', {
        'orders': orders,
        'order_timelines': order_timelines,
        'lookup_error': lookup_error,
        'query_order_id': order_id,
        'query_email': email,
    })


# ==========================================
# --- LIVE BOARD & HOMEPAGE VIEWS ---
# ==========================================

def home_view(request):
    """Renders the new homepage with the live departures board."""
    return render(request, 'home.html')

@login_required
def live_board_view(request):
    """Renders the real-time airport-style flight board HTML page."""
    return render(request, 'orders/live_board.html')

def live_board_api_view(request):
    """API endpoint for JavaScript to poll real-time updates."""
    # Include 'cancelled' so they show up on the board like cancelled flights
    active_statuses = ['paid', 'printing', 'ready', 'cancelled'] 
    orders = Order.objects.filter(status__in=active_statuses).select_related('station', 'client')
    
    board_data = []
    for order in orders:
        priority = order.priority_info
        board_data.append({
            'id': order.id,
            'client': order.client.username,
            'station': order.station.name if order.station else 'Unassigned',
            'status': order.get_status_display(),
            'status_raw': order.status,
            'time_left': priority['time_display'],
            'remaining_seconds': priority['remaining_seconds'],
            'priority': priority['display'],
            'priority_level': priority['level'],
        })
        
    # Sort so most urgent orders are at the top, but cancelled orders go to the bottom
    board_data.sort(key=lambda x: (x['status_raw'] == 'cancelled', x['remaining_seconds']))
    
    # NEW: Get system pause status
    sys_settings = SystemSettings.load()
    
    return JsonResponse({
        'orders': board_data,
        'system_paused': sys_settings.is_paused,
        'pause_reason': sys_settings.pause_reason
    })


# ==========================================
# --- ALL LINKS INDEX VIEW ---
# ==========================================

def all_links_view(request):
    """A cheat-sheet page that lists all available URLs in the app."""
    links_data = [
        ('home', 'Home (Live Board)', 'Live departures board'),
        ('dashboard', 'Client Dashboard', 'View your past orders'),
        ('upload', 'Upload / Place Order', 'Upload files for printing'),
        ('track_order', 'Track Order', 'Track order status by ID or email'),
        ('admin_dashboard', 'Admin Dashboard', 'Admin overview and management'),
        ('agent_dashboard', 'Agent Dashboard', 'Station agent dashboard'),
        ('live_board', 'Live Board (Standalone)', 'Full screen live board'),
        ('login', 'Login', 'User login page'),
        ('register', 'Register', 'User registration page'),
    ]
    
    links = []
    for url_name, name, desc in links_data:
        try:
            url = reverse(url_name)
        except Exception:
            url = '#'
        links.append({'name': name, 'url': url, 'desc': desc})
        
    links.append({'name': 'Django Admin', 'url': '/admin/', 'desc': 'Built-in database admin panel'})
    
    return render(request, 'all_links.html', {'links': links})
