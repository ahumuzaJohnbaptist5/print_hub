from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Payment
from orders.models import Order
import requests
from django.conf import settings

@login_required
def initiate_payment(request, order_id):
    """First step: Select payment method and enter phone number"""
    order = get_object_or_404(Order, id=order_id, client=request.user)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        customer_phone = request.POST.get('customer_phone')
        
        if not payment_method or not customer_phone:
            messages.error(request, 'Please fill in all fields')
            return redirect('initiate_payment', order_id=order_id)
        
        # Set merchant details based on payment method
        if payment_method == 'mtn':
            merchant_phone = '0765511075'  # Replace with your actual MTN number
            merchant_name = 'Matovu Evaristo'  # Replace with your actual name
        else:  # airtel
            merchant_phone = '0775523720'  # Replace with your actual Airtel number
            merchant_name = 'Ezra Nasaasira'  # Replace with your actual name
        
        # Create payment record
        payment = Payment.objects.create(
            order=order,
            user=request.user,
            amount=order.total_price,
            payment_method=payment_method,
            customer_phone=customer_phone,
            merchant_phone=merchant_phone,
            merchant_name=merchant_name,
        )
        
        return redirect('payment_confirmation', transaction_id=payment.transaction_id)
    
    return render(request, 'payments/initiate_payment.html', {'order': order})

@login_required
def payment_confirmation(request, transaction_id):
    """Second step: Show merchant details for manual payment"""
    payment = get_object_or_404(Payment, transaction_id=transaction_id, user=request.user)
    
    context = {
        'payment': payment,
        'merchant_phone_formatted': payment.merchant_phone,
        'merchant_name': payment.merchant_name,
    }
    return render(request, 'payments/payment_confirmation.html', context)

@login_required
@require_POST
def check_payment_status(request, transaction_id):
    """Check if payment has been completed (AJAX endpoint)"""
    payment = get_object_or_404(Payment, transaction_id=transaction_id, user=request.user)
    
    # For manual payments, you would typically:
    # 1. Check with mobile money API if payment was received
    # 2. Or manually verify and update in admin panel
    # 3. For now, we'll simulate checking
    
    # TODO: Integrate with Flutterwave or mobile money API here
    # For now, just return current status
    
    return JsonResponse({
        'status': payment.status,
        'amount_paid': float(payment.amount_paid),
        'is_complete': payment.status == 'completed'
    })

@login_required
def payment_success(request, transaction_id):
    """Payment success page"""
    payment = get_object_or_404(Payment, transaction_id=transaction_id, user=request.user)
    return render(request, 'payments/payment_success.html', {'payment': payment})
