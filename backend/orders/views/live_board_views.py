# orders/views/live_board_views.py
import io
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_control, cache_page
from PIL import Image, ImageDraw, ImageFont

from orders.models import Order, SystemSettings

@login_required
def live_board_view(request):
    return render(request, 'orders/live_board.html')

@cache_page(60 * 1)
def live_board_api_view(request):
    active_statuses = ['paid', 'printing', 'in_transit', 'ready']
    orders = Order.objects.filter(
        status__in=active_statuses
    ).select_related('station', 'client')
    cancelled_orders = Order.objects.filter(
        status='cancelled',
        cancelled_at__gte=timezone.now() - timedelta(minutes=30)
    ).select_related('station', 'client')
    all_orders = list(orders) + list(cancelled_orders)
    sys_settings = SystemSettings.load()
    board_data = []
    for order in all_orders:
        priority = order.priority_info
        board_data.append({
            'id': order.id,
            'client': order.client.username,
            'station': order.station.name if order.station else 'Unassigned',
            'file_name': order.file_name,
            'status': order.get_status_display(),
            'status_raw': order.status,
            'time_left': priority['time_display'],
            'remaining_seconds': priority['remaining_seconds'],
            'priority': priority['display'],
            'priority_level': priority['level'],
            'is_overdue': priority['is_overdue'],
            'page_count': order.page_count,
            'is_color': order.is_color,
            'binding': order.get_binding_display(),
            'order_type': order.get_order_type_display(),
            'paper_size': order.paper_size,
            'copies': order.copies,
        })
    board_data.sort(key=lambda x: (x['status_raw'] == 'cancelled', x['remaining_seconds']))
    response = JsonResponse({
        'orders': board_data,
        'system_paused': sys_settings.is_paused,
        'pause_reason': sys_settings.pause_reason,
        'total_active': len(orders),
        'total_cancelled': len(cancelled_orders),
        'last_updated': timezone.now().isoformat(),
    })
    response["Access-Control-Allow-Origin"] = "*"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    return response

@cache_control(max_age=60)
def live_board_preview_image(request):
    active_statuses = ['paid', 'printing', 'in_transit', 'ready']
    orders = Order.objects.filter(
        status__in=active_statuses
    ).select_related('station', 'client').order_by('id')
    total_active = orders.count()
    ready_count = orders.filter(status='ready').count()
    printing_count = orders.filter(status='printing').count()
    cancelled_count = Order.objects.filter(
        status='cancelled',
        cancelled_at__gte=timezone.now() - timedelta(minutes=30)
    ).count()
    
    img = Image.new('RGB', (1200, 630), color='#0f172a')
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 46)
        font_subtitle = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
        font_body = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
        font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    draw.text((50, 50), "PrintHub Live Board", fill='#e2e8f0', font=font_title)
    draw.text((50, 110), "Kabale University Printing Service", fill='#94a3b8', font=font_subtitle)
    
    stats = [
        ("Active", total_active, '#22c55e'),
        ("Ready", ready_count, '#3b82f6'),
        ("Printing", printing_count, '#a855f7'),
        ("Total Today", total_active + cancelled_count, '#f59e0b'),
    ]
    x = 50
    for label, value, color in stats:
        draw.text((x, 180), label, fill='#94a3b8', font=font_small)
        draw.text((x, 210), str(value), fill=color, font=font_body)
        x += 250
        
    draw.rectangle([50, 280, 1150, 320], fill='#1e293b')
    headers = [
        ("Order", 70), ("Client", 200), ("Station", 400),
        ("Status", 600), ("Time Left", 800), ("Priority", 1000)
    ]
    for text, x_pos in headers:
        draw.text((x_pos, 285), text, fill='#94a3b8', font=font_small)
        
    y = 330
    for order in orders[:4]:
        priority = order.priority_info
        items = [
            (70, f"#{order.id}"),
            (200, order.client.username[:12]),
            (400, order.station.name[:15] if order.station else '—'),
            (600, order.get_status_display()),
            (800, priority['time_display']),
            (1000, priority['display']),
        ]
        for x_pos, text in items:
            draw.text((x_pos, y), text, fill='#e2e8f0', font=font_small)
        y += 55
        
    draw.text((50, 570), "Scan to track your order  |  printlink.pythonanywhere.com", fill='#64748b', font=font_small)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return HttpResponse(buffer, content_type='image/png')
