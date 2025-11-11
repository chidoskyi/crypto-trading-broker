# trading/models.py
from django.db import models
from decimal import Decimal

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
    
    class Meta:
        verbose_name_plural = "Asset Categories"

class TradingPair(models.Model):
    """Available trading pairs across all asset classes"""
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
    exchange = models.CharField(max_length=50, blank=True)  # NASDAQ, NYSE, BINANCE, etc.
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
    
    # Market-specific fields
    allow_short_selling = models.BooleanField(default=False)
    allow_fractional_shares = models.BooleanField(default=False)  # For stocks
    margin_requirement = models.DecimalField(max_digits=5, decimal_places=2, default=100)  # Percentage
    contract_size = models.DecimalField(max_digits=20, decimal_places=2, null=True)  # For commodities/forex
    
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
    """Trading orders"""
    ORDER_TYPES = [
        ('market', 'Market'),
        ('limit', 'Limit'),
        ('stop_loss', 'Stop Loss'),
        ('take_profit', 'Take Profit')
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
        ('rejected', 'Rejected')
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
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
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    source = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('bot', 'AI Bot'),
            ('copy_trade', 'Copy Trade'),
            ('signal', 'Signal')
        ],
        default='manual'
    )
    source_id = models.IntegerField(null=True)  # ID of bot/trader/signal
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)

class Trade(models.Model):
    """Executed trades"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    external_trade_id = models.CharField(max_length=100, blank=True)

class Position(models.Model):
    """Open positions for users"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    side = models.CharField(max_length=50, choices=[('long', 'Long'), ('short', 'Short')])
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    leverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)