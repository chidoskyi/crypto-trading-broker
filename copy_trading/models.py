# copy_trading/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Trader(models.Model):
    """Master traders that others can copy"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    total_followers = models.IntegerField(default=0)
    
    # ✅ ADD THIS
    minimum_investment = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('10.00'))],
        help_text="Minimum trading balance required to copy this trader"
    )
    
    total_profit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    profit_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    total_trades = models.IntegerField(default=0)
    risk_score = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ✅ ADD THIS METHOD
    def update_performance_metrics(self):
        """Calculate and update performance metrics from realized P&L"""
        from trading.models import Position, Order
        from django.db.models import Sum, Count, Q
        
        # Get all filled orders by this trader
        filled_orders = Order.objects.filter(
            user=self.user,
            status='filled'
        )
        
        # Get all closed positions (where we have realized P&L)
        closed_positions = Position.objects.filter(
            user=self.user,
            status='closed',
            realized_pnl__isnull=False
        )
        
        # Calculate total profit from realized P&L
        total_profit = closed_positions.aggregate(
            total=Sum('realized_pnl')
        )['total'] or Decimal('0.00')
        
        # Count winning and losing trades
        winning_trades = closed_positions.filter(realized_pnl__gt=0).count()
        losing_trades = closed_positions.filter(realized_pnl__lt=0).count()
        total_closed = closed_positions.count()
        
        # Calculate win rate
        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else Decimal('0.00')
        
        # Calculate profit percentage (based on initial investment vs profit)
        # You can adjust this calculation based on your needs
        total_invested = closed_positions.aggregate(
            total=Sum('quantity') * Sum('entry_price')
        )
        
        # Simple profit percentage calculation
        if total_closed > 0:
            avg_position_size = closed_positions.aggregate(
                avg=Sum('quantity') * Sum('entry_price') / Count('id')
            )['avg'] or Decimal('1.00')
            
            profit_percentage = (total_profit / (avg_position_size * total_closed) * 100) if avg_position_size > 0 else Decimal('0.00')
        else:
            profit_percentage = Decimal('0.00')
        
        # Update fields
        self.total_profit = total_profit
        self.profit_percentage = profit_percentage
        self.win_rate = win_rate
        self.total_trades = total_closed
        self.save(update_fields=[
            'total_profit', 'profit_percentage', 'win_rate', 'total_trades'
        ])


class CopyTradingSubscription(models.Model):
    """User subscriptions to copy traders"""
    
    # Copy Sizing Modes (How Much to Copy)
    MODE_PROPORTIONAL = 'proportional'
    MODE_FIXED = 'fixed'
    
    SIZING_MODES = [
        (MODE_PROPORTIONAL, _('Proportional (Same % of trading balance)')),
        (MODE_FIXED, _('Fixed (Fixed amount per trade)')),
    ]

    # Execution Modes (How to Execute the Copy)
    EXEC_MANUAL = 'manual'
    EXEC_AUTO = 'auto'
    
    EXECUTION_MODES = [
        (EXEC_MANUAL, _('Manual (Requires confirmation)')),
        (EXEC_AUTO, _('Auto (Instant execution)')),
    ]
    
    follower = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='copy_subscriptions'
    )
    trader = models.ForeignKey(
        Trader,
        on_delete=models.CASCADE,
        related_name='subscribers'
    )
    is_active = models.BooleanField(default=True)
    
    # Position size limit per trade
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum amount to allocate per trade"
    )
    
    # Stop loss percentage
    stop_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Stop loss percentage for copied trades"
    )
    
    # Copy percentage (for proportional mode)
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))],
        help_text="Percentage of available trading balance to allocate"
    )

    # Fixed amount per trade (for fixed mode)
    fixed_amount_per_trade = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Fixed Amount per Trade'),
        help_text="Fixed dollar amount to allocate per trade"
    )
    
    # Sizing mode: Determines the amount of capital used
    sizing_mode = models.CharField(
        max_length=20,
        choices=SIZING_MODES,
        default=MODE_PROPORTIONAL,
        verbose_name=_('Trade Sizing Mode')
    )
    
    # Execution mode: Determines the automation level
    execution_mode = models.CharField(
        max_length=20,
        choices=EXECUTION_MODES,
        default=EXEC_AUTO,
        verbose_name=_('Trade Execution Mode')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'copy_trading_subscription'
        verbose_name = 'Copy Trading Subscription'
        verbose_name_plural = 'Copy Trading Subscriptions'
        unique_together = ['follower', 'trader']
        indexes = [
            models.Index(fields=['follower', 'is_active']),
            models.Index(fields=['trader', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.follower.username} → {self.trader.display_name}"

    def clean(self):
        """Validate subscription settings"""
        super().clean()
        
        # Prevent self-copying
        if self.follower == self.trader.user:
            raise ValidationError({
                'trader': 'You cannot copy your own trades'
            })
        
        # Validate sizing mode requirements
        if self.sizing_mode == self.MODE_FIXED:
            if not self.fixed_amount_per_trade or self.fixed_amount_per_trade <= 0:
                raise ValidationError({
                    'fixed_amount_per_trade': 'Fixed amount is required and must be greater than 0 for fixed sizing mode'
                })
        
        # Validate copy percentage for proportional mode
        if self.sizing_mode == self.MODE_PROPORTIONAL:
            if not self.copy_percentage or self.copy_percentage <= 0:
                raise ValidationError({
                    'copy_percentage': 'Copy percentage must be greater than 0 for proportional sizing mode'
                })
        
        # Validate stop loss
        if self.stop_loss_percentage and (self.stop_loss_percentage <= 0 or self.stop_loss_percentage > 100):
            raise ValidationError({
                'stop_loss_percentage': 'Stop loss must be between 0 and 100'
            })

    def save(self, *args, **kwargs):
        """Override save to run validations"""
        self.full_clean()
        super().save(*args, **kwargs)


class CopiedTrade(models.Model):
    """Record of trades copied from master traders"""
    
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_REJECTED = 'rejected'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Execution'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REJECTED, 'Rejected by Follower'),
        (STATUS_FAILED, 'Failed Execution'),
    ]
    
    subscription = models.ForeignKey(
        CopyTradingSubscription, 
        on_delete=models.CASCADE,
        related_name='copied_trades'
    )
    master_order = models.ForeignKey(
        'trading.Order', 
        on_delete=models.CASCADE, 
        related_name='copied_as_master'
    )
    follower_order = models.ForeignKey(
        'trading.Order', 
        on_delete=models.CASCADE, 
        related_name='copied_as_follower',
        null=True,
        blank=True,
        help_text="Null for pending trades in manual mode"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default=STATUS_PENDING
    )
    
    # Store calculated values for reference
    calculated_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Quantity calculated for this trade"
    )
    allocated_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dollar amount allocated from trading balance"
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if trade failed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'copy_trading_copied_trade'
        verbose_name = 'Copied Trade'
        verbose_name_plural = 'Copied Trades'
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"CopiedTrade #{self.id} - {self.status}"


class CopyTradingPerformance(models.Model):
    """Track performance metrics for copy trading subscriptions"""
    
    subscription = models.OneToOneField(
        CopyTradingSubscription,
        on_delete=models.CASCADE,
        related_name='performance'
    )
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    total_profit_loss = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_invested = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount invested through this subscription"
    )
    
    # Win rate
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Average metrics
    average_profit_per_trade = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00')
    )
    average_loss_per_trade = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Best and worst trades
    best_trade_profit = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00')
    )
    worst_trade_loss = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Timestamps
    last_trade_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'copy_trading_performance'
        verbose_name = 'Copy Trading Performance'
        verbose_name_plural = 'Copy Trading Performance'

    def __str__(self):
        return f"Performance: {self.subscription}"

    def update_metrics(self):
        """Recalculate all performance metrics from completed trades"""
        from django.db.models import Sum, Count, Avg, Max, Min
        from trading.models import Position

        # Get all completed copied trades for this subscription
        completed_trades = self.subscription.copied_trades.filter(
            status=CopiedTrade.STATUS_COMPLETED,
            follower_order__isnull=False
        ).select_related('follower_order')
    
        # Reset counters
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit_loss = Decimal('0.00')
        self.total_invested = Decimal('0.00')
        self.best_trade_profit = Decimal('0.00')
        self.worst_trade_loss = Decimal('0.00')
        
        profitable_trades = []
        losing_trades = []
        
        # Process each completed trade
        for copied_trade in completed_trades:
            self.total_trades += 1
            
            # Add allocated amount to total invested
            if copied_trade.allocated_amount:
                self.total_invested += copied_trade.allocated_amount
            
            # Get position data for P&L calculation
            try:
                # Find position created by this order
                position = Position.objects.get(order=copied_trade.follower_order)
                
                # Only count closed positions with realized P&L
                if position.status == 'closed' and position.realized_pnl is not None:
                    pnl = position.realized_pnl
                    self.total_profit_loss += pnl
                    
                    if pnl > 0:
                        self.winning_trades += 1
                        profitable_trades.append(pnl)
                        
                        # Update best trade
                        if pnl > self.best_trade_profit:
                            self.best_trade_profit = pnl
                            
                    elif pnl < 0:
                        self.losing_trades += 1
                        losing_trades.append(pnl)
                        
                        # Update worst trade
                        if pnl < self.worst_trade_loss:
                            self.worst_trade_loss = pnl
                    
                    # Update last trade timestamp
                    if position.closed_at:
                        if not self.last_trade_at or position.closed_at > self.last_trade_at:
                            self.last_trade_at = position.closed_at
                
            except Position.DoesNotExist:
                # No position found for this order (could be cancelled/rejected)
                pass
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing trade {copied_trade.id}: {e}")
        
        # Calculate win rate
        total_closed_trades = self.winning_trades + self.losing_trades
        if total_closed_trades > 0:
            self.win_rate = (self.winning_trades / total_closed_trades * 100)
        else:
            self.win_rate = Decimal('0.00')
        
        # Calculate average profit per winning trade
        if self.winning_trades > 0 and profitable_trades:
            self.average_profit_per_trade = sum(profitable_trades) / len(profitable_trades)
        else:
            self.average_profit_per_trade = Decimal('0.00')
        
        # Calculate average loss per losing trade
        if self.losing_trades > 0 and losing_trades:
            self.average_loss_per_trade = sum(losing_trades) / len(losing_trades)
        else:
            self.average_loss_per_trade = Decimal('0.00')
        
        # Save all updates
        self.save()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Updated performance metrics for subscription {self.subscription.id}: "
            f"{self.winning_trades}W/{self.losing_trades}L, "
            f"Win Rate: {self.win_rate}%, "
            f"Total P&L: ${self.total_profit_loss}"
        )