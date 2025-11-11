# copy_trading/serializers.py
from rest_framework import serializers
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade
from trading.serializers import OrderSerializer
from users.serializers import UserSerializer

class TraderSerializer(serializers.ModelSerializer):
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Trader
        fields = ['id', 'user', 'user_info', 'display_name', 'bio', 
                  'is_active', 'total_followers', 'total_profit',
                  'profit_percentage', 'win_rate', 'total_trades',
                  'risk_score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_followers', 'total_profit',
                           'profit_percentage', 'win_rate', 'total_trades',
                           'created_at', 'updated_at']

class CopyTradingSubscriptionSerializer(serializers.ModelSerializer):
    trader_detail = TraderSerializer(source='trader', read_only=True)
    
    class Meta:
        model = CopyTradingSubscription
        fields = ['id', 'trader', 'trader_detail', 'is_active', 
                  'copy_percentage', 'max_position_size',
                  'stop_loss_percentage', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        # Ensure user doesn't subscribe to themselves
        if attrs['trader'].user == self.context['request'].user:
            raise serializers.ValidationError("Cannot copy your own trades")
        
        return attrs

class CopiedTradeSerializer(serializers.ModelSerializer):
    subscription_detail = CopyTradingSubscriptionSerializer(
        source='subscription', 
        read_only=True
    )
    master_order_detail = OrderSerializer(source='master_order', read_only=True)
    follower_order_detail = OrderSerializer(source='follower_order', read_only=True)
    
    class Meta:
        model = CopiedTrade
        fields = ['id', 'subscription', 'subscription_detail', 'master_order',
                  'master_order_detail', 'follower_order', 'follower_order_detail',
                  'created_at']