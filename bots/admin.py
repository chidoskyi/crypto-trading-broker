# bots/admin.py (ADD THIS)
from django.contrib import admin
from bots.models import TradingBot, BotTrade

@admin.register(TradingBot)
class TradingBotAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'user', 'strategy', 'is_active', 
                   'total_trades', 'total_profit', 'created_at']
    list_filter = ['is_active', 'is_paper_trading', 'strategy']
    search_fields = ['name', 'user__email', 'user__username']
    readonly_fields = ['total_trades', 'winning_trades', 'total_profit', 
                      'created_at', 'updated_at', 'last_run_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'name', 'description', 'strategy', 'is_active', 
                      'is_paper_trading')
        }),
        ('Trading Pairs', {
            'fields': ('trading_pairs',)
        }),
        ('Risk Management', {
            'fields': ('max_position_size', 'stop_loss_percentage', 
                      'take_profit_percentage', 'max_daily_loss')
        }),
        ('Strategy Parameters', {
            'fields': ('parameters',)
        }),
        ('Performance', {
            'fields': ('total_trades', 'winning_trades', 'total_profit')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_run_at')
        })
    )

@admin.register(BotTrade)
class BotTradeAdmin(admin.ModelAdmin):
    list_display = ['id', 'bot', 'order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['bot__name', 'bot__user__email']
    readonly_fields = ['created_at']