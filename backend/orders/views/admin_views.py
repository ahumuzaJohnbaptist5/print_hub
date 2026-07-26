# orders/views/admin_views.py
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags
from django.http import HttpResponseForbidden

from orders.models import Order, SystemSettings, Announcement, Station
from orders.utils import apply_order_status_change
from .helpers import _user_role, _build_order_queryset, _order_summary_counts

User = get_user_model()
logger = logging.getLogger(__name__)

@login_required
@user_passes_test(lambda u: _user_role(u) == 'admin')
@transaction.atomic
def admin_dashboard_view(request):
    if _user_role(request.user) != 'admin':
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_agent':
            agent_id = request.POST.get('agent_id')
            station_id = request.POST.get('agent_station_id') or None
            if not agent_id or not agent_id.isdigit():
                messages.error(request, 'Invalid agent ID.')
                return redirect('admin_dashboard')
            agent = get_object_or_404(User, id=int(agent_id), role='agent')
            if station_id and station_id.isdigit():
                station_id = int(station_id)
            else:
                station_id = None
            if hasattr(agent, 'station'):
                agent.station_id = station_id
                agent.save(update_fields=['station'])
                messages.success(request, f'Station updated for agent {agent.username}.')
            else:
                messages.error(request, 'Agent model does not have station field.')
            return redirect('admin_dashboard')
            
        if action == 'bulk_status':
            new_status = request.POST.get('bulk_status')
            order_ids = request.POST.getlist('order_ids')
            valid = ['printing', 'in_transit', 'ready', 'collected', 'cancelled']
            if new_status in valid and order_ids:
                valid_order_ids = [oid for oid in order_ids if oid.isdigit()]
                updated_count = 0
                for oid in valid_order_ids:
                    try:
                        order = Order.objects.select_for_update().get(id=int(oid))
                        if apply_order_status_change(order, new_status, request.user):
                            updated_count += 1
                    except Order.DoesNotExist:
                        continue
                    except Exception as e:
                        logger.error(f"Error updating order {oid}: {e}")
                messages.success(request, f'Updated {updated_count} order(s) to {new_status}.')
            return redirect(request.get_full_path() or 'admin_dashboard')
            
        if action == 'update_announcement':
            if request.POST.get('delete_announcement'):
                Announcement.objects.filter(is_active=True).update(is_active=False)
                messages.success(request, 'Announcement removed.')
            else:
                title = strip_tags(request.POST.get('announcement_title', 'Announcement'))
                message_text = strip_tags(request.POST.get('announcement_message', ''))
                color = request.POST.get('announcement_color', 'bg-blue-600')
                is_active = request.POST.get('announcement_active') == 'on'
                show_home = request.POST.get('announcement_home') == 'on'
                allowed_colors = ['bg-blue-600', 'bg-red-600', 'bg-green-600', 'bg-yellow-600', 'bg-purple-600']
                if color not in allowed_colors:
                    color = 'bg-blue-600'
                if message_text:
                    Announcement.objects.update_or_create(
                        is_active=True,
                        defaults={
                            'title': title,
                            'message': message_text,
                            'background_color': color,
                            'is_active': is_active,
                            'show_on_home': show_home,
                        }
                    )
                    messages.success(request, 'Announcement updated!')
                else:
                    messages.error(request, 'Message cannot be empty.')
            return redirect('admin_dashboard')

    orders_qs = _build_order_queryset(request)
    summary = _order_summary_counts()
    overdue_count = Order.objects.filter(
        status__in=['paid', 'printing', 'in_transit', 'ready'],
    ).count()
    summary['overdue'] = overdue_count
    
    paginator = Paginator(orders_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    agents = User.objects.filter(role='agent').select_related('station')
    stations = Station.objects.all()
    system_settings = SystemSettings.load()
    
    active_filters = []
    filter_keys = {
        'status': 'Status',
        'station': 'Station',
        'date': 'Date',
        'search': 'Search',
        'order_type': 'Type'
    }
    for key, label in filter_keys.items():
        val = request.GET.get(key, '').strip()
        if val:
            safe_val = strip_tags(val)
            active_filters.append({'key': key, 'value': safe_val, 'label': label})
            
    return render(request, 'orders/admin_dashboard.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'summary': summary,
        'agents': agents,
        'stations': stations,
        'status_choices': Order.STATUS_CHOICES,
        'order_type_choices': Order.ORDER_TYPE_CHOICES,
        'active_filters': active_filters,
        'filter_status': request.GET.get('status', ''),
        'filter_station': request.GET.get('station', ''),
        'filter_date': request.GET.get('date', ''),
        'filter_search': request.GET.get('search', ''),
        'filter_order_type': request.GET.get('order_type', ''),
        'total_filtered': orders_qs.count(),
        'system_settings': system_settings,
        'active_announcement': Announcement.get_active(),
    })

@login_required
def toggle_system_pause_view(request):
    if _user_role(request.user) != 'admin':
        return HttpResponseForbidden("Admin access only.")
    sys_settings = SystemSettings.load()
    if request.method == 'POST':
        action = request.POST.get('action')
        csrf_token = request.POST.get('csrfmiddlewaretoken')
        if not csrf_token:
            return HttpResponseForbidden("Invalid request.")
        if action == 'pause':
            if not sys_settings.is_paused:
                reason = strip_tags(request.POST.get('reason', 'Unforeseen circumstances'))
                sys_settings.is_paused = True
                sys_settings.pause_reason = reason[:200]
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
