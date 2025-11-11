# referrals/admin.py (ADD THIS)
from django.contrib import admin
from referrals.models import ReferralTier, ReferralReward

@admin.register(ReferralTier)
class ReferralTierAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'min_referrals', 'commission_percentage', 
                   'bonus_amount']
    list_filter = ['min_referrals']
    search_fields = ['name']
    readonly_fields = ['created_at']

@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = ['id', 'referrer', 'referred_user', 'reward_type', 
                   'amount', 'created_at']
    list_filter = ['reward_type', 'created_at']
    search_fields = ['referrer__email', 'referred_user__email']
    readonly_fields = ['created_at']