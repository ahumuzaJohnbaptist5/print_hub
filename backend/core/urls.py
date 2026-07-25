# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from orders import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Home
    path('', views.home_view, name='home'),
    
    # Auth
    path('auth/login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('auth/logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    
    # 🛑 ADDED MISSING URLS TO PREVENT TEMPLATE CRASHES 🛑
    # Placeholder for 'register' (points to login page for now so the site doesn't crash)
    path('auth/register/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='register'),
    # Placeholder for 'admin_approve_payments' (points to admin dashboard for now)
    path('admin/approve-payments/', views.admin_dashboard_view, name='admin_approve_payments'),
    
    # Orders & Upload
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('my-orders/', views.my_orders_view, name='my_orders'),
    path('track/', views.order_track_view, name='track_order'),
    
    # Order Details & Actions
    path('orders/<int:order_id>/receipt/', views.order_receipt_view, name='order_receipt'),
    path('orders/<int:order_id>/payment/', views.payment_page_view, name='payment_page'),
    path('orders/<int:order_id>/cancel/', views.cancel_order_view, name='cancel_order'),
    path('orders/<int:order_id>/download/', views.download_order_file_view, name='download_order_file'),
    path('orders/<int:order_id>/update-status/', views.update_order_status_view, name='update_order_status'),
    
    # Admin & Agent Dashboards
    path('orders/admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('orders/agent-dashboard/', views.agent_dashboard_view, name='agent_dashboard'),
    path('orders/toggle-system-pause/', views.toggle_system_pause_view, name='toggle_system_pause'),
    
    # Live Board
    path('live-board/', views.live_board_view, name='live_board'),
    path('api/live-board/', views.live_board_api_view, name='live_board_api'),
    path('api/live-board/preview/', views.live_board_preview_image, name='live_board_preview'),
    
    # API Endpoints for Passport & Scanner
    path('orders/api/analyze-passport/', login_required(views.api_analyze_passport), name='analyze_passport'),
    path('orders/api/process-passport/', login_required(views.api_process_passport), name='process_passport'),
    path('orders/api/process-scan/', login_required(views.api_process_scan), name='process_scan'),
    path('orders/api/validate-discount/', views.validate_discount_code, name='validate_discount_code'),
    
    # Misc
    path('all-links/', views.all_links_view, name='all_links'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
