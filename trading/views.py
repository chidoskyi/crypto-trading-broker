# trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from trading.models import AssetCategory, Order, TradingPair, Position
from trading.serializers import (
    OrderSerializer, TradingPairSerializer, PositionSerializer
)
from trading.services.market_service import MarketDataService
from trading.services.order_service import OrderExecutionService

class TradingPairViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading pairs endpoints with filtering by asset class"""
    serializer_class = TradingPairSerializer
    queryset = TradingPair.objects.filter(is_active=True)
    filterset_fields = ['market_type', 'asset_category', 'exchange', 'sector']
    search_fields = ['symbol', 'name', 'base_currency']
    ordering_fields = ['symbol', 'volume_24h', 'price_change_24h']
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get trading pairs grouped by category"""
        categories = AssetCategory.objects.filter(is_active=True)
        result = {}
        
        for category in categories:
            pairs = TradingPair.objects.filter(
                asset_category=category,
                is_active=True
            )
            result[category.code] = TradingPairSerializer(pairs, many=True).data
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def crypto(self, request):
        """Get all cryptocurrency pairs"""
        pairs = self.queryset.filter(market_type='crypto')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stocks(self, request):
        """Get all stock pairs"""
        pairs = self.queryset.filter(market_type='stock')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def forex(self, request):
        """Get all forex pairs"""
        pairs = self.queryset.filter(market_type='forex')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def commodities(self, request):
        """Get all commodity pairs"""
        pairs = self.queryset.filter(market_type='commodity')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def bonds(self, request):
        """Get all bond pairs"""
        pairs = self.queryset.filter(market_type='bond')
        serializer = self.get_serializer(pairs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def market_data(self, request, pk=None):
        """Get real-time market data"""
        trading_pair = self.get_object()
        market_service = UnifiedMarketDataService()
        
        try:
            data = market_service.get_ticker(trading_pair)
            
            # Add market hours info
            data['is_market_open'] = market_service.check_market_hours(trading_pair)
            data['market_type'] = trading_pair.market_type
            data['asset_category'] = trading_pair.asset_category.name
            
            return Response(data)
        except Exception as e:
            return Response(
                {'error': str(e)},
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
                    }
                }
        
        return Response(status_info)

class OrderViewSet(viewsets.ModelViewSet):
    """Order management endpoints"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Create a new order"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_service = OrderExecutionService()
        
        try:
            order = order_service.create_order(
                request.user,
                serializer.validated_data
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an open order"""
        order = self.get_object()
        
        if order.status not in ['open', 'partially_filled']:
            return Response(
                {'error': 'Order cannot be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        # Unlock funds
        # Implementation here...
        
        return Response(OrderSerializer(order).data)

class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """Position management endpoints"""
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Position.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a position"""
        position = self.get_object()
        
        # Create closing order
        order_service = OrderExecutionService()
        order_data = {
            'trading_pair': position.trading_pair,
            'order_type': 'market',
            'side': 'sell' if position.side == 'long' else 'buy',
            'quantity': position.quantity
        }
        
        order = order_service.create_order(request.user, order_data)
        
        return Response({
            'message': 'Position closed',
            'order': OrderSerializer(order).data
        })