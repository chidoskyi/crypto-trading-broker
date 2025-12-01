# trading/services/crypto_service.py
"""
Multi-source crypto price service with fallbacks
Uses: CoinGecko (primary) -> Kraken -> Coinbase -> ccxt exchanges
NO API KEYS REQUIRED for basic functionality!
"""

import ccxt
import requests
import time
from decimal import Decimal
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class CryptoDataService:
    """
    Multi-source crypto data service with intelligent fallbacks
    Priority: CoinGecko -> Kraken -> Coinbase -> Binance (if configured)
    """
    
    def __init__(self):
        # CoinGecko API (NO KEY NEEDED!)
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        
        # Initialize ccxt exchanges (no keys needed for public data)
        self.exchanges = self._init_exchanges()
        
        # Symbol mappings for CoinGecko
        self.coingecko_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'BNB': 'binancecoin',
            'XRP': 'ripple',
            'ADA': 'cardano',
            'SOL': 'solana',
            'DOGE': 'dogecoin',
            'MATIC': 'polygon-ecosystem-token',  # Fixed: was 'matic-network'
            'USDT': 'tether',
            'USDC': 'usd-coin',
            'DOT': 'polkadot',
            'AVAX': 'avalanche-2',
            'LINK': 'chainlink',
            'UNI': 'uniswap',
        }
    
    def _init_exchanges(self):
        """Initialize multiple exchanges as fallbacks"""
        exchanges = {}
        
        # Try Kraken (very reliable, no API key needed)
        try:
            exchanges['kraken'] = ccxt.kraken({'enableRateLimit': True})
            logger.info("✅ Kraken exchange initialized")
        except Exception as e:
            logger.warning(f"⚠️ Kraken initialization failed: {e}")
        
        # Try Coinbase (US-based, no API key needed)
        try:
            exchanges['coinbase'] = ccxt.coinbase({'enableRateLimit': True})
            logger.info("✅ Coinbase exchange initialized")
        except Exception as e:
            logger.warning(f"⚠️ Coinbase initialization failed: {e}")
        
        # Try Binance if API keys are available
        if hasattr(settings, 'BINANCE_API_KEY') and settings.BINANCE_API_KEY:
            try:
                exchanges['binance'] = ccxt.binance({
                    'apiKey': settings.BINANCE_API_KEY,
                    'secret': settings.BINANCE_SECRET_KEY,
                    'enableRateLimit': True,
                })
                logger.info("✅ Binance exchange initialized")
            except Exception as e:
                logger.warning(f"⚠️ Binance initialization failed: {e}")
        
        # Try KuCoin (no API key needed)
        try:
            exchanges['kucoin'] = ccxt.kucoin({'enableRateLimit': True})
            logger.info("✅ KuCoin exchange initialized")
        except Exception as e:
            logger.warning(f"⚠️ KuCoin initialization failed: {e}")
        
        return exchanges
    
    def get_crypto_ticker(self, symbol):
        """
        Get crypto ticker with multiple fallbacks
        symbol: e.g., 'BTC/USD', 'ETH/USDT'
        """
        # Extract base currency (e.g., 'BTC' from 'BTC/USD')
        base_currency = symbol.split('/')[0]
        
        # Try CoinGecko first (NO API KEY, most reliable)
        try:
            return self._get_from_coingecko(base_currency)
        except Exception as e:
            logger.warning(f"CoinGecko failed for {symbol}: {e}")
        
        # Try exchanges in order of preference
        for exchange_name in ['kraken', 'coinbase', 'binance', 'kucoin']:
            if exchange_name in self.exchanges:
                try:
                    return self._get_from_exchange(self.exchanges[exchange_name], symbol)
                except Exception as e:
                    logger.warning(f"{exchange_name} failed for {symbol}: {e}")
                    continue
        
        raise Exception(f"All crypto data sources failed for {symbol}")
    
    def _get_from_coingecko(self, base_currency):
        """Get data from CoinGecko API (NO KEY REQUIRED!)"""
        # Get CoinGecko ID for the currency
        coin_id = self.coingecko_ids.get(base_currency)
        if not coin_id:
            raise ValueError(f"No CoinGecko mapping for {base_currency}")
        
        # Get current price data
        url = f"{self.coingecko_url}/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true',
            'include_last_updated_at': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if coin_id not in data:
            raise ValueError(f"No data returned for {coin_id}")
        
        coin_data = data[coin_id]
        last_price = Decimal(str(coin_data['usd']))
        change_24h = Decimal(str(coin_data.get('usd_24h_change', 0)))
        
        # Calculate open price from current price and 24h change
        # Formula: open = close / (1 + (percentage_change / 100))
        if change_24h != 0:
            open_price = last_price / (1 + (change_24h / 100))
        else:
            open_price = last_price
        
        # Try to get more detailed data including actual OHLC
        try:
            ohlc_url = f"{self.coingecko_url}/coins/{coin_id}/ohlc"
            ohlc_params = {
                'vs_currency': 'usd',
                'days': '1'  # Last 24 hours
            }
            ohlc_response = requests.get(ohlc_url, params=ohlc_params, timeout=10)
            ohlc_data = ohlc_response.json()
            
            if ohlc_data and len(ohlc_data) > 0:
                # Get the first candle (24h ago) for open price
                first_candle = ohlc_data[0]
                open_price = Decimal(str(first_candle[1]))  # Open is index 1
                
                # Get high and low from OHLC data
                high_24h = max([Decimal(str(candle[2])) for candle in ohlc_data])
                low_24h = min([Decimal(str(candle[3])) for candle in ohlc_data])
            else:
                # Fallback to approximation
                high_24h = last_price * Decimal('1.02')
                low_24h = last_price * Decimal('0.98')
        except:
            # If OHLC fails, use calculated open and approximated high/low
            high_24h = last_price * Decimal('1.02')
            low_24h = last_price * Decimal('0.98')
        
        return {
            'symbol': f"{base_currency}/USD",
            'last_price': last_price,
            'open': open_price,  # ADD THIS
            'close': last_price,  # ADD THIS
            'bid': last_price * Decimal('0.9999'),
            'ask': last_price * Decimal('1.0001'),
            'volume': Decimal(str(coin_data.get('usd_24h_vol', 0))),
            'change_24h': change_24h,
            'high_24h': high_24h,
            'low_24h': low_24h,
            'market_cap': Decimal(str(coin_data.get('usd_market_cap', 0))),
            'market_type': 'crypto',
            'source': 'coingecko'
        }

    def _get_from_exchange(self, exchange, symbol):
        """Get data from ccxt exchange"""
        # List of symbol variations to try
        symbol_variations = [
            symbol,  # Original (e.g., MATIC/USD)
        ]
        
        # Add USDT variation if symbol ends with /USD
        if '/USD' in symbol:
            symbol_variations.append(symbol.replace('/USD', '/USDT'))
        
        # Add MATIC/POL variation (Polygon's new ticker)
        if 'MATIC' in symbol:
            symbol_variations.append(symbol.replace('MATIC', 'POL'))
        
        # Try each variation
        for test_symbol in symbol_variations:
            try:
                ticker = exchange.fetch_ticker(test_symbol)
                
                # Get OHLCV data for accurate open price
                open_price = Decimal(str(ticker.get('open', ticker.get('last', 0))))
                
                # If open is not available in ticker, try to get it from OHLCV
                if not ticker.get('open') or ticker.get('open') == 0:
                    try:
                        ohlcv = exchange.fetch_ohlcv(test_symbol, '1d', limit=1)
                        if ohlcv and len(ohlcv) > 0:
                            open_price = Decimal(str(ohlcv[0][1]))  # Open is index 1
                    except:
                        # Calculate from percentage if available
                        last_price = Decimal(str(ticker.get('last', 0)))
                        percentage = Decimal(str(ticker.get('percentage', 0)))
                        if percentage != 0:
                            open_price = last_price / (1 + (percentage / 100))
                        else:
                            open_price = last_price
                
                return {
                    'symbol': symbol,  # Return original symbol
                    'last_price': Decimal(str(ticker.get('last', 0))),
                    'open': open_price,  # ADD THIS
                    'close': Decimal(str(ticker.get('close', ticker.get('last', 0)))),  # ADD THIS
                    'bid': Decimal(str(ticker.get('bid', ticker.get('last', 0)))),
                    'ask': Decimal(str(ticker.get('ask', ticker.get('last', 0)))),
                    'volume': Decimal(str(ticker.get('volume', 0))),
                    'change_24h': Decimal(str(ticker.get('percentage', 0))),
                    'high_24h': Decimal(str(ticker.get('high', 0))),
                    'low_24h': Decimal(str(ticker.get('low', 0))),
                    'market_type': 'crypto',
                    'source': exchange.id
                }
            except Exception as e:
                continue
        
        raise Exception(f"All symbol variations failed for {symbol}")
        
        
        def get_historical_data(self, symbol, timeframe='1h', limit=100):
            """Get historical data with fallbacks"""
            # Try each exchange until one works
            for exchange_name, exchange in self.exchanges.items():
                try:
                    # Adjust symbol format if needed
                    test_symbol = symbol
                    if '/USD' in symbol and exchange_name in ['binance', 'kucoin']:
                        test_symbol = symbol.replace('/USD', '/USDT')
                    
                    ohlcv = exchange.fetch_ohlcv(test_symbol, timeframe, limit=limit)
                    
                    return [{
                        'timestamp': candle[0],
                        'open': Decimal(str(candle[1])),
                        'high': Decimal(str(candle[2])),
                        'low': Decimal(str(candle[3])),
                        'close': Decimal(str(candle[4])),
                        'volume': Decimal(str(candle[5])),
                    } for candle in ohlcv]
                except Exception as e:
                    logger.warning(f"{exchange_name} historical data failed: {e}")
                    continue
            
            return []
        
        def get_orderbook(self, symbol, limit=20):
            """Get orderbook with fallbacks"""
            for exchange_name, exchange in self.exchanges.items():
                try:
                    test_symbol = symbol
                    if '/USD' in symbol and exchange_name in ['binance', 'kucoin']:
                        test_symbol = symbol.replace('/USD', '/USDT')
                    
                    orderbook = exchange.fetch_order_book(test_symbol, limit=limit)
                    return {
                        'bids': orderbook['bids'],
                        'asks': orderbook['asks'],
                    }
                except Exception as e:
                    logger.warning(f"{exchange_name} orderbook failed: {e}")
                    continue
            
            return {'bids': [], 'asks': []}
        
        def get_supported_coins(self):
            """Get list of supported cryptocurrencies"""
            return list(self.coingecko_ids.keys())
        
        def add_coin_mapping(self, symbol, coingecko_id):
            """Add a new coin mapping for CoinGecko"""
            self.coingecko_ids[symbol] = coingecko_id


# Example usage in your market_service.py
    def _get_crypto_ticker(self, trading_pair):
        """Get cryptocurrency ticker using multi-source service"""
        if not hasattr(self, 'crypto_service'):
            from trading.services.crypto_service import CryptoDataService
            self.crypto_service = CryptoDataService()
        
        try:
            return self.crypto_service.get_crypto_ticker(trading_pair.symbol)
        except Exception as e:
            raise Exception(f"Crypto data unavailable for {trading_pair.symbol}: {str(e)}")