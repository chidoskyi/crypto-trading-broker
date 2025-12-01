# copy_trading/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

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
    """
    Defines the contract between a Follower (user copying) and a Trader (user being copied).
    """

    # --- 1. Copy Sizing Modes (How Much to Copy) ---
    MODE_PROPORTIONAL = 'proportional'
    MODE_FIXED = 'fixed'
    
    SIZING_MODES = [
        (MODE_PROPORTIONAL, _('Proportional (Same % of capital)')),
        (MODE_FIXED, _('Fixed (Fixed amount per trade)')),
    ]

    # --- 2. Execution Modes (How to Execute the Copy) ---
    EXEC_MANUAL = 'manual'
    EXEC_AUTO = 'auto'
    
    EXECUTION_MODES = [
        (EXEC_MANUAL, _('Manual (Requires confirmation)')),
        (EXEC_AUTO, _('Auto (Instant execution)')),
    ]
    
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
    
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))] # Add MaxValueValidator
    )

    # Capital Allocation for fixed sizing
    fixed_amount_per_trade = models.DecimalField( # ADD THIS FIELD
        max_digits=20,
        decimal_places=8,
        null=True, blank=True,
        verbose_name=_('Fixed Amount per Trade')
    )
    # 1. SIZING MODE: Determines the amount of capital used (Proportional/Fixed)
    sizing_mode = models.CharField(
        max_length=20,
        choices=SIZING_MODES,
        default=MODE_PROPORTIONAL,
        verbose_name=_('Trade Sizing Mode')
    )
    # 2. EXECUTION MODE: Determines the automation level (Auto/Manual)
    execution_mode = models.CharField(
        max_length=20,
        choices=EXECUTION_MODES,
        default=EXEC_AUTO,
        verbose_name=_('Trade Execution Mode')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['follower', 'trader']

    

class CopiedTrade(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_REJECTED = 'rejected'
    STATUS_FAILED = 'failed' # e.g., Insufficient funds

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Execution'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REJECTED, 'Rejected by Follower'),
        (STATUS_FAILED, 'Failed Execution'),
    ]
    """Record of trades copied from master traders"""
    subscription = models.ForeignKey(CopyTradingSubscription, on_delete=models.CASCADE)
    master_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='master_order')
    follower_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='follower_order')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)