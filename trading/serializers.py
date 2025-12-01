# trading/serializers.py
from rest_framework import serializers
from trading.models import TradingPair, Order, Trade, Position, AssetCategory, Transaction

class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ['id', 'name', 'code', 'description', 'is_active', 'trading_days',
                  'created_at', 'trading_hours_start', 'trading_hours_end', 'updated_at']

class TradingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingPair
        fields = [
            'id',
            'symbol',
            'name',
            'base_currency',
            'quote_currency',
            'market_type',
            'market_cap',
            'is_active',
            'min_order_size',
            'max_order_size',
            'price_precision',
            'quantity_precision',
            'logo_url',
            'low',
            'high',
            'open',
            'close',
            'volume_24h',
            'price_change_24h',
            'percentage_change_24h',
            'last_price',
            'last_updated',
        ]
        read_only_fields = ['id', 'last_price', 'last_updated']


class OrderSerializer(serializers.ModelSerializer):
    trading_pair = serializers.PrimaryKeyRelatedField(
        queryset=TradingPair.objects.all()
    )
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    # ✅ ADD THESE - Readable display values
    leverage_display = serializers.CharField(source='get_leverage_display', read_only=True)
    expiration_display = serializers.CharField(source='get_expiration_type_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'trading_pair', 'trading_pair_detail', 'order_type', 
            'side', 'quantity', 'price', 'stop_price', 'filled_quantity',
            'average_price', 'status', 
            # ✅ ADD THESE NEW FIELDS
            'leverage', 'leverage_display',
            'expiration_type', 'expiration_display', 'expiration_time', 'is_expired',
            'fee', 'source', 'source_id',
            'created_at', 'updated_at', 'executed_at'
        ]
        read_only_fields = [
            'id', 'filled_quantity', 'average_price', 'status',
            'fee', 'expiration_time', 'is_expired',
            'created_at', 'updated_at', 'executed_at'
        ]
    
    def validate(self, attrs):
        trading_pair = attrs['trading_pair']
        quantity = attrs['quantity']
        
        # Validate order size
        if quantity < trading_pair.min_order_size:
            raise serializers.ValidationError(
                f"Quantity must be at least {trading_pair.min_order_size}"
            )
        
        if quantity > trading_pair.max_order_size:
            raise serializers.ValidationError(
                f"Quantity must not exceed {trading_pair.max_order_size}"
            )
        
        # Validate price for limit orders
        if attrs['order_type'] == 'limit' and not attrs.get('price'):
            raise serializers.ValidationError("Price is required for limit orders")
        
        # ✅ ADD: Validate leverage for margin requirements
        leverage = attrs.get('leverage', '1')
        if trading_pair.market_type in ['stock', 'bond']:
            # Limit leverage for stocks/bonds
            if int(leverage) > 5:
                raise serializers.ValidationError(
                    f"Maximum leverage for {trading_pair.market_type} is 5x"
                )
        
        # ✅ ADD: Validate expiration type
        expiration_type = attrs.get('expiration_type', 'gtc')
        if attrs['order_type'] == 'market' and expiration_type != 'gtc':
            # Market orders execute immediately, so expiration doesn't make sense
            attrs['expiration_type'] = 'gtc'
        
        return attrs


class TradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = Trade
        fields = ['id', 'order', 'order_detail', 'quantity', 'price', 'fee',
                  'executed_at', 'external_trade_id']


class PositionSerializer(serializers.ModelSerializer):
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    # ✅ ADD: Calculate position value and PnL
    position_value = serializers.SerializerMethodField()
    pnl_percentage = serializers.SerializerMethodField()
    margin_used = serializers.SerializerMethodField()
    
    class Meta:
        model = Position
        fields = [
            'id', 'trading_pair', 'trading_pair_detail', 'side', 'status', 'quantity',
            'entry_price', 'current_price', 'unrealized_pnl', 'leverage',
            'stop_loss', 'take_profit', 'opened_at', 'updated_at',
            # ✅ ADD THESE
            'position_value', 'pnl_percentage', 'margin_used'
        ]
    
    def get_position_value(self, obj):
        """Calculate total position value with leverage"""
        return float(obj.quantity * obj.current_price * obj.leverage)
    
    def get_pnl_percentage(self, obj):
        """Calculate PnL as percentage"""
        if obj.entry_price == 0:
            return 0
        pnl_pct = ((obj.current_price - obj.entry_price) / obj.entry_price) * 100
        if obj.side == 'short':
            pnl_pct = -pnl_pct
        return round(float(pnl_pct), 2)
    
    def get_margin_used(self, obj):
        """Calculate margin used for this position"""
        position_value = obj.quantity * obj.entry_price
        return float(position_value / obj.leverage)
        
class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model"""
    
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display',
        read_only=True
    )
    
    balance_type_display = serializers.CharField(
        source='get_balance_type_display',
        read_only=True
    )
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    is_credit = serializers.BooleanField(read_only=True)
    is_debit = serializers.BooleanField(read_only=True)
    
    # Related objects
    order_id = serializers.IntegerField(source='order.id', read_only=True, allow_null=True)
    position_id = serializers.IntegerField(source='position.id', read_only=True, allow_null=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'transaction_type',
            'transaction_type_display',
            'balance_type',
            'balance_type_display',
            'amount',
            'status',
            'status_display',
            'balance_before',
            'balance_after',
            'description',
            'reference_id',
            'metadata',
            'is_credit',
            'is_debit',
            'order_id',
            'position_id',
            'created_at',
            'updated_at',
            'completed_at'
        ]
        read_only_fields = fields  # All fields are read-only