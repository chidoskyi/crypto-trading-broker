# bots/serializers.py
from rest_framework import serializers
from bots.models import TradingBot, BotTrade
from trading.serializers import OrderSerializer

class TradingBotSerializer(serializers.ModelSerializer):
    trading_bots = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=TradingBot.objects.all()
    )
    win_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TradingBot
        fields = ['id', 'name', 'description', 'strategy', 'trading_pairs',
                  'is_active', 'is_paper_trading', 'max_position_size',
                  'stop_loss_percentage', 'take_profit_percentage',
                  'max_daily_loss', 'parameters', 'total_trades',
                  'winning_trades', 'total_profit', 'win_rate',
                  'created_at', 'updated_at', 'last_run_at']
        read_only_fields = ['id', 'total_trades', 'winning_trades', 
                           'total_profit', 'created_at', 'updated_at', 
                           'last_run_at']
    
    def get_win_rate(self, obj):
        if obj.total_trades == 0:
            return 0
        return (obj.winning_trades / obj.total_trades) * 100

class BotTradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = BotTrade
        fields = ['id', 'bot', 'order', 'order_detail', 'signal_data', 
                  'created_at']