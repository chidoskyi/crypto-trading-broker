# signals/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from signals.models import (
    SignalProvider, SignalPlan, SignalSubscription, 
    TradingSignal, SignalNotification
)
from signals.serializers import (
    SignalProviderSerializer, SignalPlanSerializer,
    SignalSubscriptionSerializer, TradingSignalSerializer,
    SignalNotificationSerializer
)
from trading.services.order_service import OrderExecutionService

class SignalProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """Signal provider listing"""
    serializer_class = SignalProviderSerializer
    permission_classes = [IsAuthenticated]
    queryset = SignalProvider.objects.filter(is_active=True)

class SignalPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Signal plan listing"""
    serializer_class = SignalPlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = SignalPlan.objects.filter(is_active=True)

class SignalSubscriptionViewSet(viewsets.ModelViewSet):
    """Signal subscription management"""
    serializer_class = SignalSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SignalSubscription.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Subscribe to a signal plan"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan = serializer.validated_data['plan']
        
        # Check if already subscribed
        if SignalSubscription.objects.filter(
            user=request.user,
            plan=plan,
            status='active'
        ).exists():
            return Response(
                {'error': 'Already subscribed to this plan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process payment (implementation depends on payment gateway)
        # For now, assume payment is successful
        
        # Create subscription
        expires_at = timezone.now() + timedelta(days=plan.duration_days)
        subscription = SignalSubscription.objects.create(
            user=request.user,
            plan=plan,
            expires_at=expires_at
        )
        
        return Response(
            SignalSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        subscription.status = 'cancelled'
        subscription.auto_renew = False
        subscription.save()
        
        return Response({'message': 'Subscription cancelled'})

class TradingSignalViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading signals"""
    serializer_class = TradingSignalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Get user's active subscriptions
        subscriptions = SignalSubscription.objects.filter(
            user=self.request.user,
            status='active',
            expires_at__gt=timezone.now()
        ).values_list('plan__provider', flat=True)
        
        # Get signals from subscribed providers
        return TradingSignal.objects.filter(
            provider__in=subscriptions,
            status='active'
        ).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a signal as an order"""
        signal = self.get_object()
        
        # Check if user has active subscription
        if not SignalSubscription.objects.filter(
            user=request.user,
            plan__provider=signal.provider,
            status='active',
            expires_at__gt=timezone.now()
        ).exists():
            return Response(
                {'error': 'No active subscription for this signal'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create order based on signal
        order_service = OrderExecutionService()
        
        order_data = {
            'trading_pair': signal.trading_pair.id,
            'order_type': 'limit',
            'side': signal.signal_type,
            'quantity': request.data.get('quantity'),
            'price': signal.entry_price,
            'stop_price': signal.stop_loss,
            'source': 'signal',
            'source_id': signal.id
        }
        
        try:
            order = order_service.create_order(request.user, order_data)
            
            # Mark signal notification as acted on
            SignalNotification.objects.filter(
                user=request.user,
                signal=signal
            ).update(acted_on=True)
            
            return Response({
                'message': 'Signal executed',
                'order_id': order.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class SignalNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Signal notifications"""
    serializer_class = SignalNotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SignalNotification.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.read_at = timezone.now()
        notification.save()
        
        return Response({'message': 'Marked as read'})