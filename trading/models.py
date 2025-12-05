# trading/models.py
from django.db import models
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model() 


class AssetCategory(models.Model):
    """Asset categories for different markets"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)  # CRYPTO, STOCK, FOREX, COMMODITY, BOND
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    trading_hours_start = models.TimeField(null=True, blank=True)  # For stocks/bonds
    trading_hours_end = models.TimeField(null=True, blank=True)
    trading_days = models.JSONField(default=list)  # [1,2,3,4,5] for Mon-Fri
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Asset Categories"

class TradingPair(models.Model):
    """Available trading pairs across all asset classes"""
    
    EXCHANGE_CHOICES = [
        ('NASDAQ', 'NASDAQ'),
        ('NYSE', 'NYSE'),
        ('COINBASE', 'Coinbase'),
        ('BINANCE', 'Binance'),
        ('FX', 'Forex'),
        ('TVC', 'TradingView Commodities'),
    ]
        
    
    symbol = models.CharField(max_length=20, unique=True)  # BTC/USD, AAPL, EUR/USD, GOLD, US10Y
    name = models.CharField(max_length=100)  # Full name: Bitcoin, Apple Inc., etc.
    base_currency = models.CharField(max_length=10)
    quote_currency = models.CharField(max_length=10)
    asset_category = models.ForeignKey(
        AssetCategory, 
        on_delete=models.CASCADE,
        related_name='trading_pairs'
    )
    market_type = models.CharField(
        max_length=20,
        choices=[
            ('crypto', 'Cryptocurrency'),
            ('stock', 'Stock'),
            ('forex', 'Forex'),
            ('commodity', 'Commodity'),
            ('bond', 'Bond'),
            ('etf', 'ETF'),
            ('index', 'Index')
        ]
    )
    exchange = models.CharField(max_length=50, choices=EXCHANGE_CHOICES, blank=True)  # NASDAQ, NYSE, BINANCE, etc.
    isin = models.CharField(max_length=12, blank=True)  # For stocks/bonds
    country_code = models.CharField(max_length=2, blank=True)  # US, GB, etc.
    sector = models.CharField(max_length=50, blank=True)  # Technology, Energy, etc.
    
    # Trading specifications
    is_active = models.BooleanField(default=True)
    min_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    max_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    price_precision = models.IntegerField(default=2)
    quantity_precision = models.IntegerField(default=8)
    trading_fee_percentage = models.DecimalField(max_digits=5, decimal_places=4)
    percentage_change_24h = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    
    # Market-specific fields
    allow_short_selling = models.BooleanField(default=False)
    allow_fractional_shares = models.BooleanField(default=False)  # For stocks
    margin_requirement = models.DecimalField(max_digits=5, decimal_places=2, default=100)  # Percentage
    contract_size = models.DecimalField(max_digits=20, decimal_places=2, null=True)  # For commodities/forex
    
    high = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    low = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    open = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    close = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    
    # Additional info
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    
    # Market data caching
    last_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    price_change_24h = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    volume_24h = models.DecimalField(max_digits=30, decimal_places=2, null=True)
    market_cap = models.DecimalField(max_digits=30, decimal_places=2, null=True)
    last_updated = models.DateTimeField(null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['symbol']
        indexes = [
            models.Index(fields=['market_type', 'is_active']),
            models.Index(fields=['symbol']),
        ]


class Order(models.Model):
    """Trading orders with industry-standard leverage and expiration"""
    
    ORDER_TYPES = [
        ('market', 'Market Order'),
        ('limit', 'Limit Order'),
        ('stop_loss', 'Stop Order'),
        ('take_profit', 'Take Profit Order')
    ]
    
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('partially_filled', 'Partially Filled'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired')  # ADD THIS for expired orders
    ]
    
    # ✅ UPDATED: Industry-Standard Leverage Choices
    LEVERAGE_CHOICES = [
        ('1', '1x (No Leverage)'),
        ('2', '2x'),
        ('3', '3x'),
        ('5', '5x'),
        ('10', '10x'),
        ('20', '20x'),
        ('25', '25x'),
        ('50', '50x'),
        ('75', '75x'),
        ('100', '100x'),
        ('125', '125x'),
    ]
    
    # ✅ UPDATED: Industry-Standard Expiration Choices
    EXPIRATION_CHOICES = [
        ('60s', '60 Seconds'),
        ('2m', '2 Minutes'),
        ('5m', '5 Minutes'),
        ('10m', '10 Minutes'),
        ('15m', '15 Minutes'),
        ('30m', '30 Minutes'),
        ('1h', '1 Hour'),
        ('2h', '2 Hours'),
        ('4h', '4 Hours'),
        ('1d', '1 Day (End of Day)'),
        ('1w', '1 Week (End of Week)'),
        ('1M', '1 Month (End of Month)'),
        ('gtc', 'Good Till Cancelled'),  # For limit orders
    ]
    
    SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('bot', 'AI Bot'),
        ('copy_trade', 'Copy Trade'),
        ('signal', 'Signal')
    ]   
    
    # Relationships
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    
    # Order details
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    
    # Execution details
    filled_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0')
    )
    average_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # ✅ UPDATED: Leverage and Expiration
    leverage = models.CharField(
        max_length=3,
        choices=LEVERAGE_CHOICES,
        default='1',
        help_text='Position leverage multiplier'
    )
    
    expiration_type = models.CharField(
        max_length=5,
        choices=EXPIRATION_CHOICES,
        default='gtc',
        help_text='Order expiration type'
    )
    
    # ✅ NEW: Calculated expiration timestamp
    expiration_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Exact time when order expires'
    )
    
    # Fees and costs
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    
    # Source tracking
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='manual'
    )
    source_id = models.IntegerField(null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['trading_pair', 'status']),
            models.Index(fields=['expiration_time']),
        ]
    
    def save(self, *args, **kwargs):
        """Calculate expiration_time based on expiration_type"""
        if not self.expiration_time and self.expiration_type != 'gtc':
            self.expiration_time = self._calculate_expiration_time()
        
        super().save(*args, **kwargs)
    
    def _calculate_expiration_time(self):
        """Calculate exact expiration timestamp"""
        now = timezone.now()
        exp_type = self.expiration_type
        
        # Time-based expirations
        if exp_type.endswith('s'):  # Seconds
            seconds = int(exp_type[:-1])
            return now + timedelta(seconds=seconds)
        
        elif exp_type.endswith('m'):  # Minutes
            minutes = int(exp_type[:-1])
            return now + timedelta(minutes=minutes)
        
        elif exp_type.endswith('h'):  # Hours
            hours = int(exp_type[:-1])
            return now + timedelta(hours=hours)
        
        elif exp_type == '1d':  # End of day
            return now.replace(hour=23, minute=59, second=59, microsecond=0)
        
        elif exp_type == '1w':  # End of week (Sunday)
            days_ahead = 6 - now.weekday()
            if days_ahead < 0:
                days_ahead += 7
            end_of_week = now + timedelta(days=days_ahead)
            return end_of_week.replace(hour=23, minute=59, second=59, microsecond=0)
        
        elif exp_type == '1M':  # End of month
            from calendar import monthrange
            last_day = monthrange(now.year, now.month)[1]
            return now.replace(
                day=last_day,
                hour=23,
                minute=59,
                second=59,
                microsecond=0
            )
        
        return None
    
    def is_expired(self):
        """Check if order has expired"""
        if self.expiration_type == 'gtc':
            return False
        
        if self.expiration_time:
            return timezone.now() > self.expiration_time
        
        return False
    
    def get_leverage_multiplier(self):
        """Get leverage as a decimal multiplier"""
        return Decimal(self.leverage)
    
    def get_position_size(self):
        """Calculate actual position size with leverage"""
        return self.quantity * self.get_leverage_multiplier()
    
    def get_margin_required(self):
        """Calculate margin required for this order"""
        position_value = self.quantity * (self.price or Decimal('0'))
        return position_value / self.get_leverage_multiplier()
    
    def __str__(self):
        return f"{self.side.upper()} {self.quantity} {self.trading_pair.symbol} @ {self.price or 'Market'}"


class Trade(models.Model):
    """Executed trades - No changes needed here"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    external_trade_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-executed_at']
    
    def __str__(self):
        return f"Trade #{self.id} - {self.quantity} @ {self.price}"

