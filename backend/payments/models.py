from django.db import models
from django.conf import settings
from orders.models import Order
from django.utils import timezone

class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved/Paid'),
        ('rejected', 'Rejected'),
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
    transaction_id = models.CharField(max_length=100)
    transaction_message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Payment for Order #{self.order.id} - {self.status}"
