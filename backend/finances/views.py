from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import transaction
import csv
from io import StringIO

from .models import (
    CommissionRate, PaperInventory, FinancialRecord, 
    AgentEarning, DiscountCode, MerchantSettings, Expense
)
from .forms import (
    CommissionRateForm, PaperInventoryForm, ExpenseForm,
    DiscountCodeForm, MerchantSettingsForm, PaperRestockForm
)
from orders.models import Order

def is_admin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'admin'


@login_required
@user_passes_test(is_admin)
def admin_financial_dashboard(request):
    """Main financial dashboard with revenue, costs, and profit analytics."""
    date_filter = request.GET.get('date', 'today')
    now = timezone.now()
    
    # Date range calculation
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif date_filter == 'week':
        start_date = now - timedelta(days=7)
        end_date = now
    elif date_filter == 'month':
        start_date = now - timedelta(days=30)
        end_date = now
    elif date_filter == 'year':
        start_date = now - timedelta(days=365)
        end_date = now
    elif date_filter == 'custom':
        try:
            start_date = datetime.strptime(request.GET.get('start_date', ''), '%Y-%m-%d')
            end_date = datetime.strptime(request.GET.get('end_date', ''), '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    
    # Financial summary using FinancialRecord model
    profit_loss = FinancialRecord.get_profit_loss(start_date, end_date)
    
    # Order-based revenue (direct from orders)
    order_revenue = Order.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
        status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']
    ).aggregate(
        total=Sum('total_price'),
        total_profit=Sum('profit'),
        total_cost=Sum('cost_of_goods'),
        total_commission=Sum('agent_commission'),
        count=Count('id')
    )
    
    # Expense breakdown by category
    expenses_by_category = Expense.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Commission summary
    commission_summary = AgentEarning.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).aggregate(
        total_paid=Sum('commission_amount', filter=Q(is_paid=True)),
        total_pending=Sum('commission_amount', filter=Q(is_paid=False)),
        total_agents=Count('agent', distinct=True),
        total_orders=Count('id')
    )
    
    # Paper inventory
    paper_inventory = PaperInventory.objects.all()
    total_paper_value = sum(paper.total_value() for paper in paper_inventory)
    low_stock_items = [paper for paper in paper_inventory if paper.is_low_stock]
    
    # Recent transactions
    recent_transactions = FinancialRecord.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).select_related('order', 'agent', 'created_by')[:20]
    
    # Top agents
    top_agents = AgentEarning.get_top_agents(
        limit=5, 
        start_date=start_date, 
        end_date=end_date
    )
    
    # Revenue trend (last 30 days for chart)
    revenue_trend = []
    for i in range(30):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        
        day_revenue = Order.objects.filter(
            created_at__gte=day_start,
            created_at__lte=day_end,
            status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']
        ).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
        
        revenue_trend.append({
            'date': day.strftime('%Y-%m-%d'),
            'revenue': float(day_revenue),
            'label': day.strftime('%b %d')
        })
    revenue_trend.reverse()  # Chronological order
    
    # Order status distribution
    status_distribution = Order.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).values('status').annotate(
        count=Count('id'),
        total_value=Sum('total_price')
    ).order_by('status')
    
    context = {
        # Financial summary
        'total_revenue': order_revenue['total'] or Decimal('0.00'),
        'total_costs': order_revenue['total_cost'] or Decimal('0.00'),
        'total_commissions': order_revenue['total_commission'] or Decimal('0.00'),
        'total_profit': order_revenue['total_profit'] or Decimal('0.00'),
        'order_count': order_revenue['count'] or 0,
        
        # Profit/Loss from financial records
        'profit_loss': profit_loss,
        
        # Expenses
        'expenses_by_category': expenses_by_category,
        'total_expenses': sum(expense['total'] for expense in expenses_by_category),
        
        # Commissions
        'commission_summary': commission_summary,
        
        # Paper inventory
        'paper_inventory': paper_inventory,
        'total_paper_value': total_paper_value,
        'low_stock_items': low_stock_items,
        'low_stock_count': len(low_stock_items),
        
        # Recent activity
        'recent_transactions': recent_transactions,
        'top_agents': top_agents,
        
        # Charts data
        'revenue_trend': revenue_trend,
        'status_distribution': list(status_distribution),
        
        # Filters
        'date_filter': date_filter,
        'start_date': start_date.strftime('%Y-%m-%d') if date_filter == 'custom' else None,
        'end_date': end_date.strftime('%Y-%m-%d') if date_filter == 'custom' else None,
        
        # Profit margin
        'profit_margin': (order_revenue['total_profit'] / order_revenue['total'] * 100) if order_revenue['total'] and order_revenue['total'] > 0 else 0,
        
        # Forms
        'expense_form': ExpenseForm(),
        'discount_form': DiscountCodeForm(),
    }
    
    return render(request, 'finances/admin_financial_dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def manage_commission_rates(request):
    """Manage commission rates with history."""
    if request.method == 'POST':
        form = CommissionRateForm(request.POST)
        if form.is_valid():
            commission_rate = form.save(commit=False)
            commission_rate.created_by = request.user
            commission_rate.save()
            
            # Update all pending agent earnings with new rate
            new_rate = commission_rate.rate_percentage
            AgentEarning.objects.filter(
                is_paid=False, 
                status='pending'
            ).update(commission_rate=new_rate)
            
            messages.success(
                request, 
                f'Commission rate set to {commission_rate.rate_percentage}%. '
                f'Pending earnings updated with new rate.'
            )
            return redirect('manage_commission_rates')
    else:
        form = CommissionRateForm()
    
    all_rates = CommissionRate.objects.all()
    active_rate = CommissionRate.get_active_rate()
    
    # Stats about current rate
    if active_rate:
        affected_earnings = AgentEarning.objects.filter(
            commission_rate=active_rate.rate_percentage,
            is_paid=False
        ).aggregate(
            total=Sum('commission_amount'),
            count=Count('id')
        )
    else:
        affected_earnings = {'total': 0, 'count': 0}
    
    return render(request, 'finances/manage_commission_rates.html', {
        'form': form,
        'active_rate': active_rate,
        'all_rates': all_rates,
        'affected_earnings': affected_earnings,
    })


@login_required
@user_passes_test(is_admin)
def manage_paper_inventory(request):
    """Manage paper inventory with stock alerts."""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_inventory':
            form = PaperInventoryForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Paper type added successfully.')
                return redirect('manage_paper_inventory')
        
        elif action == 'restock':
            inventory_id = request.POST.get('inventory_id')
            quantity = int(request.POST.get('quantity', 0))
            cost_per_sheet = request.POST.get('cost_per_sheet')
            
            if cost_per_sheet:
                cost_per_sheet = Decimal(cost_per_sheet)
            
            inventory = get_object_or_404(PaperInventory, id=inventory_id)
            inventory.restock(quantity, cost_per_sheet)
            
            messages.success(
                request, 
                f'Restocked {quantity} sheets of {inventory.get_paper_type_display()}.'
            )
            return redirect('manage_paper_inventory')
        
        elif action == 'update_threshold':
            inventory_id = request.POST.get('inventory_id')
            threshold = int(request.POST.get('threshold', 500))
            
            inventory = get_object_or_404(PaperInventory, id=inventory_id)
            inventory.low_stock_threshold = threshold
            inventory.save(update_fields=['low_stock_threshold'])
            
            messages.success(request, f'Low stock threshold updated for {inventory.get_paper_type_display()}.')
            return redirect('manage_paper_inventory')
    
    else:
        form = PaperInventoryForm()
    
    inventory_items = PaperInventory.objects.all()
    
    return render(request, 'finances/manage_paper_inventory.html', {
        'form': form,
        'inventory': inventory_items,
        'restock_form': PaperRestockForm(),
    })


@login_required
@user_passes_test(is_admin)
def add_expense(request):
    """Add a new expense with category."""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()  # This will auto-create FinancialRecord
            messages.success(
                request, 
                f'Expense of UGX {expense.amount:,.0f} recorded in {expense.get_category_display()}.'
            )
            return redirect('financial_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('financial_dashboard')


@login_required
@user_passes_test(is_admin)
def expense_list(request):
    """List all expenses with filtering."""
    expenses = Expense.objects.select_related('created_by').all()
    
    # Filters
    category = request.GET.get('category')
    if category:
        expenses = expenses.filter(category=category)
    
    date_filter = request.GET.get('date', 'month')
    now = timezone.now()
    if date_filter == 'today':
        expenses = expenses.filter(created_at__date=now.date())
    elif date_filter == 'week':
        expenses = expenses.filter(created_at__gte=now - timedelta(days=7))
    elif date_filter == 'month':
        expenses = expenses.filter(created_at__gte=now - timedelta(days=30))
    
    # Pagination
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary
    total_expenses = expenses.aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    return render(request, 'finances/expense_list.html', {
        'page_obj': page_obj,
        'expenses': page_obj.object_list,
        'total_expenses': total_expenses,
        'categories': Expense.EXPENSE_CATEGORIES,
        'filter_category': category,
        'filter_date': date_filter,
    })


@login_required
@user_passes_test(is_admin)
def manage_discount_codes(request):
    """Manage discount codes."""
    if request.method == 'POST':
        form = DiscountCodeForm(request.POST)
        if form.is_valid():
            discount = form.save(commit=False)
            discount.created_by = request.user
            discount.save()
            messages.success(request, f'Discount code "{discount.code}" created!')
            return redirect('manage_discount_codes')
    else:
        form = DiscountCodeForm()
    
    discount_codes = DiscountCode.objects.all()
    
    return render(request, 'finances/manage_discount_codes.html', {
        'form': form,
        'discount_codes': discount_codes,
    })


@login_required
@user_passes_test(is_admin)
def toggle_discount_code(request, code_id):
    """Activate/deactivate a discount code."""
    discount = get_object_or_404(DiscountCode, id=code_id)
    discount.is_active = not discount.is_active
    discount.save(update_fields=['is_active'])
    
    status = 'activated' if discount.is_active else 'deactivated'
    messages.success(request, f'Discount code "{discount.code}" {status}.')
    return redirect('manage_discount_codes')


@login_required
@user_passes_test(is_admin)
def manage_merchant_settings(request):
    """Manage payment merchant settings."""
    if request.method == 'POST':
        form = MerchantSettingsForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Merchant settings updated!')
            return redirect('manage_merchant_settings')
    else:
        form = MerchantSettingsForm()
    
    merchants = MerchantSettings.objects.all()
    
    return render(request, 'finances/manage_merchant_settings.html', {
        'form': form,
        'merchants': merchants,
    })


@login_required
@user_passes_test(is_admin)
def agent_earnings_management(request):
    """Admin view to manage all agent earnings."""
    # Filters
    agent_id = request.GET.get('agent')
    status_filter = request.GET.get('status', 'pending')
    date_filter = request.GET.get('date', 'month')
    
    now = timezone.now()
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0)
    elif date_filter == 'week':
        start_date = now - timedelta(days=7)
    elif date_filter == 'month':
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=30)
    
    earnings = AgentEarning.objects.select_related('agent', 'order').filter(
        created_at__gte=start_date
    )
    
    if agent_id:
        earnings = earnings.filter(agent_id=agent_id)
    
    if status_filter == 'paid':
        earnings = earnings.filter(is_paid=True)
    elif status_filter == 'pending':
        earnings = earnings.filter(is_paid=False)
    
    # Bulk pay
    if request.method == 'POST' and request.POST.get('action') == 'bulk_pay':
        earning_ids = request.POST.getlist('earning_ids')
        if earning_ids:
            count = AgentEarning.objects.filter(
                id__in=earning_ids, 
                is_paid=False
            ).update(
                is_paid=True, 
                status='paid', 
                paid_at=timezone.now(), 
                paid_by=request.user
            )
            messages.success(request, f'Marked {count} earnings as paid.')
            return redirect('agent_earnings_management')
    
    # Summary
    summary = earnings.aggregate(
        total=Sum('commission_amount'),
        paid=Sum('commission_amount', filter=Q(is_paid=True)),
        pending=Sum('commission_amount', filter=Q(is_paid=False)),
        count=Count('id')
    )
    
    # Pagination
    paginator = Paginator(earnings, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all agents for filter dropdown
    from django.contrib.auth import get_user_model
    User = get_user_model()
    agents = User.objects.filter(role='agent')
    
    return render(request, 'finances/agent_earnings_management.html', {
        'page_obj': page_obj,
        'earnings': page_obj.object_list,
        'summary': summary,
        'agents': agents,
        'filter_agent': agent_id,
        'filter_status': status_filter,
        'filter_date': date_filter,
    })


@login_required
@require_POST
@user_passes_test(is_admin)
def mark_earning_paid(request, earning_id):
    """Mark a single agent earning as paid."""
    earning = get_object_or_404(AgentEarning, id=earning_id)
    earning.mark_as_paid(paid_by=request.user)
    messages.success(request, f'Earning for {earning.agent.username} marked as paid.')
    return redirect('agent_earnings_management')


@login_required
def agent_earnings_dashboard(request):
    """Agent's personal earnings dashboard."""
    if getattr(request.user, 'role', None) != 'agent':
        messages.error(request, 'Access denied. Agents only.')
        return redirect('dashboard')
    
    # Date filters
    date_filter = request.GET.get('date', 'all')
    now = timezone.now()
    
    earnings = AgentEarning.objects.filter(agent=request.user)
    
    if date_filter == 'today':
        earnings = earnings.filter(created_at__date=now.date())
    elif date_filter == 'week':
        earnings = earnings.filter(created_at__gte=now - timedelta(days=7))
    elif date_filter == 'month':
        earnings = earnings.filter(created_at__gte=now - timedelta(days=30))
    
    # Summary
    summary = AgentEarning.get_agent_summary(
        request.user,
        start_date=now - timedelta(days=30) if date_filter != 'all' else None
    )
    
    # Recent earnings
    recent_earnings = earnings.select_related('order').order_by('-created_at')[:20]
    
    # Monthly breakdown (last 6 months)
    monthly_breakdown = []
    for i in range(6):
        month_start = now.replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        
        month_data = AgentEarning.objects.filter(
            agent=request.user,
            created_at__gte=month_start,
            created_at__lt=month_end
        ).aggregate(
            total=Sum('commission_amount'),
            count=Count('id'),
            paid=Sum('commission_amount', filter=Q(is_paid=True)),
            pending=Sum('commission_amount', filter=Q(is_paid=False))
        )
        
        monthly_breakdown.append({
            'month': month_start.strftime('%B %Y'),
            'total': month_data['total'] or Decimal('0.00'),
            'count': month_data['count'] or 0,
            'paid': month_data['paid'] or Decimal('0.00'),
            'pending': month_data['pending'] or Decimal('0.00'),
        })
    
    return render(request, 'finances/agent_earnings.html', {
        'earnings': recent_earnings,
        'summary': summary,
        'monthly_breakdown': monthly_breakdown,
        'date_filter': date_filter,
    })


@login_required
@user_passes_test(is_admin)
def export_financial_data(request):
    """Export financial data as CSV."""
    export_type = request.GET.get('type', 'transactions')
    date_filter = request.GET.get('date', 'month')
    
    now = timezone.now()
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0)
    elif date_filter == 'week':
        start_date = now - timedelta(days=7)
    elif date_filter == 'month':
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=30)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="financial_export_{now.strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    if export_type == 'transactions':
        writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Description', 'Order ID', 'Agent'])
        
        transactions = FinancialRecord.objects.filter(
            created_at__gte=start_date
        ).select_related('order', 'agent')
        
        for t in transactions:
            writer.writerow([
                t.created_at.strftime('%Y-%m-%d %H:%M'),
                t.get_transaction_type_display(),
                t.get_category_display() if t.category else '-',
                float(t.amount),
                t.description,
                f'#{t.order.id}' if t.order else '-',
                t.agent.username if t.agent else '-'
            ])
    
    elif export_type == 'earnings':
        writer.writerow(['Agent', 'Order', 'Commission Rate', 'Amount', 'Status', 'Date'])
        
        earnings = AgentEarning.objects.filter(
            created_at__gte=start_date
        ).select_related('agent', 'order')
        
        for e in earnings:
            writer.writerow([
                e.agent.username,
                f'#{e.order.id}',
                f'{e.commission_rate}%',
                float(e.commission_amount),
                'Paid' if e.is_paid else 'Pending',
                e.created_at.strftime('%Y-%m-%d')
            ])
    
    elif export_type == 'expenses':
        writer.writerow(['Date', 'Category', 'Amount', 'Description', 'Created By'])
        
        expenses = Expense.objects.filter(
            created_at__gte=start_date
        ).select_related('created_by')
        
        for e in expenses:
            writer.writerow([
                e.created_at.strftime('%Y-%m-%d'),
                e.get_category_display(),
                float(e.amount),
                e.description,
                e.created_by.username if e.created_by else '-'
            ])
    
    return response


