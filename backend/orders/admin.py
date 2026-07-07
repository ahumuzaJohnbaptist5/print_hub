from django.contrib import admin
from .models import Order, SystemSettings, DeliveryZone

admin.site.register(Order)
admin.site.register(SystemSettings)
admin.site.register(DeliveryZone)
