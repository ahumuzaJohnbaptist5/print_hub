from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class PaperInventory(models.Model):
    """Track paper inventory and costs"""
    PAPER_TYPES = [
        ('A4_white', 'A4 White (80gsm)'),
        ('A4_colored', 'A4 Colored'),
        ('A3_white', 'A3 White (80gsm)'),
        ('A3_colored', 'A3 Colored'),
        ('legal', 'Legal Size'),
        ('photo', 'Photo Paper'),
    ]
    
    paper_type = models.CharField(max_length=50, choices=PAPER_TYPES, default='A4_white')
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of sheets in stock"
    )
    cost_per_sheet = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Cost per sheet in UGX"
    )
    low_stock_threshold = models.IntegerField(
        default=500,
        help_text="Alert when stock falls below this number"
    )
    last_updated = models.DateTimeField(auto_now=True)
    last_restocked_at = models.DateTimeField(null=True, blank=True)
    last_restocked_quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Paper Inventory"
        ordering = ['paper_type']
    
    def __str__(self):
        return f"{self.get_paper_type_display()} - {self.quantity} sheets"
    
    def total_value(self):
        """Calculate total value of this inventory item."""
        return self.quantity * self.cost_per_sheet
    
    @property
    def is_low_stock(self):
        """Check if stock is below threshold."""
        return self.quantity <= self.low_stock_threshold
    
    @property
    def stock_status(self):
        """Get stock status for display."""
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.is_low_stock:
            return 'low_stock'
        return 'in_stock'
    
    def restock(self, quantity, cost_per_sheet=None):
        """Add stock and optionally update cost."""
        if cost_per_sheet:
            self.cost_per_sheet = cost_per_sheet
        self.quantity += quantity
        self.last_restocked_at = timezone.now()
        self.last_restocked_quantity = quantity
        self.save()
    
    def deduct(self, quantity):
        """Deduct sheets from inventory. Returns False if insufficient stock."""
        if self.quantity >= quantity:
            self.quantity -= quantity
            self.save(update_fields=['quantity'])
            return True
        return False


class CommissionRate(models.Model):
    """Commission rates set by admin for agents"""
    rate_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Commission percentage (e.g., 10.00 for 10%)"
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_commission_rates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Commission Rate"
        verbose_name_plural = "Commission Rates"
    
    def __str__(self):
        return f"{self.rate_percentage}% - {'Active' if self.is_active else 'Inactive'}"
    
    @classmethod
    def get_active_rate(cls):
        """Get the currently active commission rate."""
        return cls.objects.filter(is_active=True).order_by('-created_at').first()
    
    def save(self, *args, **kwargs):
        """Ensure only one active rate when activating a new one."""
        if self.is_active:
            # Deactivate all other rates
            CommissionRate.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class FinancialRecord(models.Model):
    """Track all financial transactions"""
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('commission', 'Commission Paid'),
        ('refund', 'Refund'),
        ('paper_purchase', 'Paper Purchase'),
        ('other', 'Other'),
    ]
    
    EXPENSE_CATEGORIES = [
        ('paper', 'Paper & Supplies'),
        ('toner', 'Toner & Ink'),
        ('maintenance', 'Equipment Maintenance'),
        ('rent', 'Rent'),
        ('utilities', 'Utilities'),
        ('salary', 'Salaries'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    ]
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=500)
    category = models.CharField(
        max_length=20, 
        choices=EXPENSE_CATEGORIES, 
        default='other',
        help_text="Expense category (for expenses only)"
    )
    order = models.ForeignKey(
        'orders.Order', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='financial_records'
    )
    agent = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='agent_financial_records'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_financial_records'
    )
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_type', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['order']),
            models.Index(fields=['agent']),
        ]
        verbose_name = "Financial Record"
        verbose_name_plural = "Financial Records"
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - UGX {self.amount:,.0f}"
    
    @property
    def is_expense(self):
        """Check if this is an expense transaction."""
        return self.transaction_type in ['expense', 'paper_purchase', 'refund']
    
    @property
    def is_income(self):
        """Check if this is an income transaction."""
        return self.transaction_type == 'income'
    
    @classmethod
    def get_income_summary(cls, start_date=None, end_date=None):
        """Get income summary for a period."""
        qs = cls.objects.filter(transaction_type='income')
        if start_date:
            qs = qs.filter(created_at__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__lte=end_date)
        return qs.aggregate(
            total=models.Sum('amount'),
            count=models.Count('id')
        )
    
    @classmethod
    def get_expense_summary(cls, start_date=None, end_date=None):
        """Get expense summary grouped by category."""
        qs = cls.objects.filter(is_expense=True)
        if start_date:
            qs = qs.filter(created_at__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__lte=end_date)
        return qs.values('category').annotate(
            total=models.Sum('amount'),
            count=models.Count('id')
        ).order_by('-total')
    
    @classmethod
    def get_profit_loss(cls, start_date=None, end_date=None):
        """Calculate profit/loss for a period."""
        income = cls.objects.filter(transaction_type='income')
        expenses = cls.objects.filter(transaction_type__in=['expense', 'paper_purchase', 'refund', 'commission'])
        
        if start_date:
            income = income.filter(created_at__gte=start_date)
            expenses = expenses.filter(created_at__gte=start_date)
        if end_date:
            income = income.filter(created_at__lte=end_date)
            expenses = expenses.filter(created_at__lte=end_date)
        
        total_income = income.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        total_expenses = expenses.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'profit': total_income - total_expenses,
            'profit_margin': ((total_income - total_expenses) / total_income * 100) if total_income > 0 else Decimal('0.00')
        }


