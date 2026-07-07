from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from orders.models import Order

User = get_user_model()

class PaperInventory(models.Model):
    """Track paper inventory and costs"""
    paper_type = models.CharField(max_length=50, default='A4 White')
    quantity = models.IntegerField(help_text="Number of sheets in stock")
    cost_per_sheet = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per sheet in UGX")
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Paper Inventory"
    
    def __str__(self):
        return f"{self.paper_type} - {self.quantity} sheets"
    
    def total_value(self):
        return self.quantity * self.cost_per_sheet


class CommissionRate(models.Model):
    """Commission rates set by admin for agents"""
    rate_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        help_text="Commission percentage (e.g., 10.00 for 10%)"
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.rate_percentage}% Commission Rate"
    
    @classmethod
    def get_active_rate(cls):
        """Get the currently active commission rate"""
        return cls.objects.filter(is_active=True).first()


class FinancialRecord(models.Model):
    """Track all financial transactions"""
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('commission', 'Commission Paid'),
    ]
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=500)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_records')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_earnings')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - UGX {self.amount}"


class AgentEarning(models.Model):
    """Track agent earnings from completed orders"""
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='earnings')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='agent_earnings')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.agent.username} - UGX {self.commission_amount} (Order #{self.order.id})"
    
    def calculate_commission(self):
        """Calculate commission based on order total and commission rate"""
        rate = CommissionRate.get_active_rate()
        if rate:
            self.commission_rate = rate.rate_percentage
            self.commission_amount = (self.order_total * rate.rate_percentage) / 100
        return self.commission_amount
