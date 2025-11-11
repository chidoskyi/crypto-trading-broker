# copy_trading/admin.py (ADD THIS)
from django.contrib import admin
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade

@admin.register(Trader)
class TraderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'display_name', 'total_followers', 
                   'profit_percentage', 'win_rate', 'is_active']
    list_filter = ['is_active', 'risk_score']
    search_fields = ['user__email', 'display_name']
    readonly_fields = ['total_followers', 'total_profit', 'profit_percentage',
                      'win_rate', 'total_trades', 'created_at', 'updated_at']

@admin.register(CopyTradingSubscription)
class CopyTradingSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'follower', 'trader', 'is_active', 
                   'copy_percentage', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['follower__email', 'trader__display_name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(CopiedTrade)
class CopiedTradeAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'master_order', 'follower_order', 
                   'created_at']
    list_filter = ['created_at']
    search_fields = ['subscription__follower__email']
    readonly_fields = ['created_at']