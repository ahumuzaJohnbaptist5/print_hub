from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from orders.views import (
    dashboard_view,
    upload_view,
    admin_dashboard_view,
    update_order_status_view,
    agent_dashboard_view,
    order_receipt_view,
    download_order_file_view,
    order_track_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 🎯 Root URL shows upload page (NO login required to see it)
    path('', upload_view, name='home'),
    
    path('auth/', include('accounts.urls')),
    path('dashboard/', login_required(dashboard_view), name='dashboard'),
    path('upload/', upload_view, name='upload'),
    path('track/', order_track_view, name='track_order'),
    path('admin-dashboard/', login_required(admin_dashboard_view), name='admin_dashboard'),
    path('orders/agent/', login_required(agent_dashboard_view), name='agent_dashboard'),
    path('orders/<int:order_id>/update/', login_required(update_order_status_view), name='update_order_status'),
    path('orders/<int:order_id>/receipt/', login_required(order_receipt_view), name='order_receipt'),
    path('orders/<int:order_id>/file/', login_required(download_order_file_view), name='download_order_file'),
    path('payments/', include('payments.urls')),
]
