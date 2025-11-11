# bots/services/bot_engine.py
import numpy as np
import pandas as pd
from decimal import Decimal
from django.utils import timezone
from bots.models import TradingBot, BotTrade
from trading.services.order_service import OrderExecutionService
from trading.services.market_service import MarketDataService

class BotEngine:
    """Execute trading bot strategies"""
    
    def __init__(self, bot):
        self.bot = bot
        self.market_service = MarketDataService()
        self.order_service = OrderExecutionService()
    
    def run(self):
        """Execute bot trading logic"""
        if not self.bot.is_active:
            return
        
        # Check daily loss limit
        if self._check_daily_loss_limit():
            self.bot.is_active = False
            self.bot.save()
            return
        
        # Run strategy for each trading pair
        for trading_pair in self.bot.trading_pairs.all():
            try:
                signal = self._generate_signal(trading_pair)
                if signal:
                    self._execute_signal(signal, trading_pair)
            except Exception as e:
                print(f"Error running bot {self.bot.id}: {e}")
        
        self.bot.last_run_at = timezone.now()
        self.bot.save()
    
    def _generate_signal(self, trading_pair):
        """Generate trading signal based on strategy"""
        if self.bot.strategy == 'moving_average':
            return self._moving_average_strategy(trading_pair)
        elif self.bot.strategy == 'rsi':
            return self._rsi_strategy(trading_pair)
        elif self.bot.strategy == 'macd':
            return self._macd_strategy(trading_pair)
        # Add more strategies...
        return None
    
    def _moving_average_strategy(self, trading_pair):
        """Moving Average Crossover Strategy"""
        params = self.bot.parameters
        short_period = params.get('short_period', 20)
        long_period = params.get('long_period', 50)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=long_period + 10
        )
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(historical_data)
        
        # Calculate moving averages
        df['sma_short'] = df['close'].rolling(window=short_period).mean()
        df['sma_long'] = df['close'].rolling(window=long_period).mean()
        
        # Get last two rows to detect crossover
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish crossover
        if (previous['sma_short'] <= previous['sma_long'] and 
            current['sma_short'] > current['sma_long']):
            return {
                'action': 'buy',
                'price': current['close'],
                'reason': 'MA Bullish Crossover'
            }
        
        # Bearish crossover
        elif (previous['sma_short'] >= previous['sma_long'] and 
              current['sma_short'] < current['sma_long']):
            return {
                'action': 'sell',
                'price': current['close'],
                'reason': 'MA Bearish Crossover'
            }
        
        return None
    
    def _rsi_strategy(self, trading_pair):
        """RSI Strategy"""
        params = self.bot.parameters
        period = params.get('rsi_period', 14)
        oversold = params.get('oversold_level', 30)
        overbought = params.get('overbought_level', 70)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=period + 10
        )
        
        df = pd.DataFrame(historical_data)
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Buy signal
        if current_rsi < oversold:
            return {
                'action': 'buy',
                'price': current_price,
                'reason': f'RSI Oversold: {current_rsi:.2f}'
            }
        
        # Sell signal
        elif current_rsi > overbought:
            return {
                'action': 'sell',
                'price': current_price,
                'reason': f'RSI Overbought: {current_rsi:.2f}'
            }
        
        return None
    
    def _execute_signal(self, signal, trading_pair):
        """Execute trading signal"""
        # Calculate position size
        quantity = self._calculate_position_size(trading_pair, signal['price'])
        
        if quantity <= 0:
            return
        
        # Create order
        order_data = {
            'trading_pair': trading_pair,
            'order_type': 'market',
            'side': signal['action'],
            'quantity': quantity,
            'source': 'bot',
            'source_id': self.bot.id
        }
        
        # Add stop loss and take profit
        if signal['action'] == 'buy':
            order_data['stop_price'] = (
                signal['price'] * (1 - self.bot.stop_loss_percentage / 100)
            )
        
        try:
            order = self.order_service.create_order(
                self.bot.user,
                order_data
            )
            
            # Record bot trade
            BotTrade.objects.create(
                bot=self.bot,
                order=order,
                signal_data=signal
            )
            
            # Update bot statistics
            self.bot.total_trades += 1
            self.bot.save()
            
        except Exception as e:
            print(f"Error executing bot signal: {e}")
    
    def _calculate_position_size(self, trading_pair, price):
        """Calculate position size based on risk management"""
        wallet = self.bot.user.wallet_set.get(
            currency=trading_pair.quote_currency
        )
        
        # Use configured max position size
        max_allocation = min(
            wallet.balance * Decimal('0.1'),  # Max 10% per trade
            self.bot.max_position_size
        )
        
        return max_allocation / Decimal(str(price))
    
    def _check_daily_loss_limit(self):
        """Check if daily loss limit exceeded"""
        today = timezone.now().date()
        
        # Calculate today's P&L
        today_trades = BotTrade.objects.filter(
            bot=self.bot,
            created_at__date=today
        ).select_related('order')
        
        total_pnl = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.order.price)
            for trade in today_trades
            if trade.order.status == 'filled'
        )
        
        return total_pnl < -self.bot.max_daily_loss