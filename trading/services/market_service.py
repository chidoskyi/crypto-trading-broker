# trading/services/market_service.py
import ccxt
import yfinance as yf
import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta

class MarketDataService:
# class UnifiedMarketDataService:
    """Unified service for fetching market data across all asset classes"""
    
    def __init__(self):
        # Initialize crypto exchange
        self.crypto_exchange = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET_KEY,
            'enableRateLimit': True,
        })
        
        # API keys for other markets
        self.alpha_vantage_key = settings.ALPHA_VANTAGE_API_KEY
        self.polygon_key = settings.POLYGON_API_KEY
        self.commodities_api_key = settings.COMMODITIES_API_KEY
    
    def get_ticker(self, trading_pair):
        """Get current ticker data based on market type"""
        cache_key = f'ticker:{trading_pair.symbol}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        market_type = trading_pair.market_type
        
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
        
        # Cache for appropriate duration based on market type
        cache_timeout = 5 if market_type == 'crypto' else 60
        cache.set(cache_key, data, timeout=cache_timeout)
        
        return data
    
    def _get_crypto_ticker(self, trading_pair):
        """Get cryptocurrency ticker data"""
        try:
            ticker = self.crypto_exchange.fetch_ticker(trading_pair.symbol)
            return {
                'symbol': trading_pair.symbol,
                'last_price': Decimal(str(ticker['last'])),
                'bid': Decimal(str(ticker['bid'])),
                'ask': Decimal(str(ticker['ask'])),
                'volume': Decimal(str(ticker['volume'])),
                'change_24h': Decimal(str(ticker['percentage'])),
                'high_24h': Decimal(str(ticker['high'])),
                'low_24h': Decimal(str(ticker['low'])),
                'market_type': 'crypto'
            }
        except Exception as e:
            raise Exception(f"Error fetching crypto data: {str(e)}")
    
    def _get_stock_ticker(self, trading_pair):
        """Get stock ticker data using yfinance"""
        try:
            stock = yf.Ticker(trading_pair.base_currency)
            info = stock.info
            history = stock.history(period='1d')
            
            if history.empty:
                raise ValueError("No stock data available")
            
            last_price = history['Close'].iloc[-1]
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': Decimal(str(last_price)),
                'bid': Decimal(str(info.get('bid', last_price))),
                'ask': Decimal(str(info.get('ask', last_price))),
                'volume': Decimal(str(history['Volume'].iloc[-1])),
                'change_24h': Decimal(str(info.get('regularMarketChangePercent', 0))),
                'high_24h': Decimal(str(history['High'].iloc[-1])),
                'low_24h': Decimal(str(history['Low'].iloc[-1])),
                'market_cap': Decimal(str(info.get('marketCap', 0))),
                'pe_ratio': info.get('trailingPE'),
                'dividend_yield': info.get('dividendYield'),
                'market_type': 'stock'
            }
        except Exception as e:
            raise Exception(f"Error fetching stock data: {str(e)}")
    
    def _get_forex_ticker(self, trading_pair):
        """Get forex ticker data"""
        try:
            # Using Alpha Vantage for forex
            url = f'https://www.alphavantage.co/query'
            params = {
                'function': 'CURRENCY_EXCHANGE_RATE',
                'from_currency': trading_pair.base_currency,
                'to_currency': trading_pair.quote_currency,
                'apikey': self.alpha_vantage_key
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'Realtime Currency Exchange Rate' in data:
                rate_data = data['Realtime Currency Exchange Rate']
                last_price = Decimal(rate_data['5. Exchange Rate'])
                
                return {
                    'symbol': trading_pair.symbol,
                    'last_price': last_price,
                    'bid': Decimal(rate_data.get('8. Bid Price', last_price)),
                    'ask': Decimal(rate_data.get('9. Ask Price', last_price)),
                    'volume': Decimal('0'),  # Forex doesn't have traditional volume
                    'change_24h': Decimal('0'),  # Calculate from historical data if needed
                    'high_24h': last_price,
                    'low_24h': last_price,
                    'market_type': 'forex'
                }
            else:
                raise ValueError("Invalid forex data response")
                
        except Exception as e:
            raise Exception(f"Error fetching forex data: {str(e)}")
    
    def _get_commodity_ticker(self, trading_pair):
        """Get commodity ticker data (Gold, Silver, Oil, etc.)"""
        try:
            # Using commodities-api.com or similar service
            commodity_map = {
                'GOLD': 'XAU',
                'SILVER': 'XAG',
                'OIL': 'WTI',
                'BRENT': 'BRENT',
                'NATURALGAS': 'NG',
                'COPPER': 'COPPER'
            }
            
            commodity_code = commodity_map.get(trading_pair.base_currency, trading_pair.base_currency)
            
            url = f'https://api.metals.live/v1/spot/{commodity_code}'
            response = requests.get(url)
            data = response.json()
            
            last_price = Decimal(str(data[0]['price']))
            
            return {
                'symbol': trading_pair.symbol,
                'last_price': last_price,
                'bid': last_price,
                'ask': last_price,
                'volume': Decimal('0'),
                'change_24h': Decimal('0'),
                'high_24h': last_price,
                'low_24h': last_price,
                'market_type': 'commodity'
            }
        except Exception as e:
            raise Exception(f"Error fetching commodity data: {str(e)}")
    
    def _get_bond_ticker(self, trading_pair):
        """Get bond ticker data (Treasury Bonds, Corporate Bonds)"""
        try:
            # For US Treasury bonds
            if 'US' in trading_pair.symbol:
                stock = yf.Ticker(f"^{trading_pair.base_currency}")
                history = stock.history(period='1d')
                
                if history.empty:
                    raise ValueError("No bond data available")
                
                last_price = history['Close'].iloc[-1]
                
                return {
                    'symbol': trading_pair.symbol,
                    'last_price': Decimal(str(last_price)),
                    'bid': Decimal(str(last_price)),
                    'ask': Decimal(str(last_price)),
                    'volume': Decimal(str(history['Volume'].iloc[-1])),
                    'change_24h': Decimal('0'),
                    'high_24h': Decimal(str(history['High'].iloc[-1])),
                    'low_24h': Decimal(str(history['Low'].iloc[-1])),
                    'market_type': 'bond',
                    'yield': last_price  # For bonds, price often represents yield
                }
            else:
                raise ValueError("Unsupported bond type")
                
        except Exception as e:
            raise Exception(f"Error fetching bond data: {str(e)}")
    
    def get_orderbook(self, trading_pair, limit=20):
        """Get order book (mainly for crypto and some stocks)"""
        if trading_pair.market_type == 'crypto':
            orderbook = self.crypto_exchange.fetch_order_book(
                trading_pair.symbol, 
                limit=limit
            )
            return {
                'bids': orderbook['bids'],
                'asks': orderbook['asks'],
            }
        else:
            # For stocks/forex/commodities, order book might not be available
            # Return synthetic order book based on current price
            ticker = self.get_ticker(trading_pair)
            return {
                'bids': [[float(ticker['bid']), 100]],
                'asks': [[float(ticker['ask']), 100]],
            }
    
    def get_historical_data(self, trading_pair, timeframe='1h', limit=100):
        """Get historical OHLCV data"""
        market_type = trading_pair.market_type
        
        if market_type == 'crypto':
            return self._get_crypto_historical(trading_pair, timeframe, limit)
        elif market_type in ['stock', 'bond']:
            return self._get_stock_historical(trading_pair, timeframe, limit)
        elif market_type == 'forex':
            return self._get_forex_historical(trading_pair, timeframe, limit)
        elif market_type == 'commodity':
            return self._get_commodity_historical(trading_pair, timeframe, limit)
    
    def _get_crypto_historical(self, trading_pair, timeframe, limit):
        """Get crypto historical data"""
        ohlcv = self.crypto_exchange.fetch_ohlcv(
            trading_pair.symbol, 
            timeframe, 
            limit=limit
        )
        return [{
            'timestamp': candle[0],
            'open': Decimal(str(candle[1])),
            'high': Decimal(str(candle[2])),
            'low': Decimal(str(candle[3])),
            'close': Decimal(str(candle[4])),
            'volume': Decimal(str(candle[5])),
        } for candle in ohlcv]
    
    def _get_stock_historical(self, trading_pair, timeframe, limit):
        """Get stock historical data"""
        # Convert timeframe to yfinance period
        period_map = {
            '1m': '1d',
            '5m': '5d',
            '15m': '5d',
            '1h': '1mo',
            '1d': '1y',
            '1w': '5y'
        }
        
        interval_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '1d': '1d',
            '1w': '1wk'
        }
        
        stock = yf.Ticker(trading_pair.base_currency)
        history = stock.history(
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
                'volume': Decimal(str(row['Volume'])),
            })
        
        return result
    
    def _get_forex_historical(self, trading_pair, timeframe, limit):
        """Get forex historical data"""
        # Implementation using Alpha Vantage or other forex data provider
        # Simplified version
        return []
    
    def _get_commodity_historical(self, trading_pair, timeframe, limit):
        """Get commodity historical data"""
        # Implementation using commodity data provider
        return []
    
    def check_market_hours(self, trading_pair):
        """Check if market is currently open for trading"""
        market_type = trading_pair.market_type
        
        # Crypto markets are 24/7
        if market_type == 'crypto':
            return True
        
        # Forex is open 24/5
        if market_type == 'forex':
            now = datetime.now()
            # Closed on weekends
            if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False
            return True
        
        # Stocks, bonds have specific trading hours
        if market_type in ['stock', 'bond']:
            category = trading_pair.asset_category
            now = datetime.now().time()
            current_day = datetime.now().weekday() + 1  # Monday = 1
            
            # Check if today is a trading day
            if current_day not in category.trading_days:
                return False
            
            # Check trading hours
            if category.trading_hours_start and category.trading_hours_end:
                if category.trading_hours_start <= now <= category.trading_hours_end:
                    return True
                return False
            
            return True  # Default to open if no hours specified
        
        # Commodities have varying hours
        if market_type == 'commodity':
            # Simplified - most commodity markets trade during business hours
            now = datetime.now()
            if now.weekday() >= 5:
                return False
            hour = now.hour
            return 9 <= hour <= 17
        
        return True  # Default to open