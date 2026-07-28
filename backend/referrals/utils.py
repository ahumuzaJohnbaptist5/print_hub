from django.conf import settings
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

REFERRAL_BONUS_AMOUNT = getattr(settings, 'REFERRAL_BONUS_AMOUNT', Decimal('5000'))
REFERRAL_ORDER_BONUS = getattr(settings, 'REFERRAL_ORDER_BONUS', Decimal('1000'))

def generate_referral_link(user):
    """Generate full referral link for a user"""
    from .models import ReferralCode
    code = ReferralCode.get_or_create_for_user(user)
    return f"{settings.SITE_URL}/auth/register/?ref={code.code}"

def get_referral_code_from_request(request):
    """Extract referral code from request"""
    return request.GET.get('ref') or request.POST.get('referral_code')

def process_referral_signup(request, user):
    """Process referral when a new user signs up"""
    from .models import Referral, ReferralCode
    
    code = get_referral_code_from_request(request)
    if not code:
        return None
    
    try:
        referral_code = ReferralCode.objects.get(code=code, is_active=True)
    except ReferralCode.DoesNotExist:
        return None
    
    # Don't allow self-referral
    if referral_code.user == user:
        return None
    
    # Check if already referred
    if Referral.objects.filter(referee=user).exists():
        return None
    
    # Create referral
    referral = Referral.objects.create(
        referrer=referral_code.user,
        referee=user,
        referral_code=referral_code,
        status='registered',
        expires_at=timezone.now() + timezone.timedelta(days=30)
    )
    
    # Send notification to referrer
    send_referral_notification(referral)
    
    return referral

def award_referral_bonus(referrer, referee):
    """Award bonus to referrer when referee completes an order"""
    from .models import ReferralBonus
    
    # Create bonus for referrer
    ReferralBonus.objects.create(
        user=referrer,
        bonus_type='referral',
        amount=REFERRAL_BONUS_AMOUNT,
        description=f'Referral bonus for {referee.username} completing their first order',
        expires_at=timezone.now() + timezone.timedelta(days=90)
    )
    
    # Also give the referee a bonus for signing up
    ReferralBonus.objects.create(
        user=referee,
        bonus_type='referral',
        amount=REFERRAL_BONUS_AMOUNT / 2,
        description=f'Welcome bonus for joining through {referrer.username}',
        expires_at=timezone.now() + timezone.timedelta(days=90)
    )
    
    # Send notifications
    send_bonus_notification(referrer, referee)

def send_referral_notification(referral):
    """Send notification when someone uses a referral code"""
    from notifications.models import Notification
    Notification.create_notification(
        user=referral.referrer,
        notification_type='referral',
        title='Someone Used Your Referral Code!',
        message=f'{referral.referee.username} signed up using your referral code!',
        link='/referrals/dashboard/'
    )

def send_bonus_notification(referrer, referee):
    """Send notification when bonus is awarded"""
    from notifications.models import Notification
    
    # Notify referrer
    Notification.create_notification(
        user=referrer,
        notification_type='bonus_earned',
        title='Referral Bonus Earned!',
        message=f'You earned {REFERRAL_BONUS_AMOUNT} UGX when {referee.username} completed their first order!',
        link='/referrals/dashboard/'
    )
    
    # Notify referee
    Notification.create_notification(
        user=referee,
        notification_type='bonus_earned',
        title='Welcome Bonus!',
        message=f'You earned {REFERRAL_BONUS_AMOUNT / 2} UGX for joining through {referrer.username}!',
        link='/referrals/dashboard/'
    )

def apply_referral_discount(order_total, user):
    """Apply referral discount to an order"""
    from .models import ReferralBonus
    
    # Check if user has any valid bonuses
    bonuses = ReferralBonus.objects.filter(
        user=user,
        is_used=False,
        expires_at__gt=timezone.now()
    ).order_by('created_at')
    
    total_discount = Decimal('0')
    used_bonuses = []
    
    for bonus in bonuses:
        if total_discount >= order_total:
            break
        remaining = order_total - total_discount
        if bonus.amount <= remaining:
            total_discount += bonus.amount
            bonus.is_used = True
            bonus.used_at = timezone.now()
            bonus.save()
            used_bonuses.append(bonus)
        else:
            # Split the bonus
            split_amount = remaining
            total_discount += split_amount
            bonus.amount -= split_amount
            bonus.save()
    
    return total_discount, used_bonuses