class Position(models.Model):
    """Open positions for users"""
    
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
    ]
    
    POSITION_SIDE = (
        ('long', 'Long'),
        ('short', 'Short')
    )
    
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    side = models.CharField(
        max_length=50, 
        choices=POSITION_SIDE
    )
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    
    # ✅ CHANGED: Keep as DecimalField for calculations
    # This is fine - it stores numeric leverage value (1.00, 10.00, etc.)
    leverage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('1.00'),
        help_text='Position leverage multiplier (1.00 = no leverage)'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        help_text='Position status (open or closed)'
    )
    
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['user', 'trading_pair']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.trading_pair.symbol} - {self.side} ({self.leverage}x)"
    
    def get_position_value(self):
        """Calculate total position value with leverage"""
        return self.quantity * self.current_price * self.leverage
    
    def get_margin_used(self):
        """Calculate margin used for this position"""
        position_value = self.quantity * self.entry_price
        return position_value / self.leverage
    
    def get_pnl_percentage(self):
        """Calculate P&L as percentage of entry value"""
        if self.entry_price == 0:
            return Decimal('0')
        
        entry_value = self.quantity * self.entry_price
        return (self.unrealized_pnl / entry_value) * 100
  
  

  
class Transaction(models.Model):
    """
    Records ALL balance changes for audit trail and accounting
    Every financial movement creates a transaction record
    """
    
    # Transaction Types
    TYPE_DEPOSIT = 'deposit'
    TYPE_WITHDRAWAL = 'withdrawal'
    TYPE_TRANSFER_TO_TRADING = 'transfer_to_trading'
    TYPE_TRANSFER_FROM_TRADING = 'transfer_from_trading'
    TYPE_ORDER_FEE = 'order_fee'
    TYPE_POSITION_OPEN = 'position_open'
    TYPE_POSITION_CLOSE = 'position_close'
    TYPE_PROFIT = 'profit'
    TYPE_LOSS = 'loss'
    TYPE_COMMISSION = 'commission'
    TYPE_REFUND = 'refund'
    TYPE_BONUS = 'bonus'
    TYPE_ADJUSTMENT = 'adjustment'  # Manual admin adjustments
    
    TRANSACTION_TYPES = [
        (TYPE_DEPOSIT, 'Deposit'),
        (TYPE_WITHDRAWAL, 'Withdrawal'),
        (TYPE_TRANSFER_TO_TRADING, 'Transfer to Trading'),
        (TYPE_TRANSFER_FROM_TRADING, 'Transfer from Trading'),
        (TYPE_ORDER_FEE, 'Order Fee'),
        (TYPE_POSITION_OPEN, 'Position Opened'),
        (TYPE_POSITION_CLOSE, 'Position Closed'),
        (TYPE_PROFIT, 'Profit'),
        (TYPE_LOSS, 'Loss'),
        (TYPE_COMMISSION, 'Commission'),
        (TYPE_REFUND, 'Refund'),
        (TYPE_BONUS, 'Bonus'),
        (TYPE_ADJUSTMENT, 'Manual Adjustment'),
    ]
    
    # Balance Types
    BALANCE_DEPOSIT = 'deposit'
    BALANCE_TRADING = 'trading'
    
    BALANCE_TYPES = [
        (BALANCE_DEPOSIT, 'Deposit Balance'),
        (BALANCE_TRADING, 'Trading Balance'),
    ]
    
    # Status
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    POSITION_SIDE = (
        ('long', 'Long'),
        ('short', 'Short')
    )
    
    # Core Fields
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='main_transactions'
    )
    
    transaction_type = models.CharField(
        max_length=30,
        choices=TRANSACTION_TYPES,
        db_index=True
    )
    
    balance_type = models.CharField(
        max_length=20,
        choices=BALANCE_TYPES,
        default=BALANCE_DEPOSIT,
        help_text="Which balance this transaction affects"
    )
    
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Positive for credits, negative for debits"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETED,
        db_index=True
    )
    
    position_side = models.CharField(
        max_length=5,
        choices=POSITION_SIDE,
        default='long',
        help_text="Position side (long or short)"
    )
    
    # Balances After Transaction (for audit trail)
    balance_before = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Balance before this transaction"
    )
    
    balance_after = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Balance after this transaction"
    )
    
    # Related Objects
    order = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        help_text="Related order if applicable"
    )
    
    position = models.ForeignKey(
        'Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        help_text="Related position if applicable"
    )
    
    # Additional Info
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of the transaction"
    )
    
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="External reference ID (e.g., payment gateway transaction ID)"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional transaction metadata"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['user', 'balance_type']),
            models.Index(fields=['status', '-created_at']),
        ]
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.user.username} - {self.get_transaction_type_display()} - {sign}${self.amount}"
    
    def save(self, *args, **kwargs):
        # Auto-generate description if not provided
        if not self.description:
            self.description = self.generate_description()
        
        super().save(*args, **kwargs)
    
    def generate_description(self):
        """Generate human-readable description"""
        sign = '+' if self.amount >= 0 else ''
        amount_str = f"{sign}${abs(self.amount)}"
        
        descriptions = {
            self.TYPE_DEPOSIT: f"Deposit of {amount_str}",
            self.TYPE_WITHDRAWAL: f"Withdrawal of {amount_str}",
            self.TYPE_TRANSFER_TO_TRADING: f"Transferred {amount_str} to trading balance",
            self.TYPE_TRANSFER_FROM_TRADING: f"Transferred {amount_str} from trading balance",
            self.TYPE_ORDER_FEE: f"Order fee: {amount_str}",
            self.TYPE_POSITION_OPEN: f"Opened position - {amount_str}",
            self.TYPE_POSITION_CLOSE: f"Closed position - {amount_str}",
            self.TYPE_PROFIT: f"Trading profit: {amount_str}",
            self.TYPE_LOSS: f"Trading loss: {amount_str}",
            self.TYPE_COMMISSION: f"Commission: {amount_str}",
            self.TYPE_REFUND: f"Refund: {amount_str}",
            self.TYPE_BONUS: f"Bonus: {amount_str}",
            self.TYPE_ADJUSTMENT: f"Balance adjustment: {amount_str}",
        }
        
        return descriptions.get(self.transaction_type, f"Transaction: {amount_str}")
    
    @property
    def is_credit(self):
        """Returns True if this is a credit (positive) transaction"""
        return self.amount > 0
    
    @property
    def is_debit(self):
        """Returns True if this is a debit (negative) transaction"""
        return self.amount < 0


# ===== HELPER FUNCTION TO CREATE TRANSACTIONS =====

def create_transaction(user, transaction_type, amount, balance_type='deposit', 
                       order=None, position=None, description='', metadata=None):
    """
    Helper function to create a transaction and update account balance
    
    Args:
        user: User object
        transaction_type: Type of transaction (from Transaction.TYPE_*)
        amount: Amount (positive for credit, negative for debit)
        balance_type: Which balance to affect ('deposit' or 'trading')
        order: Optional Order object
        position: Optional Position object
        description: Optional description
        metadata: Optional metadata dict
    
    Returns:
        Transaction object
    """
    from users.models import Account
    
    # Get or create account
    account, _ = Account.objects.get_or_create(user=user)
    
    # Determine which balance to use
    if balance_type == 'trading':
        balance_before = account.trading_balance
    else:
        balance_before = account.deposit_balance
    
    # Calculate new balance
    balance_after = balance_before + Decimal(str(amount))
    
    # Create transaction
    transaction = Transaction.objects.create(
        user=user,
        transaction_type=transaction_type,
        balance_type=balance_type,
        amount=Decimal(str(amount)),
        balance_before=balance_before,
        balance_after=balance_after,
        order=order,
        position=position,
        description=description,
        metadata=metadata or {},
        status=Transaction.STATUS_COMPLETED,
        completed_at=timezone.now()
    )
    
    # Update account balance
    if balance_type == 'trading':
        account.trading_balance = balance_after
    else:
        account.deposit_balance = balance_after
    
    account.save()
    
    return transaction
    
    
    
    