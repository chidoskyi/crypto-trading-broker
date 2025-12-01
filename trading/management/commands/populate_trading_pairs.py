# trading/management/commands/populate_trading_pairs.py
from django.core.management.base import BaseCommand
from trading.models import TradingPair, AssetCategory
from decimal import Decimal

class Command(BaseCommand):
    help = 'Populate database with trading pairs across all asset classes'

    def handle(self, *args, **kwargs):
        # Create Asset Categories
        crypto_cat, _ = AssetCategory.objects.get_or_create(
            code='CRYPTO',
            defaults={
                'name': 'Cryptocurrency',
                'description': '24/7 cryptocurrency trading',
                'trading_days': [1, 2, 3, 4, 5, 6, 7]
            }
        )
        
        stock_cat, _ = AssetCategory.objects.get_or_create(
            code='STOCK',
            defaults={
                'name': 'Stocks',
                'description': 'Stock market trading',
                'trading_days': [1, 2, 3, 4, 5],
                'trading_hours_start': '09:30:00',
                'trading_hours_end': '16:00:00'
            }
        )
        
        forex_cat, _ = AssetCategory.objects.get_or_create(
            code='FOREX',
            defaults={
                'name': 'Forex',
                'description': 'Foreign exchange trading',
                'trading_days': [1, 2, 3, 4, 5]
            }
        )
        
        commodity_cat, _ = AssetCategory.objects.get_or_create(
            code='COMMODITY',
            defaults={
                'name': 'Commodities',
                'description': 'Commodity trading',
                'trading_days': [1, 2, 3, 4, 5]
            }
        )
        
        bond_cat, _ = AssetCategory.objects.get_or_create(
            code='BOND',
            defaults={
                'name': 'Bonds',
                'description': 'Bond trading',
                'trading_days': [1, 2, 3, 4, 5]
            }
        )
        
        # Cryptocurrencies with logos
        cryptos = [
            {'symbol': 'BTC/USD', 'name': 'Bitcoin', 'base': 'BTC', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png'},
            {'symbol': 'ETH/USD', 'name': 'Ethereum', 'base': 'ETH', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'},
            {'symbol': 'USDT/USD', 'name': 'Tether', 'base': 'USDT', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/tether-usdt-logo.png'},
            {'symbol': 'BNB/USD', 'name': 'BNB', 'base': 'BNB', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/bnb-bnb-logo.png'},
            {'symbol': 'XRP/USD', 'name': 'XRP', 'base': 'XRP', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/xrp-xrp-logo.png'},
            {'symbol': 'SOL/USD', 'name': 'Solana', 'base': 'SOL', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/solana-sol-logo.png'},
            {'symbol': 'ADA/USD', 'name': 'Cardano', 'base': 'ADA', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/cardano-ada-logo.png'},
            {'symbol': 'DOGE/USD', 'name': 'Dogecoin', 'base': 'DOGE', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/dogecoin-doge-logo.png'},
            {'symbol': 'TRX/USD', 'name': 'TRON', 'base': 'TRX', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/tron-trx-logo.png'},
            {'symbol': 'MATIC/USD', 'name': 'Polygon', 'base': 'MATIC', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/polygon-matic-logo.png'},
            {'symbol': 'AVAX/USD', 'name': 'Avalanche', 'base': 'AVAX', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/avalanche-avax-logo.png'},
            {'symbol': 'DOT/USD', 'name': 'Polkadot', 'base': 'DOT', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/polkadot-new-dot-logo.png'},
            {'symbol': 'LTC/USD', 'name': 'Litecoin', 'base': 'LTC', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/litecoin-ltc-logo.png'},
            {'symbol': 'LINK/USD', 'name': 'Chainlink', 'base': 'LINK', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/chainlink-link-logo.png'},
            {'symbol': 'BCH/USD', 'name': 'Bitcoin Cash', 'base': 'BCH', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/bitcoin-cash-bch-logo.png'},
            {'symbol': 'XLM/USD', 'name': 'Stellar', 'base': 'XLM', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/stellar-xlm-logo.png'},
            {'symbol': 'UNI/USD', 'name': 'Uniswap', 'base': 'UNI', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/uniswap-uni-logo.png'},
            {'symbol': 'AAVE/USD', 'name': 'Aave', 'base': 'AAVE', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/aave-aave-logo.png'},
            {'symbol': 'SUI/USD', 'name': 'Sui', 'base': 'SUI', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/sui-sui-logo.png'},
            {'symbol': 'PEPE/USD', 'name': 'Pepe', 'base': 'PEPE', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/pepe-pepe-logo.png'},
            {'symbol': 'HYPE/USD', 'name': 'Hyperliquid', 'base': 'HYPE', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/hyperliquid-hype-logo.png'},
            {'symbol': 'HBAR/USD', 'name': 'Hedera', 'base': 'HBAR', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/hedera-hbar-logo.png'},
            {'symbol': 'APT/USD', 'name': 'Aptos', 'base': 'APT', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/aptos-apt-logo.png'},
            {'symbol': 'CBBTC/USD', 'name': 'Coinbase Wrapped BTC', 'base': 'CBBTC', 'exchange': 'Coinbase', 'logo': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png'},
            {'symbol': 'USDE/USD', 'name': 'Ethena USDe', 'base': 'USDE', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/ethena-usde-logo.png'},
            {'symbol': 'TON/USD', 'name': 'Toncoin', 'base': 'TON', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/toncoin-ton-logo.png'},
            {'symbol': 'NEAR/USD', 'name': 'NEAR Protocol', 'base': 'NEAR', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/near-protocol-near-logo.png'},
            {'symbol': 'SHIB/USD', 'name': 'Shiba Inu', 'base': 'SHIB', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/shiba-inu-shib-logo.png'},
            {'symbol': 'TAO/USD', 'name': 'Bittensor', 'base': 'TAO', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/bittensor-tao-logo.png'},
            {'symbol': 'WBTC/USD', 'name': 'Wrapped Bitcoin', 'base': 'WBTC', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/wrapped-bitcoin-wbtc-logo.png'},
            {'symbol': 'XMR/USD', 'name': 'Monero', 'base': 'XMR', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/monero-xmr-logo.png'},
            {'symbol': 'BGB/USD', 'name': 'Bitget Token', 'base': 'BGB', 'exchange': 'Bitget', 'logo': 'https://cryptologos.cc/logos/bitget-token-bgb-logo.png'},
            {'symbol': 'ETC/USD', 'name': 'Ethereum Classic', 'base': 'ETC', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/ethereum-classic-etc-logo.png'},
            {'symbol': 'WSTETH/USD', 'name': 'Wrapped stETH', 'base': 'WSTETH', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/lido-staked-ether-steth-logo.png'},
            {'symbol': 'CRO/USD', 'name': 'Cronos', 'base': 'CRO', 'exchange': 'Crypto.com', 'logo': 'https://cryptologos.cc/logos/cronos-cro-logo.png'},
            {'symbol': 'STETH/USD', 'name': 'Lido Staked Ether', 'base': 'STETH', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/lido-staked-ether-steth-logo.png'},
            {'symbol': 'ICP/USD', 'name': 'Internet Computer', 'base': 'ICP', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/internet-computer-icp-logo.png'},
            {'symbol': 'WETH/USD', 'name': 'WETH', 'base': 'WETH', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'},
            {'symbol': 'PI/USD', 'name': 'Pi Network', 'base': 'PI', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/pi-network-pi-logo.png'},
            {'symbol': 'WBT/USD', 'name': 'WhiteBIT Coin', 'base': 'WBT', 'exchange': 'WhiteBIT', 'logo': 'https://cryptologos.cc/logos/whitebit-coin-wbt-logo.png'},
            {'symbol': 'OKB/USD', 'name': 'OKB', 'base': 'OKB', 'exchange': 'OKX', 'logo': 'https://cryptologos.cc/logos/okb-okb-logo.png'},
            {'symbol': 'SUSDE/USD', 'name': 'Ethena Staked USDe', 'base': 'SUSDE', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/ethena-usde-logo.png'},
            {'symbol': 'TKX/USD', 'name': 'Token X', 'base': 'TKX', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/generic-crypto-logo.png'},
            {'symbol': 'JITOSOL/USD', 'name': 'Jito Staked SOL', 'base': 'JITOSOL', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/solana-sol-logo.png'},
            {'symbol': 'WEETH/USD', 'name': 'Wrapped eETH', 'base': 'WEETH', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'},
            {'symbol': 'LEO/USD', 'name': 'LEO Token', 'base': 'LEO', 'exchange': 'Bitfinex', 'logo': 'https://cryptologos.cc/logos/leo-token-leo-logo.png'},
            {'symbol': 'BUIDL/USD', 'name': 'BUIDL', 'base': 'BUIDL', 'exchange': 'Binance', 'logo': 'https://cryptologos.cc/logos/generic-crypto-logo.png'},
        ]
        
        for crypto in cryptos:
            TradingPair.objects.update_or_create(
                symbol=crypto['symbol'],
                defaults={
                    'name': crypto['name'],
                    'base_currency': crypto['base'],
                    'quote_currency': 'USD',
                    'asset_category': crypto_cat,
                    'market_type': 'crypto',
                    'exchange': crypto['exchange'],
                    'logo_url': crypto['logo'],
                    'min_order_size': Decimal('0.0001'),
                    'max_order_size': Decimal('1000'),
                    'price_precision': 2,
                    'quantity_precision': 8,
                    'trading_fee_percentage': Decimal('0.1'),
                    'allow_short_selling': True,
                    'margin_requirement': Decimal('50')
                }
            )
            
        
        # US Stocks with logos
        stocks = [
            {'symbol': 'AAPL', 'name': 'Apple Inc', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/apple.com'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corp', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/microsoft.com'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/google.com'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc', 'exchange': 'NASDAQ', 'sector': 'Consumer Cyclical', 'logo': 'https://logo.clearbit.com/amazon.com'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corp', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/nvidia.com'},
            {'symbol': 'META', 'name': 'Meta Platforms Inc', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/meta.com'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc', 'exchange': 'NASDAQ', 'sector': 'Automotive', 'logo': 'https://logo.clearbit.com/tesla.com'},
            {'symbol': 'BRK.B', 'name': 'Berkshire Hathaway Inc', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/berkshirehathaway.com'},
            {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/jpmorganchase.com'},
            {'symbol': 'WMT', 'name': 'Walmart Inc', 'exchange': 'NYSE', 'sector': 'Retail', 'logo': 'https://logo.clearbit.com/walmart.com'},
            {'symbol': 'LLY', 'name': 'Eli Lilly and Co', 'exchange': 'NYSE', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/lilly.com'},
            {'symbol': 'V', 'name': 'Visa Inc', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/visa.com'},
            {'symbol': 'ORCL', 'name': 'Oracle Corp', 'exchange': 'NYSE', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/oracle.com'},
            {'symbol': 'MA', 'name': 'Mastercard Inc', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/mastercard.com'},
            {'symbol': 'NFLX', 'name': 'Netflix Inc', 'exchange': 'NASDAQ', 'sector': 'Entertainment', 'logo': 'https://logo.clearbit.com/netflix.com'},
            {'symbol': 'XOM', 'name': 'Exxon Mobil Corp', 'exchange': 'NYSE', 'sector': 'Energy', 'logo': 'https://logo.clearbit.com/exxonmobil.com'},
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'exchange': 'NYSE', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/jnj.com'},
            {'symbol': 'HD', 'name': 'Home Depot Inc', 'exchange': 'NYSE', 'sector': 'Retail', 'logo': 'https://logo.clearbit.com/homedepot.com'},
            {'symbol': 'PG', 'name': 'Procter & Gamble Co', 'exchange': 'NYSE', 'sector': 'Consumer Defensive', 'logo': 'https://logo.clearbit.com/pg.com'},
            {'symbol': 'BAC', 'name': 'Bank of America Corp', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/bankofamerica.com'},
            {'symbol': 'CVX', 'name': 'Chevron Corp', 'exchange': 'NYSE', 'sector': 'Energy', 'logo': 'https://logo.clearbit.com/chevron.com'},
            {'symbol': 'KO', 'name': 'Coca-Cola Co', 'exchange': 'NYSE', 'sector': 'Consumer Defensive', 'logo': 'https://logo.clearbit.com/coca-cola.com'},
            {'symbol': 'WFC', 'name': 'Wells Fargo & Co', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/wellsfargo.com'},
            {'symbol': 'CSCO', 'name': 'Cisco Systems Inc', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/cisco.com'},
            {'symbol': 'CRM', 'name': 'Salesforce Inc', 'exchange': 'NYSE', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/salesforce.com'},
            {'symbol': 'UNH', 'name': 'UnitedHealth Group Inc', 'exchange': 'NYSE', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/unitedhealthgroup.com'},
            {'symbol': 'DIS', 'name': 'Walt Disney Co', 'exchange': 'NYSE', 'sector': 'Entertainment', 'logo': 'https://logo.clearbit.com/disney.com'},
            {'symbol': 'MRK', 'name': 'Merck & Co Inc', 'exchange': 'NYSE', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/merck.com'},
            {'symbol': 'T', 'name': 'AT&T Inc', 'exchange': 'NYSE', 'sector': 'Communication', 'logo': 'https://logo.clearbit.com/att.com'},
            {'symbol': 'PEP', 'name': 'PepsiCo Inc', 'exchange': 'NASDAQ', 'sector': 'Consumer Defensive', 'logo': 'https://logo.clearbit.com/pepsico.com'},
            {'symbol': 'VZ', 'name': 'Verizon Communications Inc', 'exchange': 'NYSE', 'sector': 'Communication', 'logo': 'https://logo.clearbit.com/verizon.com'},
            {'symbol': 'TMO', 'name': 'Thermo Fisher Scientific Inc', 'exchange': 'NYSE', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/thermofisher.com'},
            {'symbol': 'C', 'name': 'Citigroup Inc', 'exchange': 'NYSE', 'sector': 'Financial', 'logo': 'https://logo.clearbit.com/citigroup.com'},
            {'symbol': 'BA', 'name': 'Boeing Co', 'exchange': 'NYSE', 'sector': 'Industrial', 'logo': 'https://logo.clearbit.com/boeing.com'},
            {'symbol': 'AMGN', 'name': 'Amgen Inc', 'exchange': 'NASDAQ', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/amgen.com'},
            {'symbol': 'ADBE', 'name': 'Adobe Inc', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/adobe.com'},
            {'symbol': 'PFE', 'name': 'Pfizer Inc', 'exchange': 'NYSE', 'sector': 'Healthcare', 'logo': 'https://logo.clearbit.com/pfizer.com'},
            {'symbol': 'NKE', 'name': 'Nike Inc', 'exchange': 'NYSE', 'sector': 'Consumer Cyclical', 'logo': 'https://logo.clearbit.com/nike.com'},
            {'symbol': 'INTC', 'name': 'Intel Corp', 'exchange': 'NASDAQ', 'sector': 'Technology', 'logo': 'https://logo.clearbit.com/intel.com'},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'base': 'META', 'exchange': 'NASDAQ','sector': 'Communication', 'logo': 'https://logo.clearbit.com/meta.com'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'base': 'MSFT', 'exchange': 'NASDAQ','sector': 'Technology', 'logo': 'https://logo.clearbit.com/microsoft.com'},    
        ]
        
        for stock in stocks:
            TradingPair.objects.update_or_create(
                symbol=stock['symbol'],
                defaults={
                    'name': stock['name'],
                    'base_currency': stock['symbol'],
                    'quote_currency': 'USD',
                    'asset_category': stock_cat,
                    'market_type': 'stock',
                    'exchange': stock['exchange'],
                    'logo_url': stock['logo'],
                    'country_code': 'US',
                    'sector': stock['sector'],
                    'min_order_size': Decimal('0.01'),
                    'max_order_size': Decimal('10000'),
                    'price_precision': 2,
                    'quantity_precision': 2,
                    'trading_fee_percentage': Decimal('0.1'),
                    'allow_short_selling': True,
                    'allow_fractional_shares': True,
                    'margin_requirement': Decimal('50')
                }
            )
        
        # Forex Pairs with generic currency logos
        forex = [
            {'symbol': 'EUR/USD', 'name': 'Euro vs US Dollar', 'base': 'EUR', 'quote': 'USD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'USD/JPY', 'name': 'US Dollar vs Japanese Yen', 'base': 'USD', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
            {'symbol': 'GBP/USD', 'name': 'British Pound vs US Dollar', 'base': 'GBP', 'quote': 'USD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/gbp.png'},
            {'symbol': 'AUD/USD', 'name': 'Australian Dollar vs US Dollar', 'base': 'AUD', 'quote': 'USD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/aud.png'},
            {'symbol': 'NZD/USD', 'name': 'New Zealand Dollar vs US Dollar', 'base': 'NZD', 'quote': 'USD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/nzd.png'},
            {'symbol': 'USD/CAD', 'name': 'US Dollar vs Canadian Dollar', 'base': 'USD', 'quote': 'CAD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
            {'symbol': 'USD/CHF', 'name': 'US Dollar vs Swiss Franc', 'base': 'USD', 'quote': 'CHF', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
            {'symbol': 'EUR/GBP', 'name': 'Euro vs British Pound', 'base': 'EUR', 'quote': 'GBP', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'EUR/JPY', 'name': 'Euro vs Japanese Yen', 'base': 'EUR', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'GBP/JPY', 'name': 'British Pound vs Japanese Yen', 'base': 'GBP', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/gbp.png'},
            {'symbol': 'CHF/JPY', 'name': 'Swiss Franc vs Japanese Yen', 'base': 'CHF', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/chf.png'},
            {'symbol': 'EUR/CHF', 'name': 'Euro vs Swiss Franc', 'base': 'EUR', 'quote': 'CHF', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'EUR/AUD', 'name': 'Euro vs Australian Dollar', 'base': 'EUR', 'quote': 'AUD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'AUD/JPY', 'name': 'Australian Dollar vs Japanese Yen', 'base': 'AUD', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/aud.png'},
            {'symbol': 'CAD/JPY', 'name': 'Canadian Dollar vs Japanese Yen', 'base': 'CAD', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/cad.png'},
            {'symbol': 'AUD/CAD', 'name': 'Australian Dollar vs Canadian Dollar', 'base': 'AUD', 'quote': 'CAD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/aud.png'},
            {'symbol': 'AUD/NZD', 'name': 'Australian Dollar vs New Zealand Dollar', 'base': 'AUD', 'quote': 'NZD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/aud.png'},
            {'symbol': 'GBP/AUD', 'name': 'British Pound vs Australian Dollar', 'base': 'GBP', 'quote': 'AUD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/gbp.png'},
            {'symbol': 'GBP/CHF', 'name': 'British Pound vs Swiss Franc', 'base': 'GBP', 'quote': 'CHF', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/gbp.png'},
            {'symbol': 'EUR/NZD', 'name': 'Euro vs New Zealand Dollar', 'base': 'EUR', 'quote': 'NZD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'EUR/CAD', 'name': 'Euro vs Canadian Dollar', 'base': 'EUR', 'quote': 'CAD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/eur.png'},
            {'symbol': 'NZD/JPY', 'name': 'New Zealand Dollar vs Japanese Yen', 'base': 'NZD', 'quote': 'JPY', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/nzd.png'},
            {'symbol': 'USD/MXN', 'name': 'US Dollar vs Mexican Peso', 'base': 'USD', 'quote': 'MXN', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
            {'symbol': 'USD/ZAR', 'name': 'US Dollar vs South African Rand', 'base': 'USD', 'quote': 'ZAR', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
            {'symbol': 'USD/HKD', 'name': 'US Dollar vs Hong Kong Dollar', 'base': 'USD', 'quote': 'HKD', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
            {'symbol': 'USD/INR', 'name': 'US Dollar vs Indian Rupee', 'base': 'USD', 'quote': 'INR', 'logo': 'https://cdn.jsdelivr.net/gh/transferwise/currency-flags@master/src/flags/usd.png'},
        ]
        
        for fx in forex:
            TradingPair.objects.update_or_create(
                symbol=fx['symbol'],
                defaults={
                    'name': fx['name'],
                    'base_currency': fx['base'],
                    'quote_currency': fx['quote'],
                    'asset_category': forex_cat,
                    'market_type': 'forex',
                    'logo_url': fx['logo'],
                    'min_order_size': Decimal('1000'),
                    'max_order_size': Decimal('10000000'),
                    'price_precision': 5,
                    'quantity_precision': 2,
                    'trading_fee_percentage': Decimal('0.05'),
                    'allow_short_selling': True,
                    'margin_requirement': Decimal('3.33'),
                    'contract_size': Decimal('100000')
                }
            )
        
        # Commodities with generic logos
        commodities = [
            {'symbol': 'GOLD', 'name': 'Gold', 'base': 'XAU', 'contract': '100', 'logo': 'https://cdn-icons-png.flaticon.com/512/2580/2580754.png'},
            {'symbol': 'SILVER', 'name': 'Silver', 'base': 'XAG', 'contract': '5000', 'logo': 'https://cdn-icons-png.flaticon.com/512/2580/2580794.png'},
            {'symbol': 'WTI', 'name': 'Crude Oil (WTI)', 'base': 'CL', 'contract': '1000', 'logo': 'https://cdn-icons-png.flaticon.com/512/1581/1581530.png'},
            {'symbol': 'BRENT', 'name': 'Brent Crude Oil', 'base': 'BZ', 'contract': '1000', 'logo': 'https://cdn-icons-png.flaticon.com/512/1581/1581530.png'},
            {'symbol': 'NATURALGAS', 'name': 'Natural Gas', 'base': 'NG', 'contract': '10000', 'logo': 'https://cdn-icons-png.flaticon.com/512/1581/1581530.png'},
            {'symbol': 'COPPER', 'name': 'Copper', 'base': 'HG', 'contract': '25000', 'logo': 'https://cdn-icons-png.flaticon.com/512/2580/2580776.png'},
            {'symbol': 'PLATINUM', 'name': 'Platinum', 'base': 'PL', 'contract': '50', 'logo': 'https://cdn-icons-png.flaticon.com/512/2580/2580788.png'},
            {'symbol': 'PALLADIUM', 'name': 'Palladium', 'base': 'PA', 'contract': '100', 'logo': 'https://cdn-icons-png.flaticon.com/512/2580/2580783.png'},
            {'symbol': 'CORN', 'name': 'Corn', 'base': 'ZC', 'contract': '5000', 'logo': 'https://cdn-icons-png.flaticon.com/512/6978/6978256.png'},
            {'symbol': 'WHEAT', 'name': 'Wheat', 'base': 'ZW', 'contract': '5000', 'logo': 'https://cdn-icons-png.flaticon.com/512/6978/6978256.png'},
            {'symbol': 'SOYBEANS', 'name': 'Soybeans', 'base': 'ZS', 'contract': '5000', 'logo': 'https://cdn-icons-png.flaticon.com/512/6978/6978256.png'},
            {'symbol': 'SUGAR', 'name': 'Sugar', 'base': 'SB', 'contract': '112000', 'logo': 'https://cdn-icons-png.flaticon.com/512/6978/6978256.png'},
            {'symbol': 'COFFEE', 'name': 'Coffee', 'base': 'KC', 'contract': '37500', 'logo': 'https://cdn-icons-png.flaticon.com/512/6978/6978256.png'},
            {'symbol': 'COTTON', 'name': 'Cotton', 'base': 'CT', 'contract': '50000', 'logo': 'https://cdn-icons-png.flaticon.com/512/6978/6978256.png'},
        ]
        
        for commodity in commodities:
            TradingPair.objects.update_or_create(
                symbol=commodity['symbol'],
                defaults={
                    'name': commodity['name'],
                    'base_currency': commodity['base'],
                    'quote_currency': 'USD',
                    'asset_category': commodity_cat,
                    'market_type': 'commodity',
                    'logo_url': commodity['logo'],
                    'min_order_size': Decimal('0.1'),
                    'max_order_size': Decimal('1000'),
                    'price_precision': 2,
                    'quantity_precision': 2,
                    'trading_fee_percentage': Decimal('0.1'),
                    'allow_short_selling': True,
                    'margin_requirement': Decimal('10'),
                    'contract_size': Decimal(commodity['contract'])
                }
            )
        
        # Bonds with generic bond logos
        bonds = [
            # Existing US Bonds (Updated to match bondMap keys: US02Y, US05Y)
            {'symbol': 'US02Y', 'name': '2-Year US Treasury Note', 'base': 'TNX', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},
            {'symbol': 'US05Y', 'name': '5-Year US Treasury Note', 'base': 'FVX', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},
            {'symbol': 'US10Y', 'name': '10-Year US Treasury Note', 'base': 'TNX', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},
            {'symbol': 'US30Y', 'name': '30-Year US Treasury Bond', 'base': 'TYX', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},

            # Missing International Bonds Added
            {'symbol': 'GERMANY10Y', 'name': '10-Year German Bond', 'base': 'DE10YDE', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},
            {'symbol': 'UK10Y', 'name': '10-Year UK Gilt', 'base': 'UK10Y', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},
            {'symbol': 'JAPAN10Y', 'name': '10-Year Japanese Government Bond', 'base': 'JP10YJ', 'exchange': 'TVC', 'logo': 'https://cdn-icons-png.flaticon.com/512/3135/3135691.png'},
        ]
        
        for bond in bonds:
            TradingPair.objects.update_or_create(
                symbol=bond['symbol'],
                defaults={
                    'name': bond['name'],
                    'base_currency': bond['base'],
                    'quote_currency': 'USD',
                    'asset_category': bond_cat,
                    'market_type': 'bond',
                    'logo_url': bond['logo'],
                    'country_code': 'US',
                    'min_order_size': Decimal('1000'),
                    'max_order_size': Decimal('1000000'),
                    'price_precision': 3,
                    'quantity_precision': 2,
                    'trading_fee_percentage': Decimal('0.05'),
                    'allow_short_selling': False,
                    'margin_requirement': Decimal('100')
                }
            )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully populated trading pairs with logos for all asset classes!')
        )