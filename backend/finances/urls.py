from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.admin_financial_dashboard, name='financial_dashboard'),
    path('commissions/', views.manage_commission_rates, name='manage_commission_rates'),
    path('inventory/', views.manage_paper_inventory, name='manage_paper_inventory'),
    path('expenses/add/', views.add_expense, name='add_expense'),
    path('agent-earnings/', views.agent_earnings_dashboard, name='agent_earnings'),
]
