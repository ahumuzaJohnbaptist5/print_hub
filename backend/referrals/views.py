from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from .models import Referral, ReferralCode, ReferralBonus
from .utils import generate_referral_link

@login_required
def referral_dashboard(request):
    user = request.user
    code = ReferralCode.get_or_create_for_user(user)
    referral_link = generate_referral_link(user)
    
    referrals = Referral.objects.filter(referrer=user)
    
    stats = {
        'total_referrals': referrals.count(),
        'registered': referrals.filter(status='registered').count(),
        'completed': referrals.filter(status='completed').count(),
        'pending': referrals.filter(status='pending').count(),
    }
    
    bonuses = ReferralBonus.objects.filter(user=user)
    bonus_stats = bonuses.aggregate(
        total_earned=Sum('amount'),
        total_used=Sum('amount', filter=Q(is_used=True)),
        total_available=Sum('amount', filter=Q(is_used=False)),
        bonus_count=Sum('id'),
    )
    
    recent_referrals = referrals.select_related('referee').order_by('-created_at')[:10]
    recent_bonuses = bonuses.order_by('-created_at')[:10]
    
    return render(request, 'referrals/dashboard.html', {
        'referral_code': code.code,
        'referral_link': referral_link,
        'stats': stats,
        'recent_referrals': recent_referrals,
        'recent_bonuses': recent_bonuses,
        'bonus_stats': bonus_stats,
    })

@login_required
def referral_invite(request):
    user = request.user
    referral_link = generate_referral_link(user)
    code = ReferralCode.get_or_create_for_user(user)
    
    if request.method == 'POST':
        method = request.POST.get('method')
        recipient = request.POST.get('recipient')
        message = request.POST.get('message', '')
        
        if method == 'copy':
            messages.success(request, 'Referral link copied to clipboard!')
        
        return redirect('referrals:dashboard')
    
    return render(request, 'referrals/invite.html', {
        'referral_link': referral_link,
        'referral_code': code.code,
    })

@login_required
def referral_history(request):
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
