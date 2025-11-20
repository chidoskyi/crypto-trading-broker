# signals/services/notification_service.py
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from signals.models import SignalNotification, SignalSubscription

class SignalNotificationService:
    """Send trading signals to subscribed users"""
    
    def notify_subscribers(self, signal):
        """Send signal to all active subscribers"""
        # Get active subscriptions for this provider
        subscriptions = SignalSubscription.objects.filter(
            plan__provider=signal.provider,
            status='active',
            expires_at__gt=timezone.now()
        ).select_related('user')
        
        for subscription in subscriptions:
            # Check if signal's trading pair is in plan
            if signal.trading_pair in subscription.plan.trading_pairs.all():
                self._send_notification(subscription.user, signal)
    
    def _send_notification(self, user, signal):
        """Send notification to a specific user"""
        # Create notification record
        notification = SignalNotification.objects.create(
            signal=signal,
            user=user
        )
        
        # Send via WebSocket
        self._send_websocket(user, signal)
        
        # Send email if user has email notifications enabled
        if user.profile.email_notifications:
            self._send_email(user, signal)
        
        # Send push notification if mobile app
        if user.profile.push_notifications:
            self._send_push(user, signal)
    
    def _send_websocket(self, user, signal):
        """Send real-time WebSocket notification"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}',
            {
                'type': 'trading_signal',
                'signal': {
                    'id': signal.id,
                    'trading_pair': signal.trading_pair.symbol,
                    'type': signal.signal_type,
                    'entry_price': str(signal.entry_price),
                    'stop_loss': str(signal.stop_loss),
                    'take_profit': str(signal.take_profit),
                    'confidence': str(signal.confidence),
                    'analysis': signal.analysis
                }
            }
        )
    
    def _send_email(self, user, signal):
        """Send email notification"""
        subject = f'New Trading Signal: {signal.trading_pair.symbol}'
        message = f"""
        New {signal.signal_type.upper()} signal for {signal.trading_pair.symbol}
        
        Entry Price: {signal.entry_price}
        Stop Loss: {signal.stop_loss}
        Take Profit: {signal.take_profit}
        Confidence: {signal.confidence}%
        
        Analysis:
        {signal.analysis}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )