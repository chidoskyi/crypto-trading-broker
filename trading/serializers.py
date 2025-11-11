# trading/serializers.py
from rest_framework import serializers
from trading.models import TradingPair, Order, Trade, Position

class TradingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingPair
        fields = ['id', 'symbol', 'base_currency', 'quote_currency', 
                  'market_type', 'is_active', 'min_order_size', 'max_order_size',
                  'price_precision', 'quantity_precision', 'trading_fee_percentage']

class OrderSerializer(serializers.ModelSerializer):
    trading_pair = serializers.PrimaryKeyRelatedField(
        queryset=TradingPair.objects.all()
    )
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'trading_pair', 'trading_pair_detail', 'order_type', 
                  'side', 'quantity', 'price', 'stop_price', 'filled_quantity',
                  'average_price', 'status', 'fee', 'source', 'created_at',
                  'updated_at', 'executed_at']
        read_only_fields = ['id', 'filled_quantity', 'average_price', 'status',
                           'fee', 'created_at', 'updated_at', 'executed_at']
    
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
        
        return attrs

class TradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = Trade
        fields = ['id', 'order', 'order_detail', 'quantity', 'price', 'fee',
                  'executed_at', 'external_trade_id']

class PositionSerializer(serializers.ModelSerializer):
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = Position
        fields = ['id', 'trading_pair', 'trading_pair_detail', 'side', 'quantity',
                  'entry_price', 'current_price', 'unrealized_pnl', 'leverage',
                  'stop_loss', 'take_profit', 'opened_at', 'updated_at']