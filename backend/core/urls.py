from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from orders.views import dashboard_view, upload_view, admin_dashboard_view, update_order_status_view

def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('auth/', include('accounts.urls')),
    path('dashboard/', login_required(dashboard_view), name='dashboard'),
    path('upload/', login_required(upload_view), name='upload'),
    path('admin-dashboard/', login_required(admin_dashboard_view), name='admin_dashboard'),
    path('order/<int:order_id>/status/', login_required(update_order_status_view), name='update_order_status'),
]