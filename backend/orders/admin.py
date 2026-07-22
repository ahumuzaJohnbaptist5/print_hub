from django.contrib import admin
from .models import Order, SystemSettings, DeliveryZone
from .models import Announcement

admin.site.register(Order)
admin.site.register(SystemSettings)
admin.site.register(DeliveryZone)



@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['message_preview', 'is_active', 'background_color', 'created_at']
    list_editable = ['is_active', 'background_color']
    
    def message_preview(self, obj):
        return obj.message[:80]
    message_preview.short_description = 'Message'
