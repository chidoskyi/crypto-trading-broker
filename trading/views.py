# trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from trading.models import AssetCategory, Order, TradingPair, Position, Trade, Transaction
from users.models import Account
from trading.serializers import (
    OrderSerializer, TradingPairSerializer, PositionSerializer, 
    TradeSerializer, AssetCategorySerializer, TransactionSerializer
)
from decimal import Decimal
import csv
from django.http import HttpResponse
from trading.services.market_service import MarketDataService
from trading.services.order_service import OrderExecutionService
import logging


logger = logging.getLogger(__name__)


class AssetCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Asset category management endpoints"""
    serializer_class = AssetCategorySerializer
    queryset = AssetCategory.objects.filter(is_active=True)
    
    def get_permissions(self):
        """Allow unauthenticated access to list categories"""
        if self.action == 'list':
            return []
        return [IsAuthenticated()]

@api_view(['GET'])
def trading_config(request):
    """API endpoint to get trading configuration"""
    try:
        leverage_options = [
            {'value': value, 'label': label} 
            for value, label in Order.LEVERAGE_CHOICES
        ]
        
        expiration_options = [
            {'value': value, 'label': label} 
            for value, label in Order.EXPIRATION_CHOICES
        ]
        
        order_type_options = [
            {
                'value': value, 
                'label': label,
                'description': get_order_type_description(value)
            } 
            for value, label in Order.ORDER_TYPES
        ]
        
        config = {
            'leverage_options': leverage_options,
            'expiration_options': expiration_options,
            'order_type_options': order_type_options,
        }
        
        return Response(config)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to load trading configuration'}, 
            status=500
        )

def get_order_type_description(order_type):
    descriptions = {
        'market': 'Execute immediately at current market price',
        'limit': 'Execute only at specified price or better',
        'stop_loss': 'Trigger when price reaches stop level',
        'take_profit': 'Take profit at specified price level'
    }
    return descriptions.get(order_type, '')

class TradingPairViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading pairs endpoints with filtering by asset class"""
    serializer_class = TradingPairSerializer
    queryset = TradingPair.objects.filter(is_active=True)
    filterset_fields = ['market_type', 'asset_category', 'exchange', 'sector']
    search_fields = ['symbol', 'name', 'base_currency']
    ordering_fields = ['symbol', 'volume_24h', 'price_change_24h']
    ordering = ['symbol']
    
    def get_queryset(self):
        """Override to add custom filtering"""
        queryset = super().get_queryset()
        
        # Filter by search query if provided
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(symbol__icontains=search) |
                Q(name__icontains=search) |
                Q(base_currency__icontains=search)
            )
        
        return queryset.select_related('asset_category')
    
    @action(detail=True, methods=['get'])
    def ticker(self, request, pk=None):
        """Get current ticker data for a trading pair"""
        trading_pair = self.get_object()
        
        try:
            market_service = MarketDataService()
            ticker = market_service.get_ticker(trading_pair)
            
            return Response({
                'trading_pair': TradingPairSerializer(trading_pair).data,
                'ticker': {
                    'last_price': str(ticker['last_price']),
                    'open': str(ticker.get('open', 0)),
                    'high_24h': str(ticker.get('high_24h', 0)),
                    'low_24h': str(ticker.get('low_24h', 0)),
                    'volume': str(ticker.get('volume', 0)),
                    'change_24h': str(ticker.get('change_24h', 0)),
                    'bid': str(ticker.get('bid', 0)),
                    'ask': str(ticker.get('ask', 0)),
                }
            })
        except Exception as e:
            logger.error(f"Failed to get ticker for {trading_pair.symbol}: {str(e)}")
            return Response(
                {'error': 'Failed to fetch market data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get trading pairs grouped by category"""
        categories = AssetCategory.objects.filter(is_active=True)
        result = {}
        
        for category in categories:
            pairs = TradingPair.objects.filter(
                asset_category=category,
                is_active=True
            ).order_by('symbol')
            result[category.code] = TradingPairSerializer(pairs, many=True).data
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def crypto(self, request):
        """Get all cryptocurrency pairs"""
        pairs = self.get_queryset().filter(market_type='crypto')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stocks(self, request):
        """Get all stock pairs"""
        pairs = self.get_queryset().filter(market_type='stock')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def forex(self, request):
        """Get all forex pairs"""
        pairs = self.get_queryset().filter(market_type='forex')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def commodities(self, request):
        """Get all commodity pairs"""
        pairs = self.get_queryset().filter(market_type='commodity')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def bonds(self, request):
        """Get all bond pairs"""
        pairs = self.get_queryset().filter(market_type='bond')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def market_data(self, request, pk=None):
        """Get real-time market data"""
        trading_pair = self.get_object()
        market_service = MarketDataService()
        
        try:
            data = market_service.get_ticker(trading_pair)
            
            # Add market hours info
            data['is_market_open'] = market_service.check_market_hours(trading_pair)
            data['market_type'] = trading_pair.market_type
            data['asset_category'] = trading_pair.asset_category.name
            data['symbol'] = trading_pair.symbol
            
            return Response(data)
        except Exception as e:
            logger.error(f"Failed to get market data for {trading_pair.symbol}: {str(e)}")
            return Response(
                {'error': 'Failed to fetch market data', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def historical(self, request, pk=None):
        """Get historical data for a trading pair"""
        trading_pair = self.get_object()
        timeframe = request.query_params.get('timeframe', '1h')
        limit = int(request.query_params.get('limit', 100))
        
        try:
            market_service = MarketDataService()
            historical_data = market_service.get_historical_data(
                trading_pair, timeframe, limit
            )
            
            return Response({
                'trading_pair': trading_pair.symbol,
                'timeframe': timeframe,
                'data': historical_data
            })
        except Exception as e:
            logger.error(f"Failed to get historical data: {str(e)}")
            return Response(
                {'error': 'Failed to fetch historical data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def market_status(self, request):
        """Get status of all markets"""
        market_service = MarketDataService()
        categories = AssetCategory.objects.filter(is_active=True)
        
        status_info = {}
        for category in categories:
            # Get a sample pair from each category
            sample_pair = TradingPair.objects.filter(
                asset_category=category,
                is_active=True
            ).first()
            
            if sample_pair:
                is_open = market_service.check_market_hours(sample_pair)
                status_info[category.code] = {
                    'name': category.name,
                    'is_open': is_open,
                    'trading_hours': {
                        'start': str(category.trading_hours_start) if category.trading_hours_start else 'N/A',
                        'end': str(category.trading_hours_end) if category.trading_hours_end else 'N/A'
                    },
                    'trading_days': category.trading_days
                }
        
        return Response(status_info)


class OrderViewSet(viewsets.ModelViewSet):
    """Order management endpoints"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Order.objects.filter(user=self.request.user)
        
        # Filter by status if provided
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        # Filter by order type if provided
        order_type = self.request.query_params.get('order_type', None)
        if order_type:
            queryset = queryset.filter(order_type=order_type)
        
        # Filter by trading pair if provided
        pair_id = self.request.query_params.get('trading_pair', None)
        if pair_id:
            queryset = queryset.filter(trading_pair_id=pair_id)
        
        # Filter by side if provided
        side = self.request.query_params.get('side', None)
        if side:
            queryset = queryset.filter(side=side)
        
        return queryset.select_related('trading_pair').order_by('-created_at')
    
    def create(self, request):
        """Create a new order"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # ✅ Check if user has an active account
        try:
            account = Account.objects.get(user=request.user)
            if account.status != Account.STATUS_ACTIVE:
                return Response(
                    {'error': f'Your account is {account.status}. Trading is not allowed.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found. Please contact support.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        order_service = OrderExecutionService()
        
        try:
            # ✅ FIX: create_order returns a dictionary, not an Order object
            result = order_service.create_order(
                request.user,
                serializer.validated_data
            )
            
            # ✅ Extract the order object from the result dictionary
            if isinstance(result, dict):
                order = result.get('order')
                trade = result.get('trade')
                transactions = result.get('transactions')
                account_balance = result.get('account_balance')
            else:
                # Fallback if it returns just an order object
                order = result
                trade = None
                transactions = None
                account_balance = None
            
            # ✅ Refresh account balance info
            account.refresh_from_db()
            
            # Build response
            response_data = {
                'order': OrderSerializer(order).data,
                'account_balance': {
                    'trading_balance': str(account.trading_balance),
                    'available_trading_balance': str(account.available_trading_balance),
                    'pending_balance': str(account.pending_balance),
                }
            }
            
            # ✅ Add trade info if available (for market orders)
            if trade:
                response_data['trade'] = {
                    'id': trade.id,
                    'quantity': str(trade.quantity),
                    'price': str(trade.price),
                    'fee': str(trade.fee),
                    'executed_at': trade.executed_at.isoformat() if trade.executed_at else None
                }
            
            # ✅ Add transaction info if available
            if transactions:
                response_data['transactions'] = {
                    'investment': transactions.get('investment').id if transactions.get('investment') else None,
                    'fee': transactions.get('fee').id if transactions.get('fee') else None,
                }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            logger.warning(f"Order creation failed for user {request.user.id}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error creating order: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred while creating your order'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an open order"""
        order = self.get_object()
        
        if order.status not in ['open', 'partially_filled', 'pending']:
            return Response(
                {'error': f'Order cannot be cancelled. Current status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            order_service = OrderExecutionService()
            cancelled_order = order_service.cancel_order(order)
            
            # ✅ Get updated account balance
            account = Account.objects.get(user=request.user)
            
            return Response({
                'message': 'Order cancelled successfully',
                'order': OrderSerializer(cancelled_order).data,
                'account_balance': {
                    'trading_balance': str(account.trading_balance),
                    'available_trading_balance': str(account.available_trading_balance),
                    'pending_balance': str(account.pending_balance),
                }
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Failed to cancel order {order.id}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to cancel order'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def trading_summary(self, request):
        """✅ Get trading summary and account balance"""
        try:
            account = Account.objects.get(user=request.user)
            
            # Get order statistics
            orders = Order.objects.filter(user=request.user)
            total_orders = orders.count()
            open_orders = orders.filter(status__in=['open', 'pending']).count()
            filled_orders = orders.filter(status='filled').count()
            
            # Get position statistics
            positions = Position.objects.filter(user=request.user)
            total_positions = positions.count()
            total_position_value = sum(
                pos.quantity * pos.current_price * pos.leverage 
                for pos in positions
            )
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
            
            return Response({
                'account': {
                    'trading_balance': str(account.trading_balance),
                    'available_trading_balance': str(account.available_trading_balance),
                    'pending_balance': str(account.pending_balance),
                    'total_earned': str(account.total_earned),
                    'status': account.status,
                },
                'orders': {
                    'total': total_orders,
                    'open': open_orders,
                    'filled': filled_orders,
                },
                'positions': {
                    'total': total_positions,
                    'total_value': str(total_position_value),
                    'total_unrealized_pnl': str(total_unrealized_pnl),
                }
            })
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """Position management endpoints"""
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        status_param = self.request.query_params.get('status', None)

        queryset = Position.objects.filter(
            user=self.request.user
        ).select_related('trading_pair').order_by('-opened_at')

        # Filter only if status was provided
        if status_param in ['open', 'closed']:
            queryset = queryset.filter(status=status_param)

        return queryset

    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """✅ NEW: Get positions summary with P&L"""
        positions = self.get_queryset()
        
        total_value = Decimal('0')
        total_unrealized_pnl = Decimal('0')
        total_margin_used = Decimal('0')
        
        for position in positions:
            position_value = position.quantity * position.current_price * position.leverage
            margin_used = (position.quantity * position.entry_price) / position.leverage
            
            total_value += position_value
            total_unrealized_pnl += position.unrealized_pnl
            total_margin_used += margin_used
        
        return Response({
            'total_positions': positions.count(),
            'total_position_value': str(total_value),
            'total_unrealized_pnl': str(total_unrealized_pnl),
            'total_margin_used': str(total_margin_used),
            'positions': PositionSerializer(positions, many=True).data
        })
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a position"""
        position = self.get_object()
        
        try:
            order_service = OrderExecutionService()
            close_result = order_service.close_position(position)
            
            # Get updated account balance
            account = Account.objects.get(user=request.user)
            
            return Response({
                'status': 'success',
                'message': 'Position closed successfully',
                'order': OrderSerializer(close_result['order']).data,
                'realized_pnl': str(close_result['realized_pnl']),
                'account_balance': {
                    'trading_balance': str(account.trading_balance),
                    'available_trading_balance': str(account.available_trading_balance),
                    'total_earned': str(account.total_earned),
                }
            })
            
        except ValueError as e:
            return Response(
                {'status': 'error', 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Failed to close position {position.id}: {str(e)}")
            return Response(
                {'status': 'error', 'error': 'Failed to close position'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # @action(detail=True, methods=['post'])
    # def close(self, request, pk=None):
    #     """Close a position"""
    #     position = self.get_object()
        
    #     try:
    #         # Create closing order
    #         order_service = OrderExecutionService()
    #         order = order_service.close_position(position)
            
    #         # ✅ Get updated account balance
    #         account = Account.objects.get(user=request.user)
            
    #         return Response({
    #             'message': 'Position closed successfully',
    #             'order': OrderSerializer(order).data,
    #             'account_balance': {
    #                 'trading_balance': str(account.trading_balance),
    #                 'available_trading_balance': str(account.available_trading_balance),
    #                 'total_earned': str(account.total_earned),
    #             }
    #         })
    #     except ValueError as e:
    #         return Response(
    #             {'error': str(e)},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
    #     except Exception as e:
    #         logger.error(f"Failed to close position {position.id}: {str(e)}")
    #         return Response(
    #             {'error': 'Failed to close position'},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )
    
    
    @action(detail=True, methods=['post'])
    def update_stop_loss(self, request, pk=None):
        """✅ NEW: Update stop loss for a position"""
        position = self.get_object()
        stop_loss = request.data.get('stop_loss')
        
        if not stop_loss:
            return Response(
                {'error': 'stop_loss is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            stop_loss = Decimal(str(stop_loss))
            
            # Validate stop loss price
            if position.side == 'long' and stop_loss >= position.current_price:
                return Response(
                    {'error': 'Stop loss must be below current price for long positions'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if position.side == 'short' and stop_loss <= position.current_price:
                return Response(
                    {'error': 'Stop loss must be above current price for short positions'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            position.stop_loss = stop_loss
            position.save()
            
            return Response({
                'message': 'Stop loss updated successfully',
                'position': PositionSerializer(position).data
            })
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid stop loss value'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_take_profit(self, request, pk=None):
        """✅ NEW: Update take profit for a position"""
        position = self.get_object()
        take_profit = request.data.get('take_profit')
        
        if not take_profit:
            return Response(
                {'error': 'take_profit is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            take_profit = Decimal(str(take_profit))
            
            # Validate take profit price
            if position.side == 'long' and take_profit <= position.current_price:
                return Response(
                    {'error': 'Take profit must be above current price for long positions'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if position.side == 'short' and take_profit >= position.current_price:
                return Response(
                    {'error': 'Take profit must be below current price for short positions'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            position.take_profit = take_profit
            position.save()
            
            return Response({
                'message': 'Take profit updated successfully',
                'position': PositionSerializer(position).data
            })
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid take profit value'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Trade history endpoints"""
    serializer_class = TradeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Trade.objects.filter(
            order__user=self.request.user
        ).select_related('order', 'order__trading_pair').order_by('-executed_at')
        
        # ✅ Filter by trading pair if provided
        pair_id = self.request.query_params.get('trading_pair', None)
        if pair_id:
            queryset = queryset.filter(order__trading_pair_id=pair_id)
        
        # ✅ Filter by side if provided
        side = self.request.query_params.get('side', None)
        if side:
            queryset = queryset.filter(order__side=side)
        
        # ✅ Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(executed_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(executed_at__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """✅ NEW: Get trading statistics"""
        trades = self.get_queryset()
        
        if not trades.exists():
            return Response({
                'total_trades': 0,
                'total_volume': '0.00',
                'total_fees': '0.00',
                'buy_trades': 0,
                'sell_trades': 0,
                'avg_trade_size': '0.00',
            })
        
        buy_trades = trades.filter(order__side='buy')
        sell_trades = trades.filter(order__side='sell')
        
        total_volume = sum(trade.quantity * trade.price for trade in trades)
        total_fees = sum(trade.fee for trade in trades)
        avg_trade_size = total_volume / trades.count() if trades.count() > 0 else 0
        
        return Response({
            'total_trades': trades.count(),
            'total_volume': str(total_volume),
            'total_fees': str(total_fees),
            'buy_trades': buy_trades.count(),
            'sell_trades': sell_trades.count(),
            'avg_trade_size': str(avg_trade_size),
            'latest_trades': TradeSerializer(trades[:10], many=True).data
        })
 

        
class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Transaction history endpoints
    Read-only - users can view but not create/edit transactions
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Transaction.objects.filter(
            user=self.request.user
        ).select_related('order', 'position').order_by('-created_at')
        
        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type', None)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by balance type
        balance_type = self.request.query_params.get('balance_type', None)
        if balance_type:
            queryset = queryset.filter(balance_type=balance_type)
        
        # Filter by status
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by trading pair (through order or position)
        trading_pair_id = self.request.query_params.get('trading_pair', None)
        if trading_pair_id:
            queryset = queryset.filter(
                Q(order__trading_pair_id=trading_pair_id) |
                Q(position__trading_pair_id=trading_pair_id)
            )
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get transaction statistics"""
        transactions = self.get_queryset()
        
        if not transactions.exists():
            return Response({
                'total_transactions': 0,
                'total_credits': '0.00',
                'total_debits': '0.00',
                'net_amount': '0.00',
                'by_type': {},
                'by_balance_type': {}
            })
        
        # Calculate totals
        total_credits = transactions.filter(
            amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_debits = transactions.filter(
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        net_amount = total_credits + total_debits
        
        # Group by transaction type
        by_type = {}
        for trans_type, _ in Transaction.TRANSACTION_TYPES:
            count = transactions.filter(transaction_type=trans_type).count()
            total = transactions.filter(
                transaction_type=trans_type
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            if count > 0:
                by_type[trans_type] = {
                    'count': count,
                    'total': str(total)
                }
        
        # Group by balance type
        by_balance_type = {}
        for balance_type, _ in Transaction.BALANCE_TYPES:
            count = transactions.filter(balance_type=balance_type).count()
            total = transactions.filter(
                balance_type=balance_type
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            if count > 0:
                by_balance_type[balance_type] = {
                    'count': count,
                    'total': str(total)
                }
        
        return Response({
            'total_transactions': transactions.count(),
            'total_credits': str(total_credits),
            'total_debits': str(total_debits),
            'net_amount': str(net_amount),
            'by_type': by_type,
            'by_balance_type': by_balance_type
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get recent transactions summary"""
        transactions = self.get_queryset()[:10]  # Last 10 transactions
        
        return Response({
            'recent_transactions': TransactionSerializer(transactions, many=True).data,
            'total_count': Transaction.objects.filter(user=request.user).count()
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export transactions to CSV"""
        transactions = self.get_queryset()
        
        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date',
            'Type',
            'Amount',
            'Balance Type',
            'Balance Before',
            'Balance After',
            'Description',
            'Status'
        ])
        
        for transaction in transactions:
            writer.writerow([
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                transaction.get_transaction_type_display(),
                str(transaction.amount),
                transaction.get_balance_type_display(),
                str(transaction.balance_before),
                str(transaction.balance_after),
                transaction.description,
                transaction.get_status_display()
            ])
        
        return response        
        