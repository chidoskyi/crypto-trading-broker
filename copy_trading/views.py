# copy_trading/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction
from decimal import Decimal

from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade
from copy_trading.serializers import (
    TraderSerializer, 
    CopyTradingSubscriptionSerializer,
    SubscriptionCreateSerializer,
    SubscriptionUpdateSerializer,
    CopiedTradeSerializer
)


class TraderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Master trader listing and statistics endpoints
    
    Provides:
    - List of active traders
    - Trader details and statistics
    - Search and filtering capabilities
    """
    serializer_class = TraderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['display_name', 'bio']
    filterset_fields = ['risk_score']
    ordering_fields = ['total_followers', 'profit_percentage', 'win_rate', 'total_trades']
    ordering = ['-total_followers']
    
    def get_queryset(self):
        """Filter active traders and exclude self"""
        return Trader.objects.filter(
            is_active=True
        ).exclude(
            user=self.request.user
        ).select_related('user')
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed statistics for a specific trader"""
        trader = self.get_object()
        
        # Get performance metrics
        stats = {
            'trader': TraderSerializer(trader).data,
            'performance': {
                'total_profit': trader.total_profit,
                'profit_percentage': trader.profit_percentage,
                'win_rate': trader.win_rate,
                'total_trades': trader.total_trades,
                'risk_score': trader.risk_score,
            },
            'followers': {
                'total': trader.total_followers,
                'is_following': CopyTradingSubscription.objects.filter(
                    trader=trader,
                    follower=request.user,
                    is_active=True
                ).exists()
            }
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def top_performers(self, request):
        """Get top performing traders by various metrics"""
        metric = request.query_params.get('metric', 'profit_percentage')
        limit = int(request.query_params.get('limit', 10))
        
        ordering_map = {
            'profit': '-total_profit',
            'profit_percentage': '-profit_percentage',
            'win_rate': '-win_rate',
            'followers': '-total_followers',
            'trades': '-total_trades'
        }
        
        order_by = ordering_map.get(metric, '-profit_percentage')
        traders = self.get_queryset().order_by(order_by)[:limit]
        
        return Response(TraderSerializer(traders, many=True).data)


class CopyTradingSubscriptionViewSet(viewsets.ModelViewSet):
    """
    Copy trading subscription management
    
    Provides:
    - Create/update/delete subscriptions
    - View active subscriptions
    - Performance tracking
    - Subscription controls
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return SubscriptionCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return SubscriptionUpdateSerializer
        return CopyTradingSubscriptionSerializer
    
    def get_queryset(self):
        """Get subscriptions for current user"""
        return CopyTradingSubscription.objects.filter(
            follower=self.request.user
        ).select_related('trader', 'trader__user')
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create subscription and update trader follower count"""
        # Check for existing subscription
        trader = serializer.validated_data['trader']
        existing = CopyTradingSubscription.objects.filter(
            follower=self.request.user,
            trader=trader
        ).first()
        
        if existing:
            raise serializers.ValidationError(
                "You are already following this trader"
            )
        
        # Create subscription
        subscription = serializer.save(follower=self.request.user)
        
        # Increment trader's follower count
        trader.total_followers += 1
        trader.save(update_fields=['total_followers'])
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Delete subscription and update trader follower count"""
        trader = instance.trader
        
        # Check for pending trades
        pending_trades = CopiedTrade.objects.filter(
            subscription=instance,
            status=CopiedTrade.STATUS_PENDING
        ).exists()
        
        if pending_trades:
            raise serializers.ValidationError(
                "Cannot unfollow while you have pending trades. "
                "Please wait for all trades to complete."
            )
        
        # Decrement trader's follower count
        if trader.total_followers > 0:
            trader.total_followers -= 1
            trader.save(update_fields=['total_followers'])
        
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle subscription active status"""
        subscription = self.get_object()
        subscription.is_active = not subscription.is_active
        subscription.save(update_fields=['is_active'])
        
        return Response({
            'status': 'success',
            'is_active': subscription.is_active,
            'message': f"Subscription {'activated' if subscription.is_active else 'paused'}"
        })
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Get comprehensive copy trading performance"""
        subscriptions = self.get_queryset()
        
        # Calculate aggregate statistics
        active_subs = subscriptions.filter(is_active=True)
        all_copied_trades = CopiedTrade.objects.filter(
            subscription__in=subscriptions
        ).select_related('follower_order')
        
        completed_trades = all_copied_trades.filter(
            status=CopiedTrade.STATUS_COMPLETED,
            follower_order__status='filled'
        )
        
        # Calculate total profit (placeholder - implement actual P&L)
        total_profit = Decimal('0.00')
        winning_trades = 0
        
        for trade in completed_trades:
            # Implement actual profit calculation based on your Order model
            # profit = calculate_trade_profit(trade.follower_order)
            # total_profit += profit
            # if profit > 0:
            #     winning_trades += 1
            pass
        
        win_rate = (winning_trades / completed_trades.count() * 100) if completed_trades.count() > 0 else 0
        
        return Response({
            'summary': {
                'total_subscriptions': subscriptions.count(),
                'active_subscriptions': active_subs.count(),
                'total_profit': float(total_profit),
                'total_trades': all_copied_trades.count(),
                'completed_trades': completed_trades.count(),
                'pending_trades': all_copied_trades.filter(status=CopiedTrade.STATUS_PENDING).count(),
                'win_rate': float(win_rate),
            },
            'subscriptions': CopyTradingSubscriptionSerializer(
                active_subs, many=True, context={'request': request}
            ).data
        })
    
    @action(detail=True, methods=['get'])
    def trade_history(self, request, pk=None):
        """Get trade history for a specific subscription"""
        subscription = self.get_object()
        trades = CopiedTrade.objects.filter(
            subscription=subscription
        ).select_related(
            'master_order', 'follower_order'
        ).order_by('-created_at')
        
        # Pagination
        page = self.paginate_queryset(trades)
        if page is not None:
            serializer = CopiedTradeSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CopiedTradeSerializer(trades, many=True)
        return Response(serializer.data)


class CopiedTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Copied trade history and management
    
    Provides:
    - View all copied trades
    - Trade details and status
    - Manual trade approval (for manual execution mode)
    """
    serializer_class = CopiedTradeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'subscription']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get trades for current user's subscriptions"""
        return CopiedTrade.objects.filter(
            subscription__follower=self.request.user
        ).select_related(
            'subscription', 
            'subscription__trader',
            'master_order',
            'follower_order'
        )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a pending trade (for manual execution mode)"""
        trade = self.get_object()
        
        if trade.status != CopiedTrade.STATUS_PENDING:
            return Response(
                {'error': 'Only pending trades can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if trade.subscription.execution_mode != CopyTradingSubscription.EXEC_MANUAL:
            return Response(
                {'error': 'This subscription is in auto mode'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Execute the trade
            from copy_trading.services.copy_service import CopyTradingService
            service = CopyTradingService()
            service.execute_pending_trade(trade)
            
            return Response({
                'status': 'success',
                'message': 'Trade approved and executed',
                'trade': CopiedTradeSerializer(trade).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a pending trade (for manual execution mode)"""
        trade = self.get_object()
        
        if trade.status != CopiedTrade.STATUS_PENDING:
            return Response(
                {'error': 'Only pending trades can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trade.status = CopiedTrade.STATUS_REJECTED
        trade.save(update_fields=['status'])
        
        return Response({
            'status': 'success',
            'message': 'Trade rejected'
        })
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending trades requiring approval"""
        pending_trades = self.get_queryset().filter(
            status=CopiedTrade.STATUS_PENDING,
            subscription__execution_mode=CopyTradingSubscription.EXEC_MANUAL
        )
        
        serializer = self.get_serializer(pending_trades, many=True)
        return Response(serializer.data)