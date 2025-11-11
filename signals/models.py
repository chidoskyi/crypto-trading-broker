# signals/models.py
from django.db import models

class SignalProvider(models.Model):
    """Signal provider information"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('in_house', 'In-House'),
            ('third_party', 'Third Party')
        ]
    )
    accuracy_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_signals = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalPlan(models.Model):
    """Subscription plans for signals"""
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    max_signals_per_day = models.IntegerField()
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalSubscription(models.Model):
    """User subscriptions to signal plans"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    plan = models.ForeignKey(SignalPlan, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled')
        ],
        default='active'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

class TradingSignal(models.Model):
    """Trading signals"""
    SIGNAL_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('close', 'Close Position')
    ]
    
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    trading_pair = models.ForeignKey('trading.TradingPair', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    timeframe = models.CharField(max_length=20)  # 1h, 4h, 1d, etc.
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    analysis = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('hit_tp', 'Take Profit Hit'),
            ('hit_sl', 'Stop Loss Hit'),
            ('closed', 'Manually Closed'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class SignalNotification(models.Model):
    """Track signal notifications sent to users"""
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acted_on = models.BooleanField(default=False)