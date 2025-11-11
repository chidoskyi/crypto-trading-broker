# copy_trading/models.py
from django.db import models

class Trader(models.Model):
    """Master traders that others can copy"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    total_followers = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2)
    profit_percentage = models.DecimalField(max_digits=10, decimal_places=2)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_trades = models.IntegerField(default=0)
    risk_score = models.IntegerField(default=5)  # 1-10
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CopyTradingSubscription(models.Model):
    """User subscriptions to copy traders"""
    follower = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='following'
    )
    trader = models.ForeignKey(
        Trader,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    is_active = models.BooleanField(default=True)
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )  # % of capital to allocate
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    stop_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['follower', 'trader']

    

class CopiedTrade(models.Model):
    """Record of trades copied from master traders"""
    subscription = models.ForeignKey(CopyTradingSubscription, on_delete=models.CASCADE)
    master_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='master_order')
    follower_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='follower_order')
    created_at = models.DateTimeField(auto_now_add=True)