@login_required
@user_passes_test(is_admin)
def financial_reports(request):
    """Generate detailed financial reports."""
    report_type = request.GET.get('report', 'daily')
    now = timezone.now()
    
    if report_type == 'daily':
        date = request.GET.get('date', now.strftime('%Y-%m-%d'))
        try:
            report_date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            report_date = now
        
        start_date = report_date.replace(hour=0, minute=0, second=0)
        end_date = report_date.replace(hour=23, minute=59, second=59)
        
    elif report_type == 'weekly':
        start_date = now - timedelta(days=7)
        end_date = now
        
    elif report_type == 'monthly':
        start_date = now - timedelta(days=30)
        end_date = now
        
    else:
        start_date = now - timedelta(days=7)
        end_date = now
    
    # Revenue breakdown
    revenue_data = Order.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
        status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']
    ).aggregate(
        total_revenue=Sum('total_price'),
        total_profit=Sum('profit'),
        total_cost=Sum('cost_of_goods'),
        total_commission=Sum('agent_commission'),
        paper_used=Sum('paper_used'),
        order_count=Count('id'),
        avg_order_value=Avg('total_price')
    )
    
    # Revenue by station
    revenue_by_station = Order.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
        status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']
    ).values('station__name').annotate(
        total=Sum('total_price'),
        profit=Sum('profit'),
        count=Count('id')
    ).order_by('-total')
    
    # Expense breakdown
    expense_data = Expense.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Commission breakdown
    commission_data = AgentEarning.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).aggregate(
        total=Sum('commission_amount'),
        paid=Sum('commission_amount', filter=Q(is_paid=True)),
        pending=Sum('commission_amount', filter=Q(is_paid=False)),
        count=Count('id')
    )
    
    context = {
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'revenue_data': revenue_data,
        'revenue_by_station': list(revenue_by_station),
        'expense_data': expense_data,
        'commission_data': commission_data,
        'profit_loss': (revenue_data['total_revenue'] or Decimal('0.00')) - (expense_data['total'] or Decimal('0.00')),
    }
    
    return render(request, 'finances/financial_reports.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def validate_discount_code(request):
    """AJAX endpoint to validate discount codes."""
    code = request.POST.get('code', '').strip().upper()
    order_total = Decimal(request.POST.get('order_total', '0'))
    
    try:
        discount = DiscountCode.objects.get(code=code)
        
        if not discount.is_valid:
            return JsonResponse({
                'valid': False,
                'error': 'This discount code is expired or has reached its usage limit.'
            })
        
        if order_total < discount.minimum_order:
            return JsonResponse({
                'valid': False,
                'error': f'Minimum order of UGX {discount.minimum_order:,.0f} required.'
            })
        
        discounted_total = discount.apply_discount(order_total)
        savings = order_total - discounted_total
        
        return JsonResponse({
            'valid': True,
            'discount_type': discount.get_discount_type_display(),
            'discount_value': float(discount.discount_value),
            'original_total': float(order_total),
            'discounted_total': float(discounted_total),
            'savings': float(savings),
            'description': discount.description
        })
        
    except DiscountCode.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'error': 'Invalid discount code.'
        })


@login_required
@user_passes_test(is_admin)
def paper_inventory_alerts(request):
    """API endpoint for low stock alerts."""
    low_stock = PaperInventory.objects.filter(
        quantity__lte=models.F('low_stock_threshold'),
        is_active=True
    )
    
    alerts = [{
        'id': item.id,
        'type': item.get_paper_type_display(),
        'quantity': item.quantity,
        'threshold': item.low_stock_threshold,
        'status': item.stock_status,
        'last_restocked': item.last_restocked_at.strftime('%Y-%m-%d') if item.last_restocked_at else None
    } for item in low_stock]
    
    return JsonResponse({
        'alerts': alerts,
        'count': len(alerts),
        'timestamp': timezone.now().isoformat()
    })
