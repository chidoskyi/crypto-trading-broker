# copy_trading/serializers.py
from rest_framework import serializers
from decimal import Decimal
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade
from trading.serializers import OrderSerializer
from users.serializers import UserSerializer


class TraderSerializer(serializers.ModelSerializer):
    """Serializer for master traders with comprehensive stats"""
    user_info = UserSerializer(source='user', read_only=True)
    followers_count = serializers.IntegerField(source='total_followers', read_only=True)
    
    class Meta:
        model = Trader
        fields = [
            'id', 'user', 'user_info', 'display_name', 'bio', 
            'is_active', 'followers_count', 'total_profit',
            'profit_percentage', 'win_rate', 'total_trades',
            'risk_score', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_followers', 'total_profit',
            'profit_percentage', 'win_rate', 'total_trades',
            'created_at', 'updated_at'
        ]


class CopyTradingSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for copy trading subscriptions with validation"""
    trader_detail = TraderSerializer(source='trader', read_only=True)
    follower_info = UserSerializer(source='follower', read_only=True)
    
    class Meta:
        model = CopyTradingSubscription
        fields = [
            'id', 'follower', 'follower_info', 'trader', 'trader_detail', 
            'is_active', 'copy_percentage', 'max_position_size',
            'fixed_amount_per_trade', 'sizing_mode', 'execution_mode',
            'stop_loss_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'follower', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Comprehensive validation for subscriptions"""
        request = self.context.get('request')
        
        # Prevent self-copying
        if attrs.get('trader') and attrs['trader'].user == request.user:
            raise serializers.ValidationError({
                "trader": "You cannot copy your own trades"
            })
        
        # Validate sizing mode requirements
        sizing_mode = attrs.get('sizing_mode', CopyTradingSubscription.MODE_PROPORTIONAL)
        
        if sizing_mode == CopyTradingSubscription.MODE_FIXED:
            if not attrs.get('fixed_amount_per_trade'):
                raise serializers.ValidationError({
                    "fixed_amount_per_trade": "Required when using fixed sizing mode"
                })
            if attrs['fixed_amount_per_trade'] <= 0:
                raise serializers.ValidationError({
                    "fixed_amount_per_trade": "Must be greater than 0"
                })
        
        # Validate copy percentage
        copy_percentage = attrs.get('copy_percentage', Decimal('100.00'))
        if copy_percentage <= 0 or copy_percentage > 100:
            raise serializers.ValidationError({
                "copy_percentage": "Must be between 0 and 100"
            })
        
        # Validate stop loss
        stop_loss = attrs.get('stop_loss_percentage')
        if stop_loss and (stop_loss <= 0 or stop_loss > 100):
            raise serializers.ValidationError({
                "stop_loss_percentage": "Must be between 0 and 100"
            })
        
        # Validate max position size
        max_position = attrs.get('max_position_size')
        if max_position and max_position <= 0:
            raise serializers.ValidationError({
                "max_position_size": "Must be greater than 0"
            })
        
        return attrs
    
    def validate_trader(self, value):
        """Ensure trader is active"""
        if not value.is_active:
            raise serializers.ValidationError("This trader is not currently accepting followers")
        return value


class CopiedTradeSerializer(serializers.ModelSerializer):
    """Serializer for copied trade records"""
    subscription_detail = CopyTradingSubscriptionSerializer(
        source='subscription', 
        read_only=True
    )
    master_order_detail = OrderSerializer(source='master_order', read_only=True)
    follower_order_detail = OrderSerializer(source='follower_order', read_only=True)
    
    # Additional computed fields
    profit_loss = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CopiedTrade
        fields = [
            'id', 'subscription', 'subscription_detail', 
            'master_order', 'master_order_detail', 
            'follower_order', 'follower_order_detail',
            'status', 'status_display', 'profit_loss',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_profit_loss(self, obj):
        """Calculate profit/loss for completed trades"""
        if obj.status != CopiedTrade.STATUS_COMPLETED:
            return None
        
        if not obj.follower_order or obj.follower_order.status != 'filled':
            return None
        
        # Calculate based on order details
        # This is a placeholder - implement actual P&L calculation
        return {
            'amount': 0.00,
            'percentage': 0.00
        }


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating subscriptions"""
    
    class Meta:
        model = CopyTradingSubscription
        fields = [
            'trader', 'copy_percentage', 'max_position_size',
            'fixed_amount_per_trade', 'sizing_mode', 'execution_mode',
            'stop_loss_percentage'
        ]
    
    def validate(self, attrs):
        """Use parent validation"""
        return CopyTradingSubscriptionSerializer.validate(self, attrs)


class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating subscription settings"""
    
    class Meta:
        model = CopyTradingSubscription
        fields = [
            'is_active', 'copy_percentage', 'max_position_size',
            'fixed_amount_per_trade', 'sizing_mode', 'execution_mode',
            'stop_loss_percentage'
        ]
    
    def validate(self, attrs):
        """Prevent changing critical fields while trades are active"""
        instance = self.instance
        
        # Check if there are pending trades
        if hasattr(instance, 'copiedtrade_set'):
            pending_trades = instance.copiedtrade_set.filter(
                status=CopiedTrade.STATUS_PENDING
            ).exists()
            
            if pending_trades:
                # Prevent certain changes while trades are pending
                restricted_fields = ['sizing_mode', 'execution_mode']
                for field in restricted_fields:
                    if field in attrs and attrs[field] != getattr(instance, field):
                        raise serializers.ValidationError({
                            field: "Cannot change this setting while trades are pending"
                        })
        
        return attrs