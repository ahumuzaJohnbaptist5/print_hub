import math
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils import timezone


class SystemSettings(models.Model):
    """Singleton model to store global system state like pause timers."""
    is_paused = models.BooleanField(default=False)
    pause_reason = models.CharField(max_length=255, blank=True, default='')
    total_paused_seconds = models.FloatField(default=0.0)
    pause_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
        
    def get_current_paused_seconds(self):
        total = self.total_paused_seconds
        if self.is_paused and self.pause_started_at:
            total += (timezone.now() - self.pause_started_at).total_seconds()
        return total


class DeliveryZone(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., Main Campus, City Center")
    description = models.CharField(max_length=255, blank=True, null=True)
    delivery_fee = models.IntegerField(default=0, help_text="Delivery fee in UGX")
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.delivery_fee:,} UGX)"


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('printing', 'Printing'),
        ('in_transit', 'In Transit'),
        ('ready', 'Ready for Pickup'),
        ('collected', 'Collected'),
        ('cancelled', 'Cancelled'),
    )

    DELIVERY_TYPE_CHOICES = (
        ('pickup', 'Pickup at Station'),
        ('delivery', 'Deliver to Me'),
    )

    BINDING_CHOICES = (
        ('none', 'No Binding'),
        ('staple', 'Staple (Corner)'),
        ('spiral', 'Spiral Binding'),
    )

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    station = models.ForeignKey('stations.Station', on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='print_files/')
    file_name = models.CharField(max_length=255)
    page_count = models.IntegerField()
    is_color = models.BooleanField(default=False)
    is_double_sided = models.BooleanField(default=False)

    binding = models.CharField(max_length=20, choices=BINDING_CHOICES, default='none')
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES, default='pickup')
    delivery_zone = models.ForeignKey(DeliveryZone, on_delete=models.SET_NULL, null=True, blank=True)

    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    tx_ref = models.CharField(max_length=100, blank=True, null=True)
    
    paid_at = models.DateTimeField(blank=True, null=True)
    printing_at = models.DateTimeField(blank=True, null=True)
    in_transit_at = models.DateTimeField(blank=True, null=True)
    ready_at = models.DateTimeField(blank=True, null=True)
    collected_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    sla_minutes = models.IntegerField(default=120, help_text="Target time to complete order in minutes.")
    postponed_minutes = models.IntegerField(default=0, help_text="Extra minutes added if the order is postponed.")

    paper_used = models.IntegerField(default=0, help_text="Number of physical sheets consumed")
    cost_of_goods = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Cost of paper used")
    agent_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Commission paid to agent")
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Net profit for this order")

    notes = models.TextField(blank=True, default='', help_text="Internal notes about this order")
    
    cancellation_reason = models.TextField(blank=True, default='', help_text="Reason for cancellation")
    cancelled_at = models.DateTimeField(blank=True, null=True)

    BASE_PRICE_BW = 200
    COLOR_SURCHARGE = 100
    SPIRAL_BINDING_FEE = 1000

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['station', 'status']),
            models.Index(fields=['client', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    @classmethod
    def compute_price(cls, page_count, is_color=False, is_double_sided=False, binding='none', delivery_fee=0):
        price_per_page = cls.BASE_PRICE_BW + (cls.COLOR_SURCHARGE if is_color else 0)
        effective_pages = page_count
        if is_double_sided:
            effective_pages = math.ceil(page_count / 2)
        printing_cost = price_per_page * effective_pages
        binding_cost = cls.SPIRAL_BINDING_FEE if binding == 'spiral' else 0
        total_price = printing_cost + binding_cost + delivery_fee
        return total_price, effective_pages, price_per_page

    def calculate_price(self):
        delivery_fee = self.delivery_zone.delivery_fee if self.delivery_zone and self.delivery_type == 'delivery' else 0
        total, effective_pages, price_per_page = self.compute_price(
            self.page_count, self.is_color, self.is_double_sided, self.binding, delivery_fee
        )
        self.total_price = Decimal(str(total))
        return self.total_price, effective_pages, price_per_page

    def calculate_financials(self):
        _, effective_pages, _ = self.compute_price(
            self.page_count, self.is_color, self.is_double_sided, self.binding
        )
        self.paper_used = effective_pages

        try:
            from finances.models import PaperInventory
            paper = PaperInventory.objects.first()
            self.cost_of_goods = Decimal(str(effective_pages * paper.cost_per_sheet)) if paper else Decimal('0.00')
        except Exception:
            self.cost_of_goods = Decimal('0.00')

        try:
            from finances.models import CommissionRate
            rate = CommissionRate.get_active_rate()
            self.agent_commission = (self.total_price * Decimal(str(rate.rate_percentage))) / Decimal('100') if rate else Decimal('0.00')
        except Exception:
            self.agent_commission = Decimal('0.00')

        self.profit = self.total_price - self.cost_of_goods - self.agent_commission
        return self.profit

    def deduct_paper_inventory(self):
        if self.status == 'printing' and self.paper_used > 0:
            try:
                from finances.models import PaperInventory
                paper = PaperInventory.objects.first()
                if paper and paper.quantity >= self.paper_used:
                    paper.quantity -= self.paper_used
                    paper.save(update_fields=['quantity'])
                    return True
            except Exception:
                pass
        return False

    def estimated_ready_at(self):
        if self.paid_at:
            total_minutes = self.sla_minutes + self.postponed_minutes
            return self.paid_at + timedelta(minutes=total_minutes)
        return None

    @property
    def is_overdue(self):
        if self.status in ['collected', 'cancelled']:
            return False
        estimated = self.estimated_ready_at()
        if estimated:
            return timezone.now() > estimated
        return False

    @property
    def priority_info(self):
        if self.status == 'cancelled':
            return {
                'level': 'cancelled', 'display': 'CANCELLED',
                'remaining_seconds': 0, 'time_display': '--:--:--', 'is_overdue': False
            }

        start_time = self.paid_at or self.created_at
        total_minutes = self.sla_minutes + self.postponed_minutes
        deadline = start_time + timedelta(minutes=total_minutes)
        now = timezone.now()
        
        try:
            sys_settings = SystemSettings.load()
            paused_seconds = sys_settings.get_current_paused_seconds()
        except Exception:
            paused_seconds = 0
            
        effective_deadline = deadline + timedelta(seconds=paused_seconds)
        remaining_td = effective_deadline - now
        remaining_seconds = max(0, int(remaining_td.total_seconds()))
        is_overdue = now > effective_deadline
        is_postponed = self.postponed_minutes > 0
        
        if is_postponed:
            level, display = 'postponed', 'POSTPONED'
        elif is_overdue:
            level, display = 'overdue', 'OVERDUE'
        elif remaining_seconds < 600:
            level, display = 'critical', 'CRITICAL'
        elif remaining_seconds < 1800:
            level, display = 'urgent', 'URGENT'
        elif remaining_seconds < 3600:
            level, display = 'high', 'HIGH'
        else:
            level, display = 'normal', 'NORMAL'
            
        hours, remainder = divmod(remaining_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return {
            'level': level, 'display': display,
            'remaining_seconds': remaining_seconds,
            'time_display': time_display, 'is_overdue': is_overdue
        }

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        
        if is_new or not self.total_price:
            self.calculate_price()
        
        if not is_new:
            try:
                old_instance = Order.objects.get(pk=self.pk)
                self._old_status = old_instance.status
            except Order.DoesNotExist:
                self._old_status = None
        else:
            self._old_status = None
        
        if self.status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = timezone.now()
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} by {self.client.username}"
