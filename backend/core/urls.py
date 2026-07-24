from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.conf import settings
from orders import views as orders_views
from orders.views import (
    home_view,
    upload_view,
    order_track_view,
    dashboard_view,
    admin_dashboard_view,
    agent_dashboard_view,
    update_order_status_view,
    order_receipt_view,
    download_order_file_view,
    live_board_view,
    live_board_api_view,
    live_board_preview_image,
    all_links_view,
    toggle_system_pause_view,
    cancel_order_view,
    my_orders_view,
    payment_page_view,
)

@never_cache
def service_worker(request):
    with open(settings.BASE_DIR / 'sw.js', 'r') as f:
        return HttpResponse(f.read(), content_type='application/javascript')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('accounts.urls')),
    
    path('', home_view, name='home'),
    path('upload/', upload_view, name='upload'),
    path('track/', order_track_view, name='track_order'),
    path('dashboard/', login_required(dashboard_view), name='dashboard'),
    path('admin-dashboard/', login_required(admin_dashboard_view), name='admin_dashboard'),
    path('toggle-pause/', toggle_system_pause_view, name='toggle_system_pause'),
    path('all-links/', all_links_view, name='all_links'),
    
    path('orders/agent/', login_required(agent_dashboard_view), name='agent_dashboard'),
    path('orders/<int:order_id>/update/', login_required(update_order_status_view), name='update_order_status'),
    path('orders/<int:order_id>/receipt/', login_required(order_receipt_view), name='order_receipt'),
    path('orders/<int:order_id>/file/', login_required(download_order_file_view), name='download_order_file'),
    path('orders/<int:order_id>/cancel/', login_required(cancel_order_view), name='cancel_order'),
    path('orders/<int:order_id>/payment/', login_required(payment_page_view), name='payment_page'),
    path('my-orders/', login_required(my_orders_view), name='my_orders'),
    
    path('live-board/', login_required(live_board_view), name='live_board'),
    path('orders/live-board/api/', live_board_api_view, name='live_board_api'),
    path('orders/live-board-preview.png', live_board_preview_image, name='live_board_preview'),
    
    path('orders/api/analyze-passport/', login_required(orders_views.api_analyze_passport), name='analyze_passport'),
    path('orders/api/process-passport/', login_required(orders_views.api_process_passport), name='process_passport'),
    path('orders/api/process-scan/', login_required(orders_views.api_process_scan), name='process_scan'),
    path('orders/api/validate-discount/', login_required(orders_views.validate_discount_code), name='validate_discount_code'),
    
    path('payments/', include('payments.urls')),
    path('finances/', include('finances.urls')),
    path('notifications/', include('notifications.urls')),
    path('whatsapp/', include('whatsapp_bot.urls')),
    
    path('sw.js', service_worker),
]
