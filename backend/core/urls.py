# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

# Import views - Using modular imports
from orders.views import (
    client_views, admin_views, agent_views, 
    api_views, live_board_views
)
from accounts import views as accounts_views

# ============================================================
# PLACEHOLDER VIEW FOR UNDER CONSTRUCTION PAGES
# ============================================================
def _placeholder_view(request, *args, **kwargs):
    return HttpResponse("This page is under construction.", status=200)

# ============================================================
# URL PATTERNS
# ============================================================
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Home
    path('', client_views.home_view, name='home'),
    
    # Authentication - Using custom views
    path('auth/login/', accounts_views.login_view, name='login'),
    path('auth/logout/', accounts_views.logout_view, name='logout'),
    path('auth/register/', accounts_views.register_view, name='register'),
    path('auth/profile/', accounts_views.profile_view, name='profile'),
    
    # Orders & Upload (Client)
    path('dashboard/', client_views.dashboard_view, name='dashboard'),
    path('upload/', client_views.upload_view, name='upload'),
    path('my-orders/', client_views.my_orders_view, name='my_orders'),
    path('track/', client_views.order_track_view, name='track_order'),
    
    # Order Details & Actions
    path('orders/<int:order_id>/receipt/', client_views.order_receipt_view, name='order_receipt'),
    path('orders/<int:order_id>/passport-receipt/', client_views.passport_receipt_view, name='passport_receipt'),
    path('orders/<int:order_id>/payment/', client_views.payment_page_view, name='payment_page'),
    path('orders/<int:order_id>/cancel/', client_views.cancel_order_view, name='cancel_order'),
    path('orders/<int:order_id>/download/', client_views.download_order_file_view, name='download_order_file'),
    path('orders/<int:order_id>/update-status/', agent_views.update_order_status_view, name='update_order_status'),
    
    # Admin & Agent Dashboards
    path('orders/admin-dashboard/', admin_views.admin_dashboard_view, name='admin_dashboard'),
    path('orders/agent-dashboard/', agent_views.agent_dashboard_view, name='agent_dashboard'),
    path('orders/toggle-system-pause/', admin_views.toggle_system_pause_view, name='toggle_system_pause'),
    
    # Live Board
    path('live-board/', live_board_views.live_board_view, name='live_board'),
    path('api/live-board/', live_board_views.live_board_api_view, name='live_board_api'),
    path('api/live-board/preview/', live_board_views.live_board_preview_image, name='live_board_preview'),
    
    # API Endpoints
    path('orders/api/analyze-passport/', login_required(api_views.api_analyze_passport), name='analyze_passport'),
    path('orders/api/process-passport/', login_required(api_views.api_process_passport), name='process_passport'),
    path('orders/api/process-scan/', login_required(api_views.api_process_scan), name='process_scan'),
    path('orders/api/validate-discount/', api_views.validate_discount_code, name='validate_discount_code'),
    
    # File Processor API
   # path('file-processor/', include('file_processor.urls')),
    #recover passwords
    path('auth/', include('django.contrib.auth.urls')),
    
    # Misc
    path('all-links/', client_views.all_links_view, name='all_links'),
]

# ============================================================
# INCLUDE OTHER APP URLS
# ============================================================
urlpatterns += [path('finances/', include('finances.urls'))]
urlpatterns += [path('payments/', include('payments.urls'))]
urlpatterns += [path('notifications/', include('notifications.urls'))]
urlpatterns += [path('stations/', include('stations.urls'))]
urlpatterns += [path('referrals/', include('referrals.urls'))]  # ✅ ADDED



# ============================================================
# STATIC & MEDIA FILES (Development only)
# ============================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
