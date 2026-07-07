from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import CommissionRate, PaperInventory, FinancialRecord, AgentEarning
from .forms import CommissionRateForm, PaperInventoryForm
from orders.models import Order

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_financial_dashboard(request):
    """Admin financial overview"""
    
    # Date filters
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
    
    # Financial metrics from Order model
    total_revenue = Order.objects.filter(
        created_at__gte=start_date,
        status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']
    ).aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    total_costs = Order.objects.filter(
        created_at__gte=start_date
    ).aggregate(Sum('cost_of_goods'))['cost_of_goods__sum'] or 0
    
    total_commissions = Order.objects.filter(
        created_at__gte=start_date
    ).aggregate(Sum('agent_commission'))['agent_commission__sum'] or 0
    
    total_profit = total_revenue - total_costs - total_commissions
    
    # Paper inventory
    paper_inventory = PaperInventory.objects.all()
    total_paper_value = sum(paper.total_value() for paper in paper_inventory)
    
    # Recent financial records
    recent_transactions = FinancialRecord.objects.filter(
        created_at__gte=start_date
    )[:20]
    
    # Top performing agents
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
    }
    
    return render(request, 'finances/admin_financial_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def manage_commission_rates(request):
    """Admin can set commission rates"""
    if request.method == 'POST':
        form = CommissionRateForm(request.POST)
        if form.is_valid():
            # Deactivate all existing rates
            CommissionRate.objects.update(is_active=False)
            commission_rate = form.save()
            messages.success(request, f'Commission rate set to {commission_rate.rate_percentage}%')
            return redirect('finances:manage_commission_rates')
    else:
        form = CommissionRateForm()
    
    active_rate = CommissionRate.get_active_rate()
    all_rates = CommissionRate.objects.all()
    
    return render(request, 'finances/manage_commission_rates.html', {
        'form': form,
        'active_rate': active_rate,
        'all_rates': all_rates,
    })

@login_required
@user_passes_test(is_admin)
def manage_paper_inventory(request):
    """Admin manages paper inventory"""
    if request.method == 'POST':
        form = PaperInventoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paper inventory updated successfully')
            return redirect('finances:manage_paper_inventory')
    else:
        form = PaperInventoryForm()
    
    inventory = PaperInventory.objects.all()
    
    return render(request, 'finances/manage_paper_inventory.html', {
        'form': form,
        'inventory': inventory,
    })

@login_required
def agent_earnings_dashboard(request):
    """Agent views their earnings"""
    if request.user.role != 'agent':
        messages.error(request, 'Access denied. Agents only.')
        return redirect('dashboard')
    
    earnings = AgentEarning.objects.filter(agent=request.user)
    total_earned = earnings.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
    pending_earnings = earnings.filter(is_paid=False).aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
    paid_earnings = earnings.filter(is_paid=True).aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
    
    context = {
        'earnings': earnings,
        'total_earned': total_earned,
        'pending_earnings': pending_earnings,
        'paid_earnings': paid_earnings,
    }
    
    return render(request, 'finances/agent_earnings.html', context)
