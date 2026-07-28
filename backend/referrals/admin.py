from django.contrib import admin
from .models import ReferralCode, Referral, ReferralBonus

@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'is_active', 'created_at']
    search_fields = ['code', 'user__username', 'user__email']
    list_filter = ['is_active']
    readonly_fields = ['code', 'created_at']

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referee', 'status', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['referrer__username', 'referee__username']
    readonly_fields = ['created_at', 'completed_at']
    actions = ['mark_completed']

    def mark_completed(self, request, queryset):
        count = 0
        for referral in queryset:
            if referral.status == 'pending':
                referral.mark_completed()
                count += 1
        self.message_user(request, f'{count} referrals marked as completed.')
    mark_completed.short_description = 'Mark selected referrals as completed'

@admin.register(ReferralBonus)
class ReferralBonusAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'bonus_type', 'is_used', 'created_at']
    list_filter = ['bonus_type', 'is_used']
    search_fields = ['user__username', 'user__email', 'description']
    readonly_fields = ['created_at']
