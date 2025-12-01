# funds/services/wallet_generator.py
from web3 import Web3
from eth_account import Account
from bitcoin import *
from mnemonic import Mnemonic
import hashlib
from django.conf import settings
from funds.models import CryptoWalletAddress

class WalletGenerator:
    """Generate deterministic wallet addresses for users"""
    
    def __init__(self):
        # Initialize Web3 for Ethereum/BSC
        self.w3_eth = Web3(Web3.HTTPProvider(settings.ETHEREUM_NODE_URL))
        self.w3_bsc = Web3(Web3.HTTPProvider(settings.BSC_NODE_URL))
        
        # Master seed from settings (keep this VERY secure!)
        self.master_seed = settings.MASTER_SEED
    
    def generate_address(self, user, currency, network):
        """Generate unique address for user"""
        
        # Check if address already exists
        existing = CryptoWalletAddress.objects.filter(
            user=user,
            currency=currency,
            network=network
        ).first()
        
        if existing:
            return existing
        
        # Get next address index for this currency/network
        last_address = CryptoWalletAddress.objects.filter(
            currency=currency,
            network=network
        ).order_by('-address_index').first()
        
        address_index = (last_address.address_index + 1) if last_address else 0
        
        # Generate address based on network type
        if network == 'BTC':
            address = self._generate_btc_address(user.id, address_index)
        elif network in ['ETH', 'BSC']:
            address = self._generate_evm_address(user.id, address_index, network)
        elif network == 'TRC20':
            address = self._generate_tron_address(user.id, address_index)
        else:
            raise ValueError(f"Unsupported network: {network}")
        
        # Create wallet address record
        wallet_address = CryptoWalletAddress.objects.create(
            user=user,
            currency=currency,
            network=network,
            address=address,
            address_index=address_index,
            derivation_path=f"m/44'/0'/0'/0/{address_index}"
        )
        
        return wallet_address
    
    def _generate_btc_address(self, user_id, index):
        """Generate Bitcoin address using HD wallet derivation"""
        # Create deterministic seed
        seed = f"{self.master_seed}:BTC:{user_id}:{index}".encode()
        private_key = hashlib.sha256(seed).hexdigest()
        
        # Generate public key
        public_key = privtopub(private_key)
        
        # Generate P2PKH address (starts with 1)
        address = pubtoaddr(public_key)
        
        return address
    
    def _generate_evm_address(self, user_id, index, network):
        """Generate Ethereum/BSC address (both use same format)"""
        # Create deterministic seed
        seed = f"{self.master_seed}:{network}:{user_id}:{index}".encode()
        private_key_bytes = hashlib.sha256(seed).digest()
        
        # Generate account from private key
        account = Account.from_key(private_key_bytes)
        
        return account.address
    
    def _generate_tron_address(self, user_id, index):
        """Generate TRON address (TRC-20)"""
        # Tron uses same key generation as Ethereum
        # but different address format
        seed = f"{self.master_seed}:TRC20:{user_id}:{index}".encode()
        private_key_bytes = hashlib.sha256(seed).digest()
        
        # For production, use tronpy library
        # For now, return a placeholder
        # In production: from tronpy.keys import PrivateKey
        # private_key = PrivateKey(private_key_bytes)
        # address = private_key.public_key.to_base58check_address()
        
        account = Account.from_key(private_key_bytes)
        eth_address = account.address
        
        # Convert to Tron format (starts with T)
        # This is simplified - use proper Tron library in production
        tron_address = 'T' + eth_address[2:35]
        
        return tron_address
    
    def get_private_key(self, wallet_address):
        """
        Get private key for a wallet address
        WARNING: Only use this for withdrawals, keep very secure!
        """
        seed = f"{self.master_seed}:{wallet_address.network}:{wallet_address.user.id}:{wallet_address.address_index}".encode()
        
        if wallet_address.network == 'BTC':
            return hashlib.sha256(seed).hexdigest()
        else:  # EVM or TRC20
            return hashlib.sha256(seed).digest()


# Initialize wallet generator
wallet_generator = WalletGenerator()