from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import CommissionRate, PaperInventory, FinancialRecord, AgentEarning
from .forms import CommissionRateForm, PaperInventoryForm, ExpenseForm
from orders.models import Order

def is_admin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_financial_dashboard(request):
    date_filter = request.GET.get('date', 'today')
    now = timezone.now()
    
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_filter == 'week':
        start_date = now - timedelta(days=7)
    elif date_filter == 'month':
        start_date = now - timedelta(days=30)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 1. Total Revenue (Sum of total_price for active orders)
    total_revenue = Order.objects.filter(
        created_at__gte=start_date,
        status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']
    ).aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0.00')
    
    # 2. Total Costs (Sum of expenses from FinancialRecord)
    total_costs = FinancialRecord.objects.filter(
        created_at__gte=start_date,
        transaction_type='expense'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # 3. Total Commissions (Sum of commissions from AgentEarning)
    total_commissions = AgentEarning.objects.filter(
        created_at__gte=start_date
    ).aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0.00')
    
    # 4. Calculate Profit
    total_profit = total_revenue - total_costs - total_commissions
    
    paper_inventory = PaperInventory.objects.all()
    total_paper_value = sum(paper.total_value() for paper in paper_inventory)
    
    recent_transactions = FinancialRecord.objects.filter(
        created_at__gte=start_date, transaction_type='expense'
    )[:20]
    
    top_agents = AgentEarning.objects.filter(
        created_at__gte=start_date
    ).values('agent__username', 'agent__first_name').annotate(
        total_earnings=Sum('commission_amount'),
        orders_count=Count('id')
    ).order_by('-total_earnings')[:5]
    
    context = {
        'total_revenue': total_revenue,
        'total_costs': total_costs,
        'total_commissions': total_commissions,
        'total_profit': total_profit,
        'paper_inventory': paper_inventory,
        'total_paper_value': total_paper_value,
        'recent_transactions': recent_transactions,
        'top_agents': top_agents,
        'date_filter': date_filter,
        'profit_margin': (total_profit / total_revenue * 100) if total_revenue > 0 else 0,
        'expense_form': ExpenseForm(), # For the modal
    }
    
    return render(request, 'finances/admin_financial_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def manage_commission_rates(request):
    if request.method == 'POST':
        form = CommissionRateForm(request.POST)
        if form.is_valid():
            CommissionRate.objects.update(is_active=False)
            commission_rate = form.save()
            messages.success(request, f'Commission rate set to {commission_rate.rate_percentage}%')
            return redirect('manage_commission_rates')
    else:
        form = CommissionRateForm()
    
    return render(request, 'finances/manage_commission_rates.html', {
        'form': form,
        'active_rate': CommissionRate.get_active_rate(),
        'all_rates': CommissionRate.objects.all(),
    })

@login_required
@user_passes_test(is_admin)
def manage_paper_inventory(request):
    if request.method == 'POST':
        form = PaperInventoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paper inventory updated successfully')
            return redirect('manage_paper_inventory')
    else:
        form = PaperInventoryForm()
    
    return render(request, 'finances/manage_paper_inventory.html', {
        'form': form,
        'inventory': PaperInventory.objects.all(),
    })

@login_required
@user_passes_test(is_admin)
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.transaction_type = 'expense'
            expense.save()
            messages.success(request, f'Expense of UGX {expense.amount} recorded.')
            return redirect('financial_dashboard')
    return redirect('financial_dashboard')

@login_required
def agent_earnings_dashboard(request):
    if getattr(request.user, 'role', None) != 'agent':
        messages.error(request, 'Access denied. Agents only.')
        return redirect('dashboard')
    
    earnings = AgentEarning.objects.filter(agent=request.user)
    total_earned = earnings.aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0.00')
    pending_earnings = earnings.filter(is_paid=False).aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0.00')
    paid_earnings = earnings.filter(is_paid=True).aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0.00')
    
    return render(request, 'finances/agent_earnings.html', {
        'earnings': earnings,
        'total_earned': total_earned,
        'pending_earnings': pending_earnings,
        'paid_earnings': paid_earnings,
    })
