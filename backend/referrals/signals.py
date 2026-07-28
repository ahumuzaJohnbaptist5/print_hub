from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import ReferralCode

User = get_user_model()

@receiver(post_save, sender=User)
def create_referral_code(sender, instance, created, **kwargs):
    """Auto-generate referral code when a new user is created"""
    if created:
        ReferralCode.get_or_create_for_user(instance)