class AgentEarning(models.Model):
    """Track agent earnings from completed orders"""
    EARNING_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='earnings')
    order = models.ForeignKey(
        'orders.Order', 
        on_delete=models.CASCADE, 
        related_name='agent_earnings'
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, 
        choices=EARNING_STATUS, 
        default='pending'
    )
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='paid_earnings'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', 'is_paid']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
        verbose_name = "Agent Earning"
        verbose_name_plural = "Agent Earnings"
    
    def __str__(self):
        return f"{self.agent.username} - UGX {self.commission_amount:,.0f} (Order #{self.order.id})"
    
    def mark_as_paid(self, paid_by=None):
        """Mark this earning as paid."""
        self.is_paid = True
        self.status = 'paid'
        self.paid_at = timezone.now()
        if paid_by:
            self.paid_by = paid_by
        self.save()
    
    def mark_as_cancelled(self, notes=''):
        """Mark this earning as cancelled."""
        self.is_paid = False
        self.status = 'cancelled'
        self.notes = notes
        self.save()
    
    @classmethod
    def calculate_commission(cls, order_total, commission_rate=None):
        """Calculate commission amount based on order total."""
        if commission_rate is None:
            rate = CommissionRate.get_active_rate()
            commission_rate = rate.rate_percentage if rate else Decimal('0.00')
        return (order_total * commission_rate) / Decimal('100.00')
    
    @classmethod
    def get_agent_summary(cls, agent, start_date=None, end_date=None):
        """Get earnings summary for an agent."""
        qs = cls.objects.filter(agent=agent)
        if start_date:
            qs = qs.filter(created_at__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__lte=end_date)
        
        return qs.aggregate(
            total_earned=models.Sum('commission_amount'),
            total_paid=models.Sum('commission_amount', filter=models.Q(is_paid=True)),
            total_pending=models.Sum('commission_amount', filter=models.Q(is_paid=False)),
            orders_count=models.Count('id')
        )
    
    @classmethod
    def get_top_agents(cls, limit=10, start_date=None, end_date=None):
        """Get top performing agents by earnings."""
        qs = cls.objects.values(
            'agent__username', 
            'agent__first_name', 
            'agent__last_name'
        )
        if start_date:
            qs = qs.filter(created_at__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__lte=end_date)
        
        return qs.annotate(
            total_earnings=models.Sum('commission_amount'),
            orders_count=models.Count('id'),
            avg_commission=models.Avg('commission_amount')
        ).order_by('-total_earnings')[:limit]


class DiscountCode(models.Model):
    """Discount codes for promotions"""
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Minimum order total to apply discount"
    )
    max_uses = models.IntegerField(default=0, help_text="0 for unlimited")
    used_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    description = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Discount Code"
        verbose_name_plural = "Discount Codes"
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"
    
    @property
    def is_valid(self):
        """Check if discount code is currently valid."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    def apply_discount(self, order_total):
        """Calculate discounted amount."""
        if not self.is_valid or order_total < self.minimum_order:
            return order_total
        
        if self.discount_type == 'percentage':
            discount = (order_total * self.discount_value) / Decimal('100.00')
            return max(Decimal('0.00'), order_total - discount)
        else:  # fixed
            return max(Decimal('0.00'), order_total - self.discount_value)
    
    def use(self):
        """Increment usage count."""
        self.used_count += 1
        self.save(update_fields=['used_count'])


class MerchantSettings(models.Model):
    """Payment merchant settings"""
    PAYMENT_METHODS = [
        ('mtn', 'MTN Mobile Money'),
        ('airtel', 'Airtel Money'),
    ]
    
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, unique=True)
    merchant_name = models.CharField(max_length=100)
    merchant_phone = models.CharField(max_length=15)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Merchant Setting"
        verbose_name_plural = "Merchant Settings"
    
    def __str__(self):
        return f"{self.get_payment_method_display()} - {self.merchant_name}"
    
    @classmethod
    def get_merchant(cls, payment_method):
        """Get active merchant for payment method."""
        return cls.objects.filter(
            payment_method=payment_method, 
            is_active=True
        ).first()


class Expense(models.Model):
    """Track business expenses separately from FinancialRecord"""
    EXPENSE_CATEGORIES = [
        ('paper', 'Paper & Supplies'),
        ('toner', 'Toner & Ink'),
        ('maintenance', 'Equipment Maintenance'),
        ('rent', 'Rent'),
        ('utilities', 'Utilities'),
        ('salary', 'Salaries'),
        ('marketing', 'Marketing'),
        ('transport', 'Transport'),
        ('other', 'Other'),
    ]
    
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORIES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=500)
    receipt = models.FileField(upload_to='expenses/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"
    
    def __str__(self):
        return f"{self.get_category_display()} - UGX {self.amount:,.0f}"
    
    def save(self, *args, **kwargs):
        """Also create a FinancialRecord when saving an expense."""
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        if is_new:
            FinancialRecord.objects.create(
                transaction_type='expense',
                amount=self.amount,
                description=self.description,
                category=self.category,
                created_by=self.created_by
            )
