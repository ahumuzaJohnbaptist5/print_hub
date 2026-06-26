from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
import requests
from .models import Order
from stations.models import Station

# 1. User Dashboard (View own orders)
@login_required
def dashboard_view(request):
    orders = Order.objects.filter(client=request.user).order_by('-created_at')
    return render(request, 'orders/dashboard.html', {'orders': orders})

# 2. Upload Order (Client uploads file)
@login_required
def upload_view(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        page_count = request.POST.get('page_count', 1)
        is_color = request.POST.get('is_color', 'False') == 'True'
        is_double_sided = request.POST.get('is_double_sided') == 'on'
        
        if not file:
            messages.error(request, 'Please select a file.')
            return redirect('upload')
        
        try:
            # Create order (price will be auto-calculated in model's save method)
            order = Order.objects.create(
                client=request.user,
                file=file,
                file_name=file.name,
                page_count=int(page_count),
                is_color=is_color,
                is_double_sided=is_double_sided,
                status='pending'
            )
            messages.success(request, f'Order submitted successfully! Total: {order.total_price:,} UGX')
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
    
    return render(request, 'orders/upload.html')

# 3. Verify Payment (Called after Flutterwave success)
@login_required
def verify_payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, client=request.user)
    
    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        
        if not transaction_id:
            messages.error(request, 'Missing transaction ID.')
            return redirect('dashboard')
        
        url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            
            if data.get('status') == 'success' and data['data']['status'] == 'successful':
                order.status = 'paid'
                order.save()
                messages.success(request, 'Payment verified successfully!')
            else:
                messages.error(request, 'Payment verification failed.')
        except Exception as e:
            messages.error(request, f'Error verifying payment: {str(e)}')
        
        return redirect('dashboard')
    
    return render(request, 'orders/verify_payment.html', {'order': order})

# 4. Admin Dashboard (View all orders)
@login_required
def admin_dashboard_view(request):
    # Check if user is admin
    if not hasattr(request.user, 'role') or request.user.role != 'admin':
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')
    
    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'orders/admin_dashboard.html', {'orders': orders})

# 5. Agent Dashboard (View orders for a specific station)
@login_required
def agent_dashboard_view(request, station_id):
    # Check if user is agent
    if not hasattr(request.user, 'role') or request.user.role != 'agent':
        messages.error(request, 'Access denied. Agent only.')
        return redirect('dashboard')
    
    station = get_object_or_404(Station, id=station_id)
    orders = Order.objects.filter(
        station=station, 
        status__in=['paid', 'printing', 'ready']
    ).order_by('-created_at')
    
    return render(request, 'orders/agent_dashboard.html', {
        'orders': orders,
        'station': station
    })

# 6. Update Order Status (For admin/agent)
@login_required
def update_order_status_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        valid_statuses = ['pending', 'paid', 'printing', 'ready', 'collected']
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status.')
            return redirect('dashboard')
        
        order.status = new_status
        order.save()
        messages.success(request, f'Order status updated to {new_status}.')
        
        # Redirect based on user role
        if hasattr(request.user, 'role'):
            if request.user.role == 'admin':
                return redirect('admin_dashboard')
            elif request.user.role == 'agent' and order.station:
                return redirect('agent_dashboard', station_id=order.station.id)
        
        return redirect('dashboard')
    
    return render(request, 'orders/update_status.html', {'order': order})