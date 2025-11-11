# copy_trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade
from copy_trading.serializers import (
    TraderSerializer, CopyTradingSubscriptionSerializer, CopiedTradeSerializer
)

class TraderViewSet(viewsets.ReadOnlyModelViewSet):
    """Master trader listing endpoints"""
    serializer_class = TraderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Trader.objects.filter(is_active=True)
    filterset_fields = ['risk_score']
    ordering_fields = ['total_followers', 'profit_percentage', 'win_rate']
    ordering = ['-total_followers']

class CopyTradingSubscriptionViewSet(viewsets.ModelViewSet):
    """Copy trading subscription management"""
    serializer_class = CopyTradingSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CopyTradingSubscription.objects.filter(follower=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(follower=self.request.user)
        
        # Increment trader's follower count
        trader = serializer.validated_data['trader']
        trader.total_followers += 1
        trader.save()
    
    def perform_destroy(self, instance):
        # Decrement trader's follower count
        instance.trader.total_followers -= 1
        instance.trader.save()
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Get copy trading performance"""
        subscriptions = self.get_queryset().filter(is_active=True)
        
        total_profit = 0
        for sub in subscriptions:
            copied_trades = CopiedTrade.objects.filter(
                subscription=sub
            ).select_related('follower_order')
            
            for trade in copied_trades:
                if trade.follower_order.status == 'filled':
                    # Calculate profit
                    pass
        
        return Response({
            'active_subscriptions': subscriptions.count(),
            'total_profit': total_profit,
            'subscriptions': CopyTradingSubscriptionSerializer(
                subscriptions, many=True
            ).data
        })

class CopiedTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Copied trade history"""
    serializer_class = CopiedTradeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CopiedTrade.objects.filter(
            subscription__follower=self.request.user
        )