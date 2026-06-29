from django.db import models
from django.conf import settings
from django.utils import timezone
from orders.models import Order
import uuid

class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    MERCHANT_CHOICES = (
        ('mtn', 'MTN Mobile Money'),
        ('airtel', 'Airtel Money'),
    )
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=MERCHANT_CHOICES)
    customer_phone = models.CharField(max_length=15)
    merchant_phone = models.CharField(max_length=15)
    merchant_name = models.CharField(max_length=100)
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment for Order #{self.order.id} - {self.amount} UGX"
