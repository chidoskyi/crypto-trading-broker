# copy_trading/views.py
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction
from decimal import Decimal
from rest_framework import serializers

from copy_trading.models import (
    Trader, CopyTradingSubscription, CopiedTrade, CopyTradingPerformance
)
from copy_trading.serializers import (
    TraderSerializer, 
    CopyTradingSubscriptionSerializer,
    SubscriptionCreateSerializer,
    SubscriptionUpdateSerializer,
    CopiedTradeSerializer,
    CopyTradingPerformanceSerializer
)
from users.models import Account


class TraderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Master trader listing and statistics endpoints
    """
    serializer_class = TraderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['display_name', 'bio', 'user__username']
    filterset_fields = ['risk_score']
    ordering_fields = ['total_followers', 'profit_percentage', 'win_rate', 'total_trades']
    ordering = ['-total_followers']
    
    def get_queryset(self):
        """Filter active traders and exclude self"""
        queryset = Trader.objects.filter(
            is_active=True
        ).exclude(
            user=self.request.user
        ).select_related('user', 'user__profile')
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed statistics for a specific trader"""
        trader = self.get_object()
        
        stats = {
            'trader': TraderSerializer(trader).data,
            'performance': {
                'total_profit': str(trader.total_profit),
                'profit_percentage': str(trader.profit_percentage),
                'win_rate': str(trader.win_rate),
                'total_trades': trader.total_trades,
                'risk_score': trader.risk_score,
                'minimum_investment': str(trader.minimum_investment),
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

    @action(detail=False, methods=['get'])
    def check_trader_status(self, request):
        """Check if current user has a trader profile and whether it is active"""
        try:
            trader = Trader.objects.get(user=request.user)
            
            return Response({
                'is_trader': True,
                'is_active': trader.is_active,
                'trader': TraderSerializer(trader).data 
            })
            
        except Trader.DoesNotExist:
            return Response({
                'is_trader': False,
                'is_active': False,
                'trader': None 
            })
            
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def activate_trader(self, request):
        """Activate user as a trader"""
        if Trader.objects.filter(user=request.user).exists():
            return Response(
                {'message': 'You are already a trader'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        display_name = request.data.get('display_name', request.user.get_full_name() or request.user.username)
        minimum_investment_str = request.data.get('minimum_investment', '100.00')
        minimum_investment = Decimal(minimum_investment_str) if minimum_investment_str else Decimal('100.00')
        risk_score = int(request.data.get('risk_score', 5))
        
        trader = Trader.objects.create(
            user=request.user,
            display_name=display_name,
            minimum_investment=minimum_investment,
            risk_score=risk_score,
            is_active=True
        )
        
        return Response({
            'message': 'Trader account activated successfully',
            'trader': TraderSerializer(trader).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['put'])
    @transaction.atomic
    def update_trader(self, request):
        """Update current user's trader settings"""
        try:
            trader = Trader.objects.get(user=request.user)
        except Trader.DoesNotExist:
            return Response(
                {'message': 'Trader account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        trader.display_name = request.data.get('display_name', trader.display_name)
        trader.bio = request.data.get('bio', trader.bio)
        
        if 'minimum_investment' in request.data:
            trader.minimum_investment = Decimal(request.data['minimum_investment'])
        if 'risk_score' in request.data:
            trader.risk_score = int(request.data['risk_score'])
        
        trader.save()
        
        return Response({
            'message': 'Trader settings updated successfully',
            'trader': TraderSerializer(trader).data
        })

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def deactivate_trader(self, request):
        """Deactivate current user's trader account"""
        try:
            trader = Trader.objects.get(user=request.user)
        except Trader.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Trader account not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not trader.is_active:
            return Response(
                {
                    'success': False,
                    'message': 'Trader account is already inactive'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        active_followers = CopyTradingSubscription.objects.filter(
            trader=trader,
            is_active=True
        ).count()
        
        if active_followers > 0:
            return Response(
                {
                    'success': False,
                    'message': f'Cannot deactivate. You have {active_followers} active followers. Please ask them to unfollow first.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trader.is_active = False
        trader.save()
        
        return Response({
            'success': True,
            'message': 'Trader account deactivated successfully',
            'trader': TraderSerializer(trader).data
        })

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def reactivate_trader(self, request):
        """Reactivate current user's trader account"""
        try:
            trader = Trader.objects.get(user=request.user)
        except Trader.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Trader account not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        if trader.is_active:
            return Response(
                {
                    'success': False,
                    'message': 'Trader account is already active'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trader.is_active = True
        trader.save()
        
        return Response({
            'success': True,
            'message': 'Trader account reactivated successfully',
            'trader': TraderSerializer(trader).data
        })
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def update_performance(self, request):
        """Manually trigger performance metrics update for current trader"""
        try:
            trader = Trader.objects.get(user=request.user)
        except Trader.DoesNotExist:
            return Response(
                {'message': 'Trader account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update trader performance metrics
        trader.update_performance_metrics()
        
        return Response({
            'message': 'Performance metrics updated successfully',
            'trader': TraderSerializer(trader).data
        })


class CopyTradingSubscriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return SubscriptionCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return SubscriptionUpdateSerializer
        return CopyTradingSubscriptionSerializer

    def get_queryset(self):
        return (
            CopyTradingSubscription.objects
            .filter(follower=self.request.user)
            .select_related('trader', 'trader__user')
            .prefetch_related('copied_trades')
            .order_by('-created_at')
        )

    @transaction.atomic
    def perform_create(self, serializer):
        """Create subscription with balance validation and performance tracker"""
        trader = serializer.validated_data['trader']
        
        # Check minimum investment
        try:
            account = Account.objects.get(user=self.request.user)
            
            if account.trading_balance < trader.minimum_investment:
                raise serializers.ValidationError({
                    'error': f'Insufficient trading balance. Minimum required: ${trader.minimum_investment}',
                    'redirect_url': '/dashboard/deposit',
                    'minimum_required': str(trader.minimum_investment),
                    'current_balance': str(account.trading_balance)
                })
        except Account.DoesNotExist:
            raise serializers.ValidationError({'error': 'Account not found'})
        
        trader = Trader.objects.select_for_update().get(pk=trader.pk)
        
        subscription = serializer.save(follower=self.request.user)
        
        # Create performance tracker for this subscription
        CopyTradingPerformance.objects.get_or_create(subscription=subscription)
        
        trader.total_followers += 1
        trader.save(update_fields=['total_followers'])

    @transaction.atomic
    def perform_destroy(self, instance):
        trader = instance.trader
        
        trader = Trader.objects.select_for_update().get(pk=trader.pk)
        
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
        
        active_subs = subscriptions.filter(is_active=True)
        all_copied_trades = CopiedTrade.objects.filter(
            subscription__in=subscriptions
        ).select_related('follower_order')
        
        completed_trades = all_copied_trades.filter(
            status=CopiedTrade.STATUS_COMPLETED,
            follower_order__status='filled'
        )
        
        # Calculate aggregate P&L from positions
        from trading.models import Position
        total_profit = Decimal('0.00')
        winning_trades = 0
        losing_trades = 0
        
        for trade in completed_trades:
            try:
                position = Position.objects.get(order=trade.follower_order)
                if position.status == 'closed' and position.realized_pnl is not None:
                    total_profit += position.realized_pnl
                    if position.realized_pnl > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
            except Position.DoesNotExist:
                pass
        
        win_rate = (winning_trades / completed_trades.count() * 100) if completed_trades.count() > 0 else 0
        
        return Response({
            'summary': {
                'total_subscriptions': subscriptions.count(),
                'active_subscriptions': active_subs.count(),
                'total_profit': str(total_profit),
                'total_trades': all_copied_trades.count(),
                'completed_trades': completed_trades.count(),
                'pending_trades': all_copied_trades.filter(status=CopiedTrade.STATUS_PENDING).count(),
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
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
        
        page = self.paginate_queryset(trades)
        if page is not None:
            serializer = CopiedTradeSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CopiedTradeSerializer(trades, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def detailed_performance(self, request, pk=None):
        """Get detailed performance metrics for a subscription"""
        subscription = self.get_object()
        
        # Get or create performance record
        performance, created = CopyTradingPerformance.objects.get_or_create(
            subscription=subscription
        )
        
        # Update metrics if needed
        if created or not performance.last_trade_at:
            performance.update_metrics()
        
        return Response(CopyTradingPerformanceSerializer(performance).data)


class CopiedTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Copied trade history and management
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
            from copy_trading.services.copy_service import CopyTradingService
            service = CopyTradingService()
            service.execute_pending_trade(trade)
            
            # Update performance metrics after trade execution
            performance, _ = CopyTradingPerformance.objects.get_or_create(
                subscription=trade.subscription
            )
            performance.update_metrics()
            
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


class CopyTradingPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Performance metrics for copy trading subscriptions
    """
    serializer_class = CopyTradingPerformanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get performance records for user's subscriptions"""
        return CopyTradingPerformance.objects.filter(
            subscription__follower=self.request.user
        ).select_related('subscription', 'subscription__trader')
    
    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Refresh performance metrics for a subscription"""
        performance = self.get_object()
        performance.update_metrics()
        
        return Response({
            'message': 'Performance metrics updated',
            'performance': CopyTradingPerformanceSerializer(performance).data
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get aggregate performance summary across all subscriptions"""
        performances = self.get_queryset()
        
        total_profit_loss = performances.aggregate(
            total=Sum('total_profit_loss')
        )['total'] or Decimal('0.00')
        
        total_trades = performances.aggregate(
            total=Sum('total_trades')
        )['total'] or 0
        
        total_winning = performances.aggregate(
            total=Sum('winning_trades')
        )['total'] or 0
        
        total_losing = performances.aggregate(
            total=Sum('losing_trades')
        )['total'] or 0
        
        overall_win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0
        
        return Response({
            'total_subscriptions': performances.count(),
            'total_profit_loss': str(total_profit_loss),
            'total_trades': total_trades,
            'total_winning_trades': total_winning,
            'total_losing_trades': total_losing,
            'overall_win_rate': float(overall_win_rate),
            'performances': CopyTradingPerformanceSerializer(
                performances, many=True
            ).data
        })