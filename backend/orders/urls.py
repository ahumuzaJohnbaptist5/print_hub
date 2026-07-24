# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Public URLs
    path('', views.home_view, name='home'),
    path('track/', views.order_track_view, name='track_order'),
    path('links/', views.all_links_view, name='all_links'),
    
    # Client URLs
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('my-orders/', views.my_orders_view, name='my_orders'),
    path('<int:order_id>/receipt/', views.order_receipt_view, name='order_receipt'),
    path('<int:order_id>/cancel/', views.cancel_order_view, name='cancel_order'),
    path('<int:order_id>/download/', views.download_order_file_view, name='download_order_file'),
    path('<int:order_id>/payment/', views.payment_page_view, name='payment_page'),  # NEW
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('toggle-pause/', views.toggle_system_pause_view, name='toggle_system_pause'),
    
    # Agent URLs
    path('agent-dashboard/', views.agent_dashboard_view, name='agent_dashboard'),
    path('<int:order_id>/update-status/', views.update_order_status_view, name='update_order_status'),
    
    # Live Board URLs
    path('live-board/', views.live_board_view, name='live_board'),
    path('api/live-board/', views.live_board_api_view, name='live_board_api'),
    path('live-board-preview/', views.live_board_preview_image, name='live_board_preview'),
    
    # API Endpoints
    path('api/analyze-passport/', views.api_analyze_passport, name='api_analyze_passport'),
    path('api/process-passport/', views.api_process_passport, name='api_process_passport'),
    path('api/process-scan/', views.api_process_scan, name='api_process_scan'),
    path('api/validate-discount/', views.validate_discount_code, name='validate_discount_code'),
]
