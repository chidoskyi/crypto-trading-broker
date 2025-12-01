# copy_trading/admin.py (ADD THIS)
from django.contrib import admin
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade

@admin.register(Trader)
class TraderAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'user', 'total_followers', 'profit_percentage',
        'win_rate', 'risk_score', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'risk_score', 'created_at']
    search_fields = ['display_name', 'user__username', 'user__email']
    readonly_fields = [
        'total_followers', 'total_profit', 'profit_percentage',
        'win_rate', 'total_trades', 'created_at', 'updated_at'
    ]
    ordering = ['-total_followers', '-profit_percentage']


@admin.register(CopyTradingSubscription)
class CopyTradingSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'follower', 'trader', 'is_active', 'sizing_mode',
        'execution_mode', 'copy_percentage', 'created_at'
    ]
    list_filter = [
        'is_active', 'sizing_mode', 'execution_mode', 'created_at'
    ]
    search_fields = [
        'follower__username', 'follower__email',
        'trader__display_name', 'trader__user__username'
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['follower', 'trader']


@admin.register(CopiedTrade)
class CopiedTradeAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'subscription', 'master_order', 'follower_order',
        'status', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'subscription__follower__username',
        'master_order__id', 'follower_order__id'
    ]
    readonly_fields = ['created_at']
    raw_id_fields = ['subscription', 'master_order', 'follower_order']
