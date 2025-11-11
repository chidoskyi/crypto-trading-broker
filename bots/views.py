# bots/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from bots.models import TradingBot, BotTrade
from bots.serializers import TradingBotSerializer, BotTradeSerializer
from bots.services.bot_engine import BotEngine

class TradingBotViewSet(viewsets.ModelViewSet):
    """Trading bot management endpoints"""
    serializer_class = TradingBotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return TradingBot.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a trading bot"""
        bot = self.get_object()
        
        if bot.is_active:
            return Response(
                {'error': 'Bot is already running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bot.is_active = True
        bot.save()
        
        return Response({'message': 'Bot started successfully'})
    
    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """Stop a trading bot"""
        bot = self.get_object()
        
        if not bot.is_active:
            return Response(
                {'error': 'Bot is not running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bot.is_active = False
        bot.save()
        
        return Response({'message': 'Bot stopped successfully'})
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get bot performance metrics"""
        bot = self.get_object()
        
        trades = BotTrade.objects.filter(bot=bot).select_related('order')
        
        # Calculate metrics
        total_profit = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.signal_data.get('price', 0))
            for trade in trades
            if trade.order.status == 'filled'
        )
        
        return Response({
            'total_trades': bot.total_trades,
            'winning_trades': bot.winning_trades,
            'total_profit': bot.total_profit,
            'win_rate': (bot.winning_trades / bot.total_trades * 100) 
                       if bot.total_trades > 0 else 0,
            'recent_trades': BotTradeSerializer(trades[:10], many=True).data
        })

class BotTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Bot trade history endpoints"""
    serializer_class = BotTradeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BotTrade.objects.filter(bot__user=self.request.user)