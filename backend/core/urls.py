from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.conf import settings
from orders.views import live_board_preview_image   # <-- add this import at the top
from orders.views import (
    home_view,
    dashboard_view,
    upload_view,
    admin_dashboard_view,
    update_order_status_view,
    agent_dashboard_view,
    order_receipt_view,
    download_order_file_view,
    order_track_view,
    live_board_view,
    live_board_api_view,
    all_links_view,
    toggle_system_pause_view,
)

@never_cache
def service_worker(request):
    with open(settings.BASE_DIR / 'sw.js', 'r') as f:
        return HttpResponse(f.read(), content_type='application/javascript')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('auth/', include('accounts.urls')),
    path('dashboard/', login_required(dashboard_view), name='dashboard'),
    path('upload/', upload_view, name='upload'),
    path('track/', order_track_view, name='track_order'),
    path('admin-dashboard/', login_required(admin_dashboard_view), name='admin_dashboard'),
    path('orders/agent/', login_required(agent_dashboard_view), name='agent_dashboard'),
    path('orders/<int:order_id>/update/', login_required(update_order_status_view), name='update_order_status'),
    path('orders/<int:order_id>/receipt/', login_required(order_receipt_view), name='order_receipt'),
    path('orders/<int:order_id>/file/', login_required(download_order_file_view), name='download_order_file'),
    path('toggle-pause/', toggle_system_pause_view, name='toggle_system_pause'),
    path('live-board/', login_required(live_board_view), name='live_board'),
    path('orders/live-board/api/', live_board_api_view, name='live_board_api'),
    path('all-links/', all_links_view, name='all_links'),
    path('payments/', include('payments.urls')),
    # core/urls.py (or orders/urls.py if you have one)
    path('orders/live-board-preview.png', live_board_preview_image, name='live_board_preview'),

    path('finances/', include('finances.urls')),
    path('notifications/', include('notifications.urls')),
    path('sw.js', service_worker),
]
