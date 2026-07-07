from django.urls import path
from . import views

app_name = 'finances'

urlpatterns = [
    path('admin/dashboard/', views.admin_financial_dashboard, name='admin_financial_dashboard'),
    path('admin/commission-rates/', views.manage_commission_rates, name='manage_commission_rates'),
    path('admin/paper-inventory/', views.manage_paper_inventory, name='manage_paper_inventory'),
    path('agent/earnings/', views.agent_earnings_dashboard, name='agent_earnings'),
]
