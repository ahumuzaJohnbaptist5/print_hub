import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class ReferralCode(models.Model):
    """Unique referral code for each user"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_code'
    )
    code = models.CharField(max_length=20, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.code}"
    
    @classmethod
    def generate_code(cls, user):
        """Generate a unique referral code for a user"""
        # Use username + random suffix
        base = user.username[:4].upper()
        suffix = str(uuid.uuid4())[:6].upper()
        code = f"{base}{suffix}"
        
        # Ensure uniqueness
        while cls.objects.filter(code=code).exists():
            suffix = str(uuid.uuid4())[:6].upper()
            code = f"{base}{suffix}"
        
        return code
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get existing referral code or create one"""
        code, created = cls.objects.get_or_create(
            user=user,
            defaults={'code': cls.generate_code(user)}
        )
        return code


class Referral(models.Model):
    """Track referrals between users"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('registered', 'Registered'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    )
    
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_users'
    )
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_by'
    )
    referral_code = models.ForeignKey(
        ReferralCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['referrer', 'referee']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['referrer', 'status']),
        ]
    
    def __str__(self):
        return f"{self.referrer.username} -> {self.referee.username} ({self.status})"
    
    def mark_completed(self):
        """Mark referral as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        
        # Award bonus to referrer
        from referrals.utils import award_referral_bonus
        award_referral_bonus(self.referrer, self.referee)
    
    def is_expired(self):
        """Check if referral has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class ReferralBonus(models.Model):
    """Track referral bonuses earned"""
    BONUS_TYPES = (
        ('referral', 'Referral Bonus'),
        ('order', 'Order Bonus'),
        ('promotion', 'Promotion Bonus'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_bonuses'
    )
    referral = models.ForeignKey(
        Referral,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bonuses'
    )
    bonus_type = models.CharField(max_length=20, choices=BONUS_TYPES, default='referral')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    description = models.CharField(max_length=255)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} UGX ({self.bonus_type})"
    
    def use_bonus(self):
        """Mark bonus as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    @property
    def is_valid(self):
        """Check if bonus is still valid"""
        if self.is_used:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
