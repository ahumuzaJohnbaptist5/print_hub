from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Payment
from orders.models import Order
import re

@login_required
def payment_page(request, order_id):
    """The single unified Copy & Pay + Paste Message page"""
    order = get_object_or_404(Order, id=order_id, client=request.user)
    
    # If already has a payment, redirect to status
    existing_payment = Payment.objects.filter(order=order).first()
    if existing_payment:
        return redirect('payment_status', payment_id=existing_payment.id)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        customer_phone = request.POST.get('customer_phone')
        transaction_id = request.POST.get('transaction_id', '').strip()
        transaction_message = request.POST.get('transaction_message', '').strip()
        
        if not all([payment_method, customer_phone, transaction_id]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('payment_page', order_id=order_id)
        
        # Merchant details
        if payment_method == 'mtn':
            merchant_phone, merchant_name = '0765511075', 'Matovu Evaristo'
        else:
            merchant_phone, merchant_name = '0775523720', 'Ezra Nasaasira'
        
        # Create Payment (Status: Pending)
        Payment.objects.create(
            order=order, user=request.user, amount=order.total_price,
            payment_method=payment_method, customer_phone=customer_phone,
            merchant_phone=merchant_phone, merchant_name=merchant_name,
            transaction_id=transaction_id, transaction_message=transaction_message,
            status='pending'
        )
        
        messages.success(request, 'Payment submitted! Waiting for admin approval.')
        return redirect('dashboard')

    return render(request, 'payments/payment_page.html', {'order': order})

@login_required
def payment_status(request, payment_id):
    """Show payment status"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    return render(request, 'payments/payment_status.html', {'payment': payment})

@login_required
@require_POST
def extract_transaction_id(request):
    """AJAX endpoint to extract Transaction ID from pasted SMS"""
    message = request.POST.get('message', '')
    
    # Regex to find common transaction ID patterns
    patterns = [
        r'(?:Transaction\s*ID|Ref|Reference)[:\s]*([A-Z0-9]+)',
        r'\b([A-Z]{2,}[0-9]{6,})\b',
        r'\b([0-9]{10,})\b'
    ]
    
    transaction_id = None
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            transaction_id = match.group(1).upper()
            break
            
    is_valid = bool(transaction_id and len(transaction_id) >= 6)
    
    return JsonResponse({'transaction_id': transaction_id, 'is_valid': is_valid})

@login_required
def admin_approve_payments(request):
    """Admin page to approve/reject payments"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
        
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        action = request.POST.get('action')
        payment = get_object_or_404(Payment, id=payment_id)
        
        if action == 'approve':
            # 1. Update Payment Status
            payment.status = 'approved'
            payment.save()
            
            # 2. Update Order Status
            payment.order.status = 'paid'
            payment.order.save()
            
            # 3. Send Email Notification
            from orders.utils import send_payment_confirmed_email
            try:
                send_payment_confirmed_email(payment.order)
            except Exception as e:
                print(f"Payment email failed: {e}")
            
            messages.success(request, f'Payment {payment.transaction_id} approved!')
            
        elif action == 'reject':
            payment.status = 'rejected'
            payment.save()
            messages.error(request, f'Payment {payment.transaction_id} rejected.')
            
        return redirect('admin_approve_payments')

    # GET request: Show pending payments
    pending = Payment.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'payments/admin_approve.html', {'pending_payments': pending})
