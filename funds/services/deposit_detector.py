# funds/services/deposit_detector.py
from web3 import Web3
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from funds.models import CryptoWalletAddress, PendingDeposit, Wallet, Transaction
from django.conf import settings
from notifications.services import NotificationService
import requests

class DepositDetector:
    """Monitor blockchains for incoming deposits"""
    
    def __init__(self):
        # Initialize Web3 connections
        self.w3_eth = Web3(Web3.HTTPProvider(settings.ETHEREUM_NODE_URL))
        self.w3_bsc = Web3(Web3.HTTPProvider(settings.BSC_NODE_URL))
        
        # Token contract addresses
        self.USDT_ETH = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
        self.USDC_ETH = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
        self.USDT_BSC = '0x55d398326f99059fF775485246999027B3197955'
        self.USDC_BSC = '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
        
        # ERC-20 Transfer event signature
        self.TRANSFER_EVENT_SIGNATURE = self.w3_eth.keccak(
            text="Transfer(address,address,uint256)"
        ).hex()
    
    def check_all_deposits(self):
        """Main function to check all deposit addresses"""
        print("Checking for new deposits...")
        
        # Get all active addresses
        addresses = CryptoWalletAddress.objects.filter(is_active=True)
        
        for addr in addresses:
            try:
                if addr.network == 'BTC':
                    self._check_btc_deposits(addr)
                elif addr.network == 'ETH':
                    self._check_eth_deposits(addr)
                elif addr.network == 'BSC':
                    self._check_bsc_deposits(addr)
                elif addr.network == 'TRC20':
                    self._check_tron_deposits(addr)
                
                # Update last checked time
                addr.last_checked = timezone.now()
                addr.save(update_fields=['last_checked'])
                
            except Exception as e:
                print(f"Error checking {addr.address}: {e}")
        
        # Check confirmations for pending deposits
        self._check_pending_confirmations()
    
    def _check_btc_deposits(self, wallet_address):
        """Check Bitcoin deposits using Blockchain.info API"""
        try:
            # Use blockchain.info API
            url = f'https://blockchain.info/rawaddr/{wallet_address.address}'
            response = requests.get(url, timeout=10)
            data = response.json()
            
            for tx in data.get('txs', []):
                tx_hash = tx['hash']
                
                # Skip if already processed
                if PendingDeposit.objects.filter(tx_hash=tx_hash).exists():
                    continue
                
                # Calculate amount received to this address
                amount_satoshi = 0
                from_address = ''
                
                for output in tx['out']:
                    if output.get('addr') == wallet_address.address:
                        amount_satoshi += output['value']
                
                if amount_satoshi > 0:
                    # Get sender address
                    if tx['inputs']:
                        from_address = tx['inputs'][0].get('prev_out', {}).get('addr', '')
                    
                    amount_btc = Decimal(amount_satoshi) / Decimal(100000000)
                    confirmations = tx.get('confirmations', 0)
                    block_height = tx.get('block_height')
                    
                    # Create pending deposit
                    pending = PendingDeposit.objects.create(
                        user=wallet_address.user,
                        wallet_address=wallet_address,
                        currency='BTC',
                        network='BTC',
                        amount=amount_btc,
                        tx_hash=tx_hash,
                        from_address=from_address,
                        block_number=block_height,
                        confirmations=confirmations,
                        required_confirmations=3,
                        status='confirming' if confirmations < 3 else 'completed'
                    )
                    
                    # If enough confirmations, credit immediately
                    if confirmations >= 3:
                        self._credit_deposit(pending)
                    else:
                        # Send notification about pending deposit
                        NotificationService.create_notification(
                            user=wallet_address.user,
                            notification_type='deposit',
                            title=f'Bitcoin Deposit Detected',
                            message=f'Deposit of {amount_btc} BTC detected. Waiting for {3 - confirmations} more confirmations.',
                            priority='normal'
                        )
        
        except Exception as e:
            print(f"Error checking BTC deposits: {e}")
    
    def _check_eth_deposits(self, wallet_address):
        """Check Ethereum deposits (ETH and ERC-20 tokens)"""
        try:
            address = Web3.to_checksum_address(wallet_address.address)
            
            # Check ETH balance
            if wallet_address.currency == 'ETH':
                balance_wei = self.w3_eth.eth.get_balance(address)
                balance_eth = Web3.from_wei(balance_wei, 'ether')
                
                # Compare with last known balance (implement tracking)
                # For simplicity, checking recent transactions
                latest_block = self.w3_eth.eth.block_number
                
                # Get transactions (last 1000 blocks)
                from_block = max(0, latest_block - 1000)
                
                # This is simplified - in production use event logs
                # or a service like Etherscan API
            
            # Check ERC-20 tokens (USDT, USDC)
            if wallet_address.currency in ['USDT', 'USDC']:
                contract_address = (
                    self.USDT_ETH if wallet_address.currency == 'USDT' 
                    else self.USDC_ETH
                )
                
                self._check_erc20_transfers(
                    wallet_address, 
                    contract_address,
                    'ETH'
                )
        
        except Exception as e:
            print(f"Error checking ETH deposits: {e}")
    
    def _check_erc20_transfers(self, wallet_address, contract_address, network):
        """Check ERC-20 token transfers"""
        try:
            w3 = self.w3_eth if network == 'ETH' else self.w3_bsc
            
            # Get recent blocks
            latest_block = w3.eth.block_number
            from_block = latest_block - 1000  # Check last 1000 blocks
            
            # Create filter for Transfer events to our address
            address = Web3.to_checksum_address(wallet_address.address)
            contract = Web3.to_checksum_address(contract_address)
            
            # Get transfer events
            # Transfer event topic: Transfer(address,address,uint256)
            transfer_topic = self.TRANSFER_EVENT_SIGNATURE
            
            # Filter for transfers TO our address
            logs = w3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': 'latest',
                'address': contract,
                'topics': [
                    transfer_topic,
                    None,  # from (any address)
                    '0x' + address[2:].zfill(64).lower()  # to (our address)
                ]
            })
            
            for log in logs:
                tx_hash = log['transactionHash'].hex()
                
                # Skip if already processed
                if PendingDeposit.objects.filter(tx_hash=tx_hash).exists():
                    continue
                
                # Decode transfer amount
                amount_raw = int(log['data'], 16)
                
                # USDT and USDC use 6 decimals
                amount = Decimal(amount_raw) / Decimal(1000000)
                
                # Get transaction details
                tx = w3.eth.get_transaction(log['transactionHash'])
                from_address = tx['from']
                
                # Get confirmations
                tx_block = log['blockNumber']
                confirmations = latest_block - tx_block
                
                # Create pending deposit
                pending = PendingDeposit.objects.create(
                    user=wallet_address.user,
                    wallet_address=wallet_address,
                    currency=wallet_address.currency,
                    network=network,
                    amount=amount,
                    tx_hash=tx_hash,
                    from_address=from_address,
                    block_number=tx_block,
                    confirmations=confirmations,
                    required_confirmations=12,  # ETH needs more confirmations
                    status='confirming' if confirmations < 12 else 'completed'
                )
                
                if confirmations >= 12:
                    self._credit_deposit(pending)
                else:
                    NotificationService.create_notification(
                        user=wallet_address.user,
                        notification_type='deposit',
                        title=f'{wallet_address.currency} Deposit Detected',
                        message=f'Deposit of {amount} {wallet_address.currency} detected. Waiting for confirmations ({confirmations}/12).',
                        priority='normal'
                    )
        
        except Exception as e:
            print(f"Error checking ERC-20 transfers: {e}")
    
    def _check_bsc_deposits(self, wallet_address):
        """Check Binance Smart Chain deposits"""
        try:
            address = Web3.to_checksum_address(wallet_address.address)
            
            # Check BNB balance
            if wallet_address.currency == 'BNB':
                balance_wei = self.w3_bsc.eth.get_balance(address)
                balance_bnb = Web3.from_wei(balance_wei, 'ether')
                # Similar to ETH checking
            
            # Check BEP-20 tokens
            if wallet_address.currency in ['USDT', 'USDC']:
                contract_address = (
                    self.USDT_BSC if wallet_address.currency == 'USDT'
                    else self.USDC_BSC
                )
                
                self._check_erc20_transfers(
                    wallet_address,
                    contract_address,
                    'BSC'
                )
        
        except Exception as e:
            print(f"Error checking BSC deposits: {e}")
    
    def _check_tron_deposits(self, wallet_address):
        """Check TRON (TRC-20) deposits"""
        # Use TronGrid API or similar
        # Implementation similar to ETH but for Tron network
        pass
    
    def _check_pending_confirmations(self):
        """Update confirmations for pending deposits"""
        pending = PendingDeposit.objects.filter(
            status__in=['detected', 'confirming']
        )
        
        for deposit in pending:
            try:
                if deposit.network == 'BTC':
                    # Check BTC confirmations
                    url = f'https://blockchain.info/rawtx/{deposit.tx_hash}'
                    response = requests.get(url, timeout=10)
                    data = response.json()
                    confirmations = data.get('confirmations', 0)
                    
                    deposit.confirmations = confirmations
                    
                    if confirmations >= deposit.required_confirmations:
                        deposit.status = 'completed'
                        self._credit_deposit(deposit)
                    
                    deposit.save()
                
                elif deposit.network in ['ETH', 'BSC']:
                    w3 = self.w3_eth if deposit.network == 'ETH' else self.w3_bsc
                    
                    # Get current block
                    latest_block = w3.eth.block_number
                    confirmations = latest_block - deposit.block_number
                    
                    deposit.confirmations = confirmations
                    
                    if confirmations >= deposit.required_confirmations:
                        deposit.status = 'completed'
                        self._credit_deposit(deposit)
                    
                    deposit.save()
            
            except Exception as e:
                print(f"Error updating confirmations for {deposit.tx_hash}: {e}")
    
    @db_transaction.atomic
    def _credit_deposit(self, pending_deposit):
        """Credit user's wallet after deposit confirmation"""
        # Get or create wallet
        wallet, _ = Wallet.objects.get_or_create(
            user=pending_deposit.user,
            currency=pending_deposit.currency
        )
        
        # Add balance
        wallet.balance += pending_deposit.amount
        wallet.save()
        
        # Create transaction record
        tx = Transaction.objects.create(
            user=pending_deposit.user,
            transaction_type='deposit',
            currency=pending_deposit.currency,
            amount=pending_deposit.amount,
            status='completed',
            reference_id=f'DEPOSIT-{pending_deposit.tx_hash[:12]}',
            external_id=pending_deposit.tx_hash,
            completed_at=timezone.now()
        )
        
        # Link transaction to pending deposit
        pending_deposit.transaction = tx
        pending_deposit.completed_at = timezone.now()
        pending_deposit.save()
        
        # Update wallet address stats
        wallet_addr = pending_deposit.wallet_address
        wallet_addr.total_received += pending_deposit.amount
        wallet_addr.total_deposits += 1
        wallet_addr.save()
        
        # Send notification
        NotificationService.notify_deposit(
            user=pending_deposit.user,
            amount=pending_deposit.amount,
            currency=pending_deposit.currency,
            tx_hash=pending_deposit.tx_hash
        )


# Initialize detector
deposit_detector = DepositDetector()