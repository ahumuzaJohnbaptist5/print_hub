from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator, RegexValidator
from orders.models import Order


class Payment(models.Model):
    """Payment records for orders via mobile money."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved/Paid'),
        ('rejected', 'Rejected'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    )
    
    MERCHANT_CHOICES = (
        ('mtn', 'MTN Mobile Money'),
        ('airtel', 'Airtel Money'),
    )
    
    PAYMENT_TYPES = (
        ('full', 'Full Payment'),
        ('partial', 'Partial Payment'),
        ('deposit', 'Deposit'),
    )
    
    # Core fields
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_method = models.CharField(
        max_length=10, 
        choices=MERCHANT_CHOICES
    )
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_TYPES,
        default='full',
        help_text="Whether this is full, partial, or deposit payment"
    )
    
    # Customer details
    customer_phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in format: '0771234567'"
        )]
    )
    customer_name = models.CharField(max_length=100, blank=True)
    
    # Merchant details (now can be null - use MerchantSettings model instead)
    merchant_phone = models.CharField(max_length=15, blank=True)
    merchant_name = models.CharField(max_length=100, blank=True)
    
    # Transaction details
    transaction_id = models.CharField(max_length=100)
    transaction_message = models.TextField(blank=True)
    transaction_reference = models.CharField(
        max_length=100, 
        blank=True,
        help_text="External payment gateway reference"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    status_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection or failure"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Admin tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payments'
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_payments'
    )
    
    # Additional info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes about this payment")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['order']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['payment_method']),
        ]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
    
    def __str__(self):
        return f"Payment #{self.id} - Order #{self.order.id} - {self.get_status_display()}"
    
    @property
    def is_approved(self):
        """Check if payment is approved."""
        return self.status == 'approved'
    
    @property
    def is_pending(self):
        """Check if payment is pending."""
        return self.status == 'pending'
    
    @property
    def is_refunded(self):
        """Check if payment is refunded."""
        return self.status == 'refunded'
    
    @property
    def can_be_approved(self):
        """Check if payment can be approved."""
        return self.status in ['pending']
    
    @property
    def can_be_rejected(self):
        """Check if payment can be rejected."""
        return self.status in ['pending']
    
    @property
    def can_be_refunded(self):
        """Check if payment can be refunded."""
        return self.status in ['approved']
    
    def approve(self, approved_by=None):
        """
        Approve payment and update order status.
        Returns True if successful.
        """
        if not self.can_be_approved:
            return False
        
        now = timezone.now()
        self.status = 'approved'
        self.approved_at = now
        if approved_by:
            self.approved_by = approved_by
        self.save()
        
        # Update order status to 'paid'
        if self.order.status == 'pending':
            self.order.status = 'paid'
            self.order.paid_at = now
            self.order.transaction_id = self.transaction_id
            self.order.save()
        
        # Create financial record
        self._create_income_record()
        
        return True
    
    def reject(self, rejected_by=None, reason=''):
        """
        Reject payment with optional reason.
        Returns True if successful.
        """
        if not self.can_be_rejected:
            return False
        
        self.status = 'rejected'
        self.rejected_at = timezone.now()
        self.status_reason = reason
        if rejected_by:
            self.rejected_by = rejected_by
        self.save()
        
        return True
    
    def mark_as_failed(self, reason=''):
        """Mark payment as failed."""
        self.status = 'failed'
        self.status_reason = reason
        self.save()
        
        return True
    
    def mark_as_expired(self):
        """Mark payment as expired if not completed within timeframe."""
        if self.status == 'pending':
            self.status = 'expired'
            self.status_reason = 'Payment not completed within required timeframe'
            self.save()
            
            # Cancel order if no other approved payments
            if not self.order.payments.filter(status='approved').exists():
                self.order.status = 'cancelled'
                self.order.cancellation_reason = 'Payment expired'
                self.order.cancelled_at = timezone.now()
                self.order.save()
            
            return True
        return False
    
    def refund(self, refunded_by=None, reason=''):
        """
        Process refund for approved payment.
        Returns True if successful.
        """
        if not self.can_be_refunded:
            return False
        
        self.status = 'refunded'
        self.refunded_at = timezone.now()
        self.status_reason = reason
        self.save()
        
        # Create refund record
        self._create_refund_record(refunded_by)
        
        return True
    
    def _create_income_record(self):
        """Create financial record for approved payment."""
        try:
            from finances.models import FinancialRecord
            FinancialRecord.objects.create(
                transaction_type='income',
                amount=self.amount,
                description=f'Payment for Order #{self.order.id} - {self.order.file_name}',
                order=self.order,
                notes=f'Payment ID: {self.id}, Transaction: {self.transaction_id}'
            )
        except Exception:
            pass  # Don't break payment approval if record creation fails
    
    def _create_refund_record(self, refunded_by=None):
        """Create financial record for refund."""
        try:
            from finances.models import FinancialRecord
            FinancialRecord.objects.create(
                transaction_type='refund',
                amount=self.amount,
                description=f'Refund for Order #{self.order.id} - {self.order.file_name}',
                order=self.order,
                created_by=refunded_by,
                notes=f'Refund for Payment ID: {self.id}, Transaction: {self.transaction_id}'
            )
        except Exception:
            pass
    
    def get_merchant_details(self):
        """Get merchant details from MerchantSettings if available."""
        try:
            from finances.models import MerchantSettings
            merchant = MerchantSettings.get_merchant(self.payment_method)
            if merchant:
                return {
                    'phone': merchant.merchant_phone,
                    'name': merchant.merchant_name,
                }
        except Exception:
            pass
        
        # Fallback to stored values
        return {
            'phone': self.merchant_phone,
            'name': self.merchant_name,
        }
    
    @classmethod
    def get_pending_count(cls):
        """Get count of pending payments."""
        return cls.objects.filter(status='pending').count()
    
    @classmethod
    def get_today_summary(cls):
        """Get today's payment summary."""
        today = timezone.now().date()
        payments = cls.objects.filter(created_at__date=today)
        
        return payments.aggregate(
            total_amount=models.Sum('amount'),
            total_count=models.Count('id'),
            approved_count=models.Count('id', filter=models.Q(status='approved')),
            pending_count=models.Count('id', filter=models.Q(status='pending')),
            rejected_count=models.Count('id', filter=models.Q(status='rejected')),
        )
    
    @classmethod
    def get_success_rate(cls, days=30):
        """Get payment success rate for the last N days."""
        start_date = timezone.now() - timezone.timedelta(days=days)
        payments = cls.objects.filter(created_at__gte=start_date)
        
        total = payments.count()
        approved = payments.filter(status='approved').count()
        
        if total > 0:
            return (approved / total) * 100
        return 0


class PaymentReminder(models.Model):
    """Track payment reminders sent to users."""
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payment_reminders'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_reminders'
    )
    reminder_type = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('sms', 'SMS'),
            ('push', 'Push Notification'),
        ]
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = "Payment Reminder"
        verbose_name_plural = "Payment Reminders"
    
    def __str__(self):
        return f"Reminder for Order #{self.order.id} - {self.reminder_type}"
    
    def mark_as_read(self):
        """Mark reminder as read."""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


class PaymentMethod(models.Model):
    """User's saved payment methods for faster checkout."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_payment_methods'
    )
    payment_type = models.CharField(
        max_length=10,
        choices=Payment.MERCHANT_CHOICES
    )
    phone_number = models.CharField(max_length=15)
    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
        unique_together = ['user', 'phone_number']
        verbose_name = "Saved Payment Method"
        verbose_name_plural = "Saved Payment Methods"
    
    def __str__(self):
        return f"{self.user.username} - {self.get_payment_type_display()}: {self.phone_number}"
    
    def save(self, *args, **kwargs):
        """Ensure only one default payment method per user."""
        if self.is_default:
            # Remove default from other methods
            PaymentMethod.objects.filter(
                user=self.user, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def verify(self):
        """Mark payment method as verified."""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'verified_at'])


class PaymentWebhookLog(models.Model):
    """Log payment webhook calls from payment providers."""
    
    provider = models.CharField(
        max_length=20,
        choices=[
            ('mtn', 'MTN Mobile Money'),
            ('airtel', 'Airtel Money'),
            ('flutterwave', 'Flutterwave'),
            ('other', 'Other'),
        ]
    )
    event_type = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payment Webhook Log"
        verbose_name_plural = "Payment Webhook Logs"
    
    def __str__(self):
        return f"{self.provider} - {self.event_type} - {self.created_at}"
    
    def mark_as_processed(self):
        """Mark webhook as successfully processed."""
        self.is_processed = True
        self.save(update_fields=['is_processed'])
    
    def mark_as_failed(self, error_message):
        """Mark webhook as failed with error."""
        self.is_processed = False
        self.error_message = error_message
        self.save(update_fields=['is_processed', 'error_message'])
