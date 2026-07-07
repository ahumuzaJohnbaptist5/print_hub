from django.contrib import admin
from .models import Order, DeliveryZone

# Register your models here.
admin.site.register(Order)
admin.site.register(DeliveryZone)
