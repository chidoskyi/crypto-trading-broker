# funds/management/commands/init_deposit_methods.py
from django.core.management.base import BaseCommand
from funds.models import DepositMethod
from decimal import Decimal

class Command(BaseCommand):
    help = 'Initialize deposit methods'

    def handle(self, *args, **kwargs):
        methods = [
            # Bitcoin
            {
                'currency': 'BTC',
                'network': 'BTC',
                'name': 'Bitcoin',
                'min_deposit': Decimal('0.0001'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 3,
                'block_time_seconds': 600,  # 10 minutes
            },
            
            # Ethereum
            {
                'currency': 'ETH',
                'network': 'ETH',
                'name': 'Ethereum',
                'min_deposit': Decimal('0.01'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 12,
                'block_time_seconds': 15,
            },
            
            # USDT - Ethereum (ERC-20)
            {
                'currency': 'USDT',
                'network': 'ETH',
                'name': 'USDT (ERC-20)',
                'min_deposit': Decimal('10'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 12,
                'block_time_seconds': 15,
                'contract_address': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            },
            
            # USDT - BSC (BEP-20)
            {
                'currency': 'USDT',
                'network': 'BSC',
                'name': 'USDT (BEP-20)',
                'min_deposit': Decimal('10'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 15,
                'block_time_seconds': 3,
                'contract_address': '0x55d398326f99059fF775485246999027B3197955',
            },
            
            # USDT - Tron (TRC-20)
            {
                'currency': 'USDT',
                'network': 'TRC20',
                'name': 'USDT (TRC-20)',
                'min_deposit': Decimal('10'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 19,
                'block_time_seconds': 3,
                'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
            },
            
            # USDC - Ethereum (ERC-20)
            {
                'currency': 'USDC',
                'network': 'ETH',
                'name': 'USDC (ERC-20)',
                'min_deposit': Decimal('10'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 12,
                'block_time_seconds': 15,
                'contract_address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            },
            
            # USDC - BSC (BEP-20)
            {
                'currency': 'USDC',
                'network': 'BSC',
                'name': 'USDC (BEP-20)',
                'min_deposit': Decimal('10'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 15,
                'block_time_seconds': 3,
                'contract_address': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',
            },
            
            # BNB - BSC
            {
                'currency': 'BNB',
                'network': 'BSC',
                'name': 'BNB (Binance Coin)',
                'min_deposit': Decimal('0.01'),
                'deposit_fee_percentage': Decimal('0'),
                'required_confirmations': 15,
                'block_time_seconds': 3,
            },
        ]
        
        for method_data in methods:
            method, created = DepositMethod.objects.update_or_create(
                currency=method_data['currency'],
                network=method_data['network'],
                defaults=method_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created: {method.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Updated: {method.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Deposit methods initialized!')
        )