# trading/admin.py
from django.contrib import admin
from trading.models import TradingPair, Order, Trade, Position, AssetCategory

@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'description', 'is_active', 'trading_hours_start', 'trading_hours_end', 'trading_days']
    list_filter = ['is_active']
    search_fields = ['code', 'name']

@admin.register(TradingPair)
class TradingPairAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'market_type', 'is_active', 'trading_fee_percentage']
    list_filter = ['market_type', 'is_active']
    search_fields = ['symbol', 'base_currency', 'quote_currency']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'trading_pair', 'side', 'order_type', 
                   'quantity', 'status', 'created_at']
    list_filter = ['status', 'order_type', 'side', 'source']
    search_fields = ['user__email', 'trading_pair__symbol']
    readonly_fields = ['created_at', 'updated_at', 'executed_at']

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'quantity', 'price', 'fee', 'executed_at']
    list_filter = ['executed_at']
    search_fields = ['order__user__email']

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['user', 'trading_pair', 'side', 'quantity', 
                   'unrealized_pnl', 'opened_at']
    list_filter = ['side', 'opened_at']
    search_fields = ['user__email', 'trading_pair__symbol']