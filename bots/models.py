# bots/models.py
from django.db import models

class TradingBot(models.Model):
    """AI trading bot configurations"""
    STRATEGY_CHOICES = [
        ('moving_average', 'Moving Average Crossover'),
        ('rsi', 'RSI Strategy'),
        ('macd', 'MACD Strategy'),
        ('bollinger', 'Bollinger Bands'),
        ('arbitrage', 'Arbitrage'),
        ('ml_model', 'Machine Learning Model'),
        ('custom', 'Custom Strategy')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=False)
    is_paper_trading = models.BooleanField(default=True)
    
    # Risk management
    max_position_size = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    take_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Strategy parameters (JSON for flexibility)
    parameters = models.JSONField(default=dict)
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

class BotTrade(models.Model):
    """Trades executed by bots"""
    bot = models.ForeignKey(TradingBot, on_delete=models.CASCADE)
    order = models.ForeignKey('trading.Order', on_delete=models.CASCADE)
    signal_data = models.JSONField()  # Store the signal that triggered the trade
    created_at = models.DateTimeField(auto_now_add=True)