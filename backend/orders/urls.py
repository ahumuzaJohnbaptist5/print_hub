from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('<int:order_id>/receipt/', views.order_receipt_view, name='order_receipt'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('agent-dashboard/', views.agent_dashboard_view, name='agent_dashboard'),
    path('<int:order_id>/update-status/', views.update_order_status_view, name='update_order_status'),
    path('<int:order_id>/download/', views.download_order_file_view, name='download_order_file'),
    path('track/', views.order_track_view, name='order_track'),
    
    # --- NEW LIVE BOARD PATHS ---
    path('live-board/', views.live_board_view, name='live_board'),
    path('api/live-board/', views.live_board_api_view, name='live_board_api'),
]
