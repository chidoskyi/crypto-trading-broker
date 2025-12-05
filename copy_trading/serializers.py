# copy_trading/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import Trader, CopyTradingSubscription, CopiedTrade, CopyTradingPerformance
from users.models import Profile, Account
from trading.serializers import OrderSerializer
from users.serializers import UserSerializer

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['display_name', 'bio', 'profile_picture']


class TraderSerializer(serializers.ModelSerializer):
    user_info = UserSerializer(source='user', read_only=True)
    profile = ProfileSerializer(source='user.profile', read_only=True)
    followers_count = serializers.IntegerField(source='total_followers', read_only=True)

    class Meta:
        model = Trader
        fields = [
            'id', 'user', 'user_info', 'profile',
            'is_active', 'followers_count', 'total_profit',
            'profit_percentage', 'win_rate', 'total_trades','display_name',
            'risk_score', 'minimum_investment', 'bio',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_followers', 'total_profit',
            'profit_percentage', 'win_rate', 'total_trades',
            'created_at', 'updated_at'
        ]


class CopyTradingPerformanceSerializer(serializers.ModelSerializer):
    """Serializer for copy trading performance metrics"""
    
    # Computed fields
    roi = serializers.SerializerMethodField()
    average_trade_size = serializers.SerializerMethodField()
    profit_factor = serializers.SerializerMethodField()
    
    class Meta:
        model = CopyTradingPerformance
        fields = [
            'id', 'subscription', 'total_trades', 'winning_trades',
            'losing_trades', 'total_profit_loss', 'total_invested',
            'win_rate', 'average_profit_per_trade', 'average_loss_per_trade',
            'best_trade_profit', 'worst_trade_loss', 'last_trade_at',
            'updated_at', 'roi', 'average_trade_size', 'profit_factor'
        ]
        read_only_fields = fields  # All fields are read-only
    
    def get_roi(self, obj):
        """Calculate Return on Investment (ROI) percentage"""
        if obj.total_invested > 0:
            return float((obj.total_profit_loss / obj.total_invested) * 100)
        return 0.00
    
    def get_average_trade_size(self, obj):
        """Calculate average trade size"""
        if obj.total_trades > 0:
            return float(obj.total_invested / obj.total_trades)
        return 0.00
    
    def get_profit_factor(self, obj):
        """Calculate profit factor (total profit / total loss)"""
        total_profit = obj.winning_trades * obj.average_profit_per_trade if obj.average_profit_per_trade else Decimal('0')
        total_loss = abs(obj.losing_trades * obj.average_loss_per_trade) if obj.average_loss_per_trade else Decimal('0')
        
        if total_loss > 0:
            return float(total_profit / total_loss)
        return float(total_profit) if total_profit > 0 else 0.00


class CopyTradingSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for copy trading subscriptions with validation"""
    trader_detail = TraderSerializer(source='trader', read_only=True)
    follower_info = UserSerializer(source='follower', read_only=True)
    copied_trades_count = serializers.SerializerMethodField()
    performance = CopyTradingPerformanceSerializer(read_only=True)
    
    
    class Meta:
        model = CopyTradingSubscription
        fields = [
            'id', 'follower', 'follower_info', 'trader', 'trader_detail', 
            'is_active', 'copy_percentage', 'max_position_size',
            'fixed_amount_per_trade', 'sizing_mode', 'execution_mode',
            'stop_loss_percentage', 'created_at', 'updated_at', 
            'copied_trades_count', 'performance'
        ]
        read_only_fields = ['id', 'follower', 'created_at', 'updated_at', 'performance']
        
    def get_copied_trades_count(self, obj):
        return obj.copied_trades.filter(
            status=CopiedTrade.STATUS_COMPLETED
        ).count()
    
    def validate(self, attrs):
        """Comprehensive validation for subscriptions"""
        request = self.context.get('request')
        trader = attrs.get('trader')
        
        # Check minimum investment
        if trader and request:
            try:
                account = Account.objects.get(user=request.user)
                
                if account.trading_balance < trader.minimum_investment:
                    raise serializers.ValidationError({
                        "trader": f"Minimum trading balance required: ${trader.minimum_investment}. "
                                f"Your current balance: ${account.trading_balance}. "
                                f"Please deposit more funds.",
                        "redirect_url": "/dashboard/deposit",
                        "minimum_required": str(trader.minimum_investment),
                        "current_balance": str(account.trading_balance)
                    })
            except Account.DoesNotExist:
                raise serializers.ValidationError({
                    "account": "Account not found"
                })
        
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
            'calculated_quantity', 'allocated_amount', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_profit_loss(self, obj):
        """Calculate profit/loss for completed trades"""
        if obj.status != CopiedTrade.STATUS_COMPLETED:
            return None
        
        if not obj.follower_order or obj.follower_order.status != 'filled':
            return None
        
        # Get position related to this order
        from trading.models import Position
        try:
            position = Position.objects.get(order=obj.follower_order)
            
            if position.status == 'closed' and position.realized_pnl is not None:
                # Position is closed, show realized P&L
                return {
                    'amount': float(position.realized_pnl),
                    'percentage': float(position.get_pnl_percentage()),
                    'is_realized': True
                }
            else:
                # Position is open, show unrealized P&L
                return {
                    'amount': float(position.unrealized_pnl),
                    'percentage': float(position.get_pnl_percentage()),
                    'is_realized': False
                }
        except Position.DoesNotExist:
            return None


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
        if hasattr(instance, 'copied_trades'):
            pending_trades = instance.copied_trades.filter(
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