# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from orders import views
from accounts import views as accounts_views
from django.http import HttpResponse
from django.urls import reverse, NoReverseMatch

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
    path('', views.home_view, name='home'),
    
    # Authentication - Using custom views from accounts app
    path('auth/login/', accounts_views.login_view, name='login'),
    path('auth/logout/', accounts_views.logout_view, name='logout'),
    path('auth/register/', accounts_views.register_view, name='register'),
    path('auth/profile/', accounts_views.profile_view, name='profile'),
    
    # Orders & Upload (Client)
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
    
    # API Endpoints
    path('orders/api/analyze-passport/', login_required(views.api_analyze_passport), name='analyze_passport'),
    path('orders/api/process-passport/', login_required(views.api_process_passport), name='process_passport'),
    path('orders/api/process-scan/', login_required(views.api_process_scan), name='process_scan'),
    path('orders/api/validate-discount/', views.validate_discount_code, name='validate_discount_code'),
    
    # Misc
    path('all-links/', views.all_links_view, name='all_links'),
]

# ============================================================
# INCLUDE OTHER APP URLS
# ============================================================
try:
    urlpatterns += [path('finances/', include('finances.urls'))]
except Exception:
    pass

try:
    urlpatterns += [path('payments/', include('payments.urls'))]
except Exception:
    pass

try:
    urlpatterns += [path('notifications/', include('notifications.urls'))]
except Exception:
    pass

try:
    urlpatterns += [path('stations/', include('stations.urls'))]
except Exception:
    pass

# ============================================================
# PLACEHOLDER ROUTES FOR ANY URL NAMES REFERENCED IN TEMPLATES
# These prevent NoReverseMatch crashes
# ============================================================

_placeholder_urls = {
    'financial_dashboard': 'finances/dashboard/',
    'admin_approve_payments': 'admin/approve-payments/',
    'low_stock_alerts': 'api/low-stock-alerts/',
    'payment_status_check': 'payments/status/<int:order_id>/check/',
    'manage_commission_rates': 'finances/commission-rates/',
    'manage_paper_inventory': 'finances/paper-inventory/',
    'add_expense': 'finances/add-expense/',
    'expense_list': 'finances/expenses/',
    'manage_discount_codes': 'finances/discount-codes/',
    'toggle_discount_code': 'finances/discount-codes/<int:code_id>/toggle/',
    'manage_merchant_settings': 'finances/merchant-settings/',
    'agent_earnings': 'finances/agent-earnings/',
    'agent_earnings_management': 'finances/agent-earnings/management/',
    'mark_earning_paid': 'finances/agent-earnings/<int:earning_id>/pay/',
    'export_financial_data': 'finances/export/',
    'financial_reports': 'finances/reports/',
    'paper_inventory_alerts': 'finances/paper-alerts/',
    'verify_email': 'auth/verify-email/<str:token>/',
    'verification_sent': 'auth/verification-sent/',
}

for url_name, url_path in _placeholder_urls.items():
    try:
        reverse(url_name)
    except NoReverseMatch:
        urlpatterns.append(path(url_path, _placeholder_view, name=url_name))

# ============================================================
# STATIC & MEDIA FILES (Development only)
# ============================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
