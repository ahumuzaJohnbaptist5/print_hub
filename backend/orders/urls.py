# orders/urls.py
from django.urls import path
from . import views
from . import passport_api  # <-- ADD THIS LINE

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('receipt/<int:order_id>/', views.order_receipt_view, name='order_receipt'),
    path('track/', views.order_track_view, name='track_order'),
    path('admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('agent/', views.agent_dashboard_view, name='agent_dashboard'),
    path('update/<int:order_id>/', views.update_order_status_view, name='update_order_status'),
    path('download/<int:order_id>/', views.download_order_file_view, name='download_order_file'),
    path('toggle-pause/', views.toggle_system_pause_view, name='toggle_system_pause'),
    path('live-board/', views.live_board_view, name='live_board'),
    path('live-board/api/', views.live_board_api_view, name='live_board_api'),

    # Passport API endpoints
    path('api/analyze-passport/', passport_api.analyze_passport_frame, name='analyze_passport'),
    path('api/process-passport/', passport_api.process_passport_photo, name='process_passport'),
    path('api/process-scan/', passport_api.process_scanned_document, name='process_scan'),
]
