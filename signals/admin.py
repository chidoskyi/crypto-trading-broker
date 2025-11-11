# signals/admin.py (ADD THIS)
from django.contrib import admin
from signals.models import (
    SignalProvider, SignalPlan, SignalSubscription, 
    TradingSignal, SignalNotification
)

@admin.register(SignalProvider)
class SignalProviderAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'provider_type', 'accuracy_rate', 
                   'total_signals', 'is_active']
    list_filter = ['is_active', 'provider_type']
    search_fields = ['name']
    readonly_fields = ['total_signals', 'created_at']

@admin.register(SignalPlan)
class SignalPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'provider', 'price', 'duration_days', 
                   'is_active']
    list_filter = ['is_active', 'provider']
    search_fields = ['name', 'provider__name']
    readonly_fields = ['created_at']

@admin.register(SignalSubscription)
class SignalSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'plan', 'status', 'started_at', 'expires_at']
    list_filter = ['status', 'auto_renew']
    search_fields = ['user__email', 'plan__name']
    readonly_fields = ['started_at']

@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ['id', 'provider', 'trading_pair', 'signal_type', 
                   'confidence', 'status', 'created_at']
    list_filter = ['status', 'signal_type', 'provider']
    search_fields = ['trading_pair__symbol', 'provider__name']
    readonly_fields = ['created_at', 'closed_at']

@admin.register(SignalNotification)
class SignalNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'signal', 'sent_at', 'read_at', 'acted_on']
    list_filter = ['acted_on', 'sent_at']
    search_fields = ['user__email', 'signal__trading_pair__symbol']
    readonly_fields = ['sent_at', 'read_at']