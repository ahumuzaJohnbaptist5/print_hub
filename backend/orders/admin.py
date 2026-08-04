from django.contrib import admin
from .models import Order, SystemSettings, DeliveryZone
from .models import Announcement
from .models import SupportSettings

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

# backend/orders/admin.py


@admin.register(SupportSettings)
class SupportSettingsAdmin(admin.ModelAdmin):
    list_display = ['support_group_link', 'support_admin_number', 'support_agent_fallback', 'updated_at']
    fieldsets = (
        ('WhatsApp Group', {
            'fields': ('support_group_link',),
            'description': 'Add your WhatsApp group invite link'
        }),
        ('Contact Numbers', {
            'fields': ('support_admin_number', 'support_agent_fallback'),
            'description': 'Phone numbers for fallback contacts'
        }),
    )
