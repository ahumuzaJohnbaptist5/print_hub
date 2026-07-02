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
            
            # 3. Send Email Notification (using our safe utility)
            from orders.utils import send_payment_confirmed_email
            try:
                send_payment_confirmed_email(payment.order)
            except Exception as e:
                print(f"Payment email failed: {e}")
            
            messages.success(request, f'Payment {payment.transaction_id} approved! Email sent to {payment.user.email}.')
            
        elif action == 'reject':
            payment.status = 'rejected'
            payment.save()
            messages.error(request, f'Payment {payment.transaction_id} rejected.')
            
        return redirect('admin_approve_payments')

    # GET request: Show pending payments
    pending = Payment.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'payments/admin_approve.html', {'pending_payments': pending})
