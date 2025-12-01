# notifications/services.py
from django.core.mail import send_mail
from django.conf import settings
from notifications.models import Notification, NotificationPreference
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class NotificationService:
    """Central notification service"""
    
    @staticmethod
    def create_notification(user, notification_type, title, message, 
                          link='', priority='normal', send_email=False):
        """Create and send notification"""
        
        # Check user preferences
        try:
            prefs = NotificationPreference.objects.get(user=user)
            
            # Check if user wants this type of notification
            if not prefs.app_all:
                return None
                
            # Check email preference
            email_field = f'email_{notification_type}'
            if hasattr(prefs, email_field):
                send_email = send_email and getattr(prefs, email_field)
                
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            prefs = NotificationPreference.objects.create(user=user)
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            priority=priority,
            send_email=send_email
        )
        
        # Send via WebSocket (real-time)
        NotificationService.send_realtime(user, notification)
        
        # Send email if requested
        if send_email:
            NotificationService.send_email_notification(user, notification)
        
        return notification
    
    @staticmethod
    def send_realtime(user, notification):
        """Send real-time notification via WebSocket"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}',
            {
                'type': 'notification_message',
                'notification': {
                    'id': notification.id,
                    'type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'link': notification.link,
                    'priority': notification.priority,
                    'created_at': notification.created_at.isoformat()
                }
            }
        )
    
    @staticmethod
    def send_email_notification(user, notification):
        """Send email notification"""
        try:
            send_mail(
                subject=f'[Trading Platform] {notification.title}',
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
            
            notification.email_sent = True
            notification.save()
            
        except Exception as e:
            print(f"Error sending email: {e}")
    
    # Convenience methods for specific notification types
    
    @staticmethod
    def notify_deposit(user, amount, currency, tx_hash=''):
        """Notify user of deposit"""
        return NotificationService.create_notification(
            user=user,
            notification_type='deposit',
            title=f'Deposit Received: {amount} {currency}',
            message=f'Your deposit of {amount} {currency} has been credited to your account.',
            link=f'/transactions?type=deposit',
            priority='normal',
            send_email=True
        )
    
    @staticmethod
    def notify_withdrawal(user, amount, currency, status):
        """Notify user of withdrawal"""
        return NotificationService.create_notification(
            user=user,
            notification_type='withdrawal',
            title=f'Withdrawal {status}: {amount} {currency}',
            message=f'Your withdrawal of {amount} {currency} is {status}.',
            link=f'/transactions?type=withdrawal',
            priority='high',
            send_email=True
        )
    
    @staticmethod
    def notify_trade(user, order):
        """Notify user of trade execution"""
        return NotificationService.create_notification(
            user=user,
            notification_type='trade',
            title=f'Trade Executed: {order.trading_pair.symbol}',
            message=f'{order.side.title()} {order.quantity} {order.trading_pair.symbol} at {order.average_price}',
            link=f'/orders/{order.id}',
            priority='normal',
            send_email=False
        )
    
    @staticmethod
    def notify_kyc_status(user, status, reason=''):
        """Notify user of KYC status change"""
        message = f'Your KYC verification has been {status}.'
        if reason:
            message += f' Reason: {reason}'
            
        return NotificationService.create_notification(
            user=user,
            notification_type='kyc',
            title=f'KYC {status.title()}',
            message=message,
            link='/profile/kyc',
            priority='high',
            send_email=True
        )
    
    @staticmethod
    def notify_loan_status(user, loan, status):
        """Notify user of loan status"""
        return NotificationService.create_notification(
            user=user,
            notification_type='loan',
            title=f'Loan {status}: ${loan.amount}',
            message=f'Your loan application for ${loan.amount} has been {status}.',
            link=f'/loans/{loan.id}',
            priority='high',
            send_email=True
        )