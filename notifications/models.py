# notifications/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    """General notification system for all platform events"""
    
    NOTIFICATION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('trade', 'Trade Executed'),
        ('order', 'Order Update'),
        ('kyc', 'KYC Update'),
        ('signal', 'Trading Signal'),
        ('copy_trade', 'Copy Trade Executed'),
        ('bot', 'Bot Activity'),
        ('loan', 'Loan Update'),
        ('referral', 'Referral Reward'),
        ('system', 'System Notification'),
        ('security', 'Security Alert'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, 
                            related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)  # URL to relevant page
    
    # Related objects (optional)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    
    # Notification state
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Priority
    priority = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='normal')
    
    # Delivery channels
    send_email = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"

class NotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                                related_name='notification_preferences')
    
    # Email notifications
    email_deposit = models.BooleanField(default=True)
    email_withdrawal = models.BooleanField(default=True)
    email_trade = models.BooleanField(default=True)
    email_signal = models.BooleanField(default=True)
    email_kyc = models.BooleanField(default=True)
    email_security = models.BooleanField(default=True)
    
    # Push notifications
    push_deposit = models.BooleanField(default=True)
    push_withdrawal = models.BooleanField(default=True)
    push_trade = models.BooleanField(default=True)
    push_signal = models.BooleanField(default=True)
    push_kyc = models.BooleanField(default=True)
    push_security = models.BooleanField(default=True)
    
    # In-app notifications
    app_all = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)