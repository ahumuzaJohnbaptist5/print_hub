from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.admin_financial_dashboard, name='financial_dashboard'),
    path('commission-rates/', views.manage_commission_rates, name='manage_commission_rates'),
    path('paper-inventory/', views.manage_paper_inventory, name='manage_paper_inventory'),
    path('add-expense/', views.add_expense, name='add_expense'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('discount-codes/', views.manage_discount_codes, name='manage_discount_codes'),
    path('discount-codes/<int:code_id>/toggle/', views.toggle_discount_code, name='toggle_discount_code'),
    path('validate-discount/', views.validate_discount_code, name='validate_discount_code'),
    path('merchant-settings/', views.manage_merchant_settings, name='manage_merchant_settings'),
    path('agent-earnings/', views.agent_earnings_dashboard, name='agent_earnings'),
    path('agent-earnings/management/', views.agent_earnings_management, name='agent_earnings_management'),
    path('agent-earnings/<int:earning_id>/pay/', views.mark_earning_paid, name='mark_earning_paid'),
    path('export/', views.export_financial_data, name='export_financial_data'),
    path('reports/', views.financial_reports, name='financial_reports'),
    path('paper-alerts/', views.paper_inventory_alerts, name='paper_inventory_alerts'),
]
