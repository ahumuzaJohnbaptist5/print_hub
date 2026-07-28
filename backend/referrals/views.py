from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import Referral, ReferralCode, ReferralBonus
from .utils import generate_referral_link, apply_referral_discount
from orders.models import Order

@login_required
def referral_dashboard(request):
    """User's referral dashboard"""
    user = request.user
    
    # Get or create referral code
    code = ReferralCode.get_or_create_for_user(user)
    referral_link = generate_referral_link(user)
    
    # Get referral stats
    referrals = Referral.objects.filter(referrer=user)
    
    stats = {
        'total_referrals': referrals.count(),
        'registered': referrals.filter(status='registered').count(),
        'completed': referrals.filter(status='completed').count(),
        'pending': referrals.filter(status='pending').count(),
    }
    
    # Get bonus stats
    bonuses = ReferralBonus.objects.filter(user=user)
    bonus_stats = bonuses.aggregate(
        total_earned=Sum('amount'),
        total_used=Sum('amount', filter=Q(is_used=True)),
        total_available=Sum('amount', filter=Q(is_used=False)),
        bonus_count=Count('id'),
    )
    
    # Recent referrals
    recent_referrals = referrals.select_related('referee').order_by('-created_at')[:10]
    
    # Recent bonuses
    recent_bonuses = bonuses.order_by('-created_at')[:10]
    
    # Orders using referral discounts
    discount_orders = Order.objects.filter(
        client=user,
        referral_discount_applied__gt=0
    ).order_by('-created_at')[:10]
    
    return render(request, 'referrals/dashboard.html', {
        'referral_code': code.code,
        'referral_link': referral_link,
        'stats': stats,
        'recent_referrals': recent_referrals,
        'recent_bonuses': recent_bonuses,
        'bonus_stats': bonus_stats,
        'discount_orders': discount_orders,
    })

@login_required
def referral_invite(request):
    """Send referral invites via WhatsApp/Email"""
    user = request.user
    referral_link = generate_referral_link(user)
    
    if request.method == 'POST':
        invite_method = request.POST.get('method')
        recipient = request.POST.get('recipient')
        custom_message = request.POST.get('message', '')
        
        if not recipient:
            messages.error(request, 'Please enter a recipient.')
            return redirect('referral_invite')
        
        # Send invite based on method
        if invite_method == 'whatsapp':
            from whatsapp_bot.views import send_whatsapp_message
            message = custom_message or f"🎉 Hey! Join PrintHub using my referral code and get discounts on printing!\n\n"
            message += f"🔗 Use my link: {referral_link}\n"
            message += f"📱 Use code: {user.referral_code.code}\n\n"
            message += "You'll get a welcome bonus! 💰"
            
            try:
                send_whatsapp_message(recipient, message)
                messages.success(request, f'WhatsApp invite sent to {recipient}!')
            except Exception as e:
                messages.error(request, f'Failed to send WhatsApp message: {str(e)}')
        
        elif invite_method == 'email':
            # Send email invite
            subject = "Join PrintHub - Get Printing Discounts!"
            message = custom_message or f"Hi!\n\n"
            message += f"Join PrintHub using my referral code and get discounts on printing.\n\n"
            message += f"🔗 Referral Link: {referral_link}\n"
            message += f"📱 Referral Code: {user.referral_code.code}\n\n"
            message += "You'll get a welcome bonus! 💰\n\n"
            message += "PrintHub - Kabale University Printing Service"
            
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=False
                )
                messages.success(request, f'Email invite sent to {recipient}!')
            except Exception as e:
                messages.error(request, f'Failed to send email: {str(e)}')
        
        elif invite_method == 'copy':
            messages.info(request, f'Referral link copied to clipboard!')
        
        return redirect('referral_dashboard')
    
    return render(request, 'referrals/invite.html', {
        'referral_link': referral_link,
        'referral_code': ReferralCode.get_or_create_for_user(user).code,
    })

@login_required
def referral_history(request):
    """Detailed referral history"""
    user = request.user
    status_filter = request.GET.get('status', '')
    
    referrals = Referral.objects.filter(referrer=user).select_related('referee')
    
    if status_filter:
        referrals = referrals.filter(status=status_filter)
    
    paginator = Paginator(referrals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'referrals/referral_history.html', {
        'page_obj': page_obj,
        'referrals': page_obj.object_list,
        'status_filter': status_filter,
        'status_choices': Referral.STATUS_CHOICES,
    })

@login_required
def referral_stats_api(request):
    """API endpoint for referral stats"""
    user = request.user
    
    referrals = Referral.objects.filter(referrer=user)
    bonuses = ReferralBonus.objects.filter(user=user)
    
    data = {
        'stats': {
            'total_referrals': referrals.count(),
            'registered': referrals.filter(status='registered').count(),
            'completed': referrals.filter(status='completed').count(),
            'pending': referrals.filter(status='pending').count(),
        },
        'bonuses': {
            'total_earned': str(bonuses.aggregate(total=Sum('amount'))['total'] or 0),
            'total_used': str(bonuses.filter(is_used=True).aggregate(total=Sum('amount'))['total'] or 0),
            'available': str(bonuses.filter(is_used=False).aggregate(total=Sum('amount'))['total'] or 0),
        },
        'referral_code': ReferralCode.get_or_create_for_user(user).code,
        'referral_link': generate_referral_link(user),
    }
    
    return JsonResponse(data)

@login_required
@login_required
def apply_referral_discount_view(request):
    """API endpoint to apply referral discount to order"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    order_id = request.POST.get('order_id')
    if not order_id:
        return JsonResponse({'error': 'Order ID required'}, status=400)
    
    try:
        order = Order.objects.get(id=order_id, client=request.user)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    
    # Apply referral discount
    discount_amount, used_bonuses = apply_referral_discount(order.total_price, request.user)
    
    if discount_amount > 0:
        # Update order
        order.referral_discount_applied = discount_amount
        order.total_price -= discount_amount
        order.save()
        
        return JsonResponse({
            'success': True,
            'discount_applied': float(discount_amount),
            'new_total': float(order.total_price),
            'bonuses_used': len(used_bonuses),
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'No valid referral bonuses available.',
        })
