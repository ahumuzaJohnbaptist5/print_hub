import math
from datetime import timedelta

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

    def __str__(self):
        return f"{self.name} ({self.delivery_fee:,} UGX)"


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('printing', 'Printing'),
        ('in_transit', 'In Transit'), # <--- NEW STATUS
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

    total_price = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    tx_ref = models.CharField(max_length=100, blank=True, null=True)
    
    paid_at = models.DateTimeField(blank=True, null=True)
    printing_at = models.DateTimeField(blank=True, null=True)
    in_transit_at = models.DateTimeField(blank=True, null=True) # <--- NEW TIMESTAMP
    ready_at = models.DateTimeField(blank=True, null=True)
    collected_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    sla_minutes = models.IntegerField(default=120, help_text="Target time to complete order in minutes.")
    postponed_minutes = models.IntegerField(default=0, help_text="Extra minutes added if the order is postponed.")

    BASE_PRICE_BW = 200
    COLOR_SURCHARGE = 100
    SPIRAL_BINDING_FEE = 1000

    @classmethod
    def compute_price(cls, page_count, is_color=False, is_double_sided=False, binding='none', delivery_fee=0):
        price_per_page = cls.BASE_PRICE_BW + (cls.COLOR_SURCHARGE if is_color else 0)
        effective_pages = page_count
        if is_double_sided:
            effective_pages = math.ceil(page_count / 2)
            
        printing_cost = price_per_page * effective_pages
        
        binding_cost = 0
        if binding == 'spiral':
            binding_cost = cls.SPIRAL_BINDING_FEE
            
        total_price = printing_cost + binding_cost + delivery_fee
        return total_price, effective_pages, price_per_page

    def calculate_price(self):
        delivery_fee = self.delivery_zone.delivery_fee if self.delivery_zone and self.delivery_type == 'delivery' else 0
        total, _, _ = self.compute_price(
            self.page_count, self.is_color, self.is_double_sided, self.binding, delivery_fee
        )
        self.total_price = total
        return self.total_price

    def estimated_ready_at(self):
        if self.paid_at:
            total_minutes = self.sla_minutes + self.postponed_minutes
            return self.paid_at + timedelta(minutes=total_minutes)
        return None

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
        self.calculate_price()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} by {self.client.username}"
