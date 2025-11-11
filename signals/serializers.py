# signals/serializers.py
from rest_framework import serializers
from signals.models import (
    SignalProvider, SignalPlan, SignalSubscription, 
    TradingSignal, SignalNotification
)
from trading.serializers import TradingPairSerializer

class SignalProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignalProvider
        fields = ['id', 'name', 'description', 'provider_type', 'accuracy_rate',
                  'total_signals', 'is_active', 'created_at']

class SignalPlanSerializer(serializers.ModelSerializer):
    provider_detail = SignalProviderSerializer(source='provider', read_only=True)
    
    class Meta:
        model = SignalPlan
        fields = ['id', 'provider', 'provider_detail', 'name', 'description',
                  'price', 'duration_days', 'max_signals_per_day',
                  'trading_pairs', 'is_active', 'created_at']

class SignalSubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = SignalPlanSerializer(source='plan', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = SignalSubscription
        fields = ['id', 'plan', 'plan_detail', 'status', 'started_at',
                  'expires_at', 'auto_renew', 'days_remaining']
        read_only_fields = ['id', 'started_at', 'expires_at']
    
    def get_days_remaining(self, obj):
        from datetime import datetime
        if obj.expires_at:
            delta = obj.expires_at - datetime.now(obj.expires_at.tzinfo)
            return max(0, delta.days)
        return 0

class TradingSignalSerializer(serializers.ModelSerializer):
    provider_detail = SignalProviderSerializer(source='provider', read_only=True)
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = TradingSignal
        fields = ['id', 'provider', 'provider_detail', 'trading_pair',
                  'trading_pair_detail', 'signal_type', 'entry_price',
                  'stop_loss', 'take_profit', 'timeframe', 'confidence',
                  'analysis', 'status', 'created_at', 'closed_at']

class SignalNotificationSerializer(serializers.ModelSerializer):
    signal_detail = TradingSignalSerializer(source='signal', read_only=True)
    
    class Meta:
        model = SignalNotification
        fields = ['id', 'signal', 'signal_detail', 'sent_at', 'read_at', 
                  'acted_on']