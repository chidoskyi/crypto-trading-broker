# trading/services/market_service.py
"""
Optimized Market Data Service using the BEST FREE APIs:
1. Binance (FREE) - Crypto - Unlimited requests
2. yfinance (FREE) - Stocks, Bonds, Commodities, Forex - No API key needed
3. Alpha Vantage (FREE) - Forex backup - 500 requests/day

NO PAID APIs REQUIRED!
"""

import ccxt
import yfinance as yf
import requests
import time
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MarketDataService:
    """Unified service for fetching market data using best free APIs"""
    
    def __init__(self):
        # Initialize multi-source crypto service (NO API KEY REQUIRED!)
        self.crypto_service = None
        try:
            from trading.services.crypto_service import CryptoDataService
            self.crypto_service = CryptoDataService()
            logger.info("✅ Multi-source crypto service initialized (CoinGecko + exchanges)")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize crypto service: {e}")
        
        # Alpha Vantage for forex (optional backup)
        self.alpha_vantage_key = getattr(settings, 'ALPHA_VANTAGE_API_KEY', None)
        if self.alpha_vantage_key:
            logger.info("✅ Alpha Vantage API key found")
        else:
            logger.info("ℹ️ Alpha Vantage not configured - using yfinance for forex")
    
    def get_ticker(self, trading_pair):
        """Get current ticker data based on market type"""
        cache_key = f'ticker:{trading_pair.symbol}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        market_type = trading_pair.market_type
        
        try:
            if market_type == 'crypto':
                data = self._get_crypto_ticker(trading_pair)
            elif market_type == 'stock':
                data = self._get_stock_ticker(trading_pair)
            elif market_type == 'forex':
                data = self._get_forex_ticker(trading_pair)
            elif market_type == 'commodity':
                data = self._get_commodity_ticker(trading_pair)
            elif market_type == 'bond':
                data = self._get_bond_ticker(trading_pair)
            else:
                raise ValueError(f"Unsupported market type: {market_type}")
            
            # Cache for appropriate duration
            cache_timeout = 5 if market_type == 'crypto' else 60
            cache.set(cache_key, data, timeout=cache_timeout)
            
            return data
        except Exception as e:
            logger.error(f"Error fetching ticker for {trading_pair.symbol}: {e}")
            # Return stale cached data if available
            cached_data = cache.get(cache_key, version=None)
            if cached_data:
                logger.info(f"Returning stale cached data for {trading_pair.symbol}")
                return cached_data
            raise
    
    def _get_crypto_ticker(self, trading_pair):
        """Get cryptocurrency ticker using multi-source service (NO API KEY REQUIRED!)"""
        if not self.crypto_service:
            raise Exception("Crypto service not initialized")
        
        try:
            # Use multi-source crypto service (CoinGecko -> Kraken -> Coinbase -> others)
            return self.crypto_service.get_crypto_ticker(trading_pair.symbol)
        except Exception as e:
            raise Exception(f"Crypto data unavailable for {trading_pair.symbol}: {str(e)}")
    
    def _get_stock_ticker(self, trading_pair):
        """Get stock ticker using yfinance (FREE - no API key needed)"""
        try:
            time.sleep(0.5)  # Rate limiting: 500ms between requests
            
            stock = yf.Ticker(trading_pair.base_currency)
            history = stock.history(period='5d')  # Get last 5 days
            
            if history.empty:
                raise ValueError(f"No stock data available for {trading_pair.base_currency}")
            
            # Get today's data
            last_price = history['Close'].iloc[-1]
            open_price = history['Open'].iloc[-1]  # TODAY'S OPEN
            volume = history['Volume'].iloc[-1] if 'Volume' in history else 0
            high = history['High'].iloc[-1]
            low = history['Low'].iloc[-1]
            
            # Calculate change percentage from today's open
            change_pct = 0
            if open_price:
                change_pct = ((last_price - open_price) / open_price) * 100
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': Decimal(str(last_price)),
                'open': Decimal(str(open_price)),  # ADD THIS
                'close': Decimal(str(last_price)),  # ADD THIS
                'bid': Decimal(str(last_price * 0.9999)),
                'ask': Decimal(str(last_price * 1.0001)),
                'volume': Decimal(str(volume)),
                'change_24h': Decimal(str(change_pct)),
                'high_24h': Decimal(str(high)),
                'low_24h': Decimal(str(low)),
                'market_cap': Decimal('0'),
                'market_type': 'stock'
            }
        except Exception as e:
            raise Exception(f"Stock data unavailable: {str(e)}")
    
    def _get_forex_ticker(self, trading_pair):
        """Get forex ticker using yfinance (FREE) with Alpha Vantage backup"""
        # Try Alpha Vantage first if available (more accurate)
        if self.alpha_vantage_key:
            try:
                return self._get_forex_alpha_vantage(trading_pair)
            except Exception as e:
                logger.warning(f"Alpha Vantage forex failed, falling back to yfinance: {e}")
        
        # Fallback to yfinance (always works, no key needed)
        return self._get_forex_yfinance(trading_pair)
    
    def _get_forex_alpha_vantage(self, trading_pair):
        """Get forex from Alpha Vantage (FREE - 500 requests/day)"""
        url = 'https://www.alphavantage.co/query'
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': trading_pair.base_currency,
            'to_currency': trading_pair.quote_currency,
            'apikey': self.alpha_vantage_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'Realtime Currency Exchange Rate' in data:
            rate_data = data['Realtime Currency Exchange Rate']
            last_price = Decimal(rate_data['5. Exchange Rate'])
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': last_price,
                'bid': Decimal(rate_data.get('8. Bid Price', last_price)),
                'ask': Decimal(rate_data.get('9. Ask Price', last_price)),
                'volume': Decimal('0'),
                'change_24h': Decimal('0'),
                'high_24h': last_price,
                'low_24h': last_price,
                'market_type': 'forex'
            }
        else:
            raise ValueError("Invalid Alpha Vantage response")
    
    def _get_forex_yfinance(self, trading_pair):
        """Get forex from yfinance (FREE - no API key needed)"""
        try:
            time.sleep(0.5)  # Rate limiting
            
            symbol = f"{trading_pair.base_currency}{trading_pair.quote_currency}=X"
            ticker = yf.Ticker(symbol)
            history = ticker.history(period='5d')
            
            if history.empty:
                raise ValueError(f"No forex data for {trading_pair.symbol}")
            
            last_price = history['Close'].iloc[-1]
            open_price = history['Open'].iloc[-1]
            high = history['High'].iloc[-1]
            low = history['Low'].iloc[-1]
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': Decimal(str(last_price)),
                'open': Decimal(str(open_price)),  # ADD THIS
                'close': Decimal(str(last_price)),  # ADD THIS
                'bid': Decimal(str(last_price * 0.99999)),
                'ask': Decimal(str(last_price * 1.00001)),
                'volume': Decimal('0'),
                'change_24h': Decimal('0'),
                'high_24h': Decimal(str(high)),
                'low_24h': Decimal(str(low)),
                'market_type': 'forex'
            }
        except Exception as e:
            raise Exception(f"Forex data unavailable: {str(e)}")
    
    def _get_commodity_ticker(self, trading_pair):
        """Get commodity ticker using yfinance futures (FREE - no API key needed)"""
        try:
            time.sleep(0.5)  # Rate limiting
            
            ticker_map = {
                'GOLD': 'GC=F', 'SILVER': 'SI=F', 'WTI': 'CL=F',
                'BRENT': 'BZ=F', 'NATURALGAS': 'NG=F', 'COPPER': 'HG=F',
                'PLATINUM': 'PL=F', 'PALLADIUM': 'PA=F',
            }
            
            yf_symbol = ticker_map.get(trading_pair.symbol)
            if not yf_symbol:
                yf_symbol = f"{trading_pair.base_currency}=F"
            
            ticker = yf.Ticker(yf_symbol)
            history = ticker.history(period='5d')
            
            if history.empty:
                raise ValueError(f"No commodity data for {trading_pair.symbol}")
            
            last_price = Decimal(str(history['Close'].iloc[-1]))
            open_price = Decimal(str(history['Open'].iloc[-1]))
            high = Decimal(str(history['High'].iloc[-1]))
            low = Decimal(str(history['Low'].iloc[-1]))
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': last_price,
                'open': open_price,  # ADD THIS
                'close': last_price,  # ADD THIS
                'bid': last_price * Decimal('0.9995'),
                'ask': last_price * Decimal('1.0005'),
                'volume': Decimal('0'),
                'change_24h': Decimal('0'),
                'high_24h': high,
                'low_24h': low,
                'market_type': 'commodity'
            }
        except Exception as e:
            raise Exception(f"Commodity data unavailable: {str(e)}")
    
    def _get_bond_ticker(self, trading_pair):
        """Get bond ticker using yfinance (FREE - no API key needed)"""
        try:
            time.sleep(0.5)  # Rate limiting
            
            # Map to yfinance treasury symbols
            ticker_map = {
                'US2Y': '^IRX',   # 13 Week Treasury Bill (proxy for 2Y)
                'US5Y': '^FVX',   # 5 Year Treasury Yield
                'US10Y': '^TNX',  # 10 Year Treasury Yield
                'US30Y': '^TYX',  # 30 Year Treasury Yield
            }
            
            yf_symbol = ticker_map.get(trading_pair.symbol, f"^{trading_pair.base_currency}")
            ticker = yf.Ticker(yf_symbol)
            history = ticker.history(period='5d')
            
            if history.empty:
                raise ValueError(f"No bond data for {trading_pair.symbol}")
            
            last_price = history['Close'].iloc[-1]
            open_price = history['Open'].iloc[-1]
            high = history['High'].iloc[-1]
            low = history['Low'].iloc[-1]
            volume = history['Volume'].iloc[-1] if 'Volume' in history else 0
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': Decimal(str(last_price)),
                'open': Decimal(str(open_price)),
                'close': Decimal(str(last_price)),
                'bid': Decimal(str(last_price)),
                'ask': Decimal(str(last_price)),
                'volume': Decimal(str(volume)),
                'change_24h': Decimal('0'),
                'high_24h': Decimal(str(high)),
                'low_24h': Decimal(str(low)),
                'market_type': 'bond',
                'yield': Decimal(str(last_price))
            }
        except Exception as e:
            raise Exception(f"Bond data unavailable: {str(e)}")
    
    def get_orderbook(self, trading_pair, limit=20):
        """Get order book"""
        if trading_pair.market_type == 'crypto' and self.crypto_service:
            try:
                return self.crypto_service.get_orderbook(trading_pair.symbol, limit)
            except:
                pass
        
        # Fallback: synthetic order book
        ticker = self.get_ticker(trading_pair)
        return {
            'bids': [[float(ticker['bid']), 100]],
            'asks': [[float(ticker['ask']), 100]],
        }
    
    def get_historical_data(self, trading_pair, timeframe='1h', limit=100):
        """Get historical OHLCV data"""
        market_type = trading_pair.market_type
        
        try:
            if market_type == 'crypto' and self.crypto_service:
                return self.crypto_service.get_historical_data(trading_pair.symbol, timeframe, limit)
            else:
                # Use yfinance for all non-crypto assets
                return self._get_yfinance_historical(trading_pair, timeframe, limit)
        except Exception as e:
            logger.error(f"Error fetching historical data for {trading_pair.symbol}: {e}")
            return []
    
    def _get_crypto_historical(self, trading_pair, timeframe, limit):
        """Deprecated - now handled by crypto_service"""
        if self.crypto_service:
            return self.crypto_service.get_historical_data(trading_pair.symbol, timeframe, limit)
        return []
    
    def _get_yfinance_historical(self, trading_pair, timeframe, limit):
        """Get historical data from yfinance (stocks, forex, commodities, bonds)"""
        period_map = {
            '1m': '1d', '5m': '5d', '15m': '5d',
            '1h': '1mo', '1d': '1y', '1w': '5y'
        }
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m',
            '1h': '1h', '1d': '1d', '1w': '1wk'
        }
        
        # Determine the symbol to use
        if trading_pair.market_type == 'forex':
            symbol = f"{trading_pair.base_currency}{trading_pair.quote_currency}=X"
        elif trading_pair.market_type == 'commodity':
            ticker_map = {
                'WTI': 'CL=F', 'BRENT': 'BZ=F', 'NATURALGAS': 'NG=F',
                'COPPER': 'HG=F', 'GOLD': 'GC=F', 'SILVER': 'SI=F',
                'PLATINUM': 'PL=F', 'PALLADIUM': 'PA=F'
            }
            symbol = ticker_map.get(trading_pair.symbol, f"{trading_pair.base_currency}=F")
        elif trading_pair.market_type == 'bond':
            ticker_map = {
                'US2Y': '^IRX', 'US5Y': '^FVX',
                'US10Y': '^TNX', 'US30Y': '^TYX'
            }
            symbol = ticker_map.get(trading_pair.symbol, f"^{trading_pair.base_currency}")
        else:
            symbol = trading_pair.base_currency
        
        ticker = yf.Ticker(symbol)
        history = ticker.history(
            period=period_map.get(timeframe, '1mo'),
            interval=interval_map.get(timeframe, '1d')
        )
        
        result = []
        for index, row in history.tail(limit).iterrows():
            result.append({
                'timestamp': int(index.timestamp() * 1000),
                'open': Decimal(str(row['Open'])),
                'high': Decimal(str(row['High'])),
                'low': Decimal(str(row['Low'])),
                'close': Decimal(str(row['Close'])),
                'volume': Decimal(str(row.get('Volume', 0))),
            })
        
        return result
    
    def check_market_hours(self, trading_pair):
        """Check if market is currently open for trading"""
        market_type = trading_pair.market_type
        
        if market_type == 'crypto':
            return True
        
        if market_type == 'forex':
            now = datetime.now()
            return now.weekday() < 5  # Monday-Friday
        
        if market_type in ['stock', 'bond']:
            category = trading_pair.asset_category
            now = datetime.now().time()
            current_day = datetime.now().weekday() + 1
            
            if current_day not in category.trading_days:
                return False
            
            if category.trading_hours_start and category.trading_hours_end:
                return category.trading_hours_start <= now <= category.trading_hours_end
            
            return True
        
        if market_type == 'commodity':
            now = datetime.now()
            if now.weekday() >= 5:
                return False
            return 9 <= now.hour <= 17
        
        return True