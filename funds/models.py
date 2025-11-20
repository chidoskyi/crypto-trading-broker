# funds/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
# funds/models.py (UPDATED)
from django.db import models
from django.contrib.auth import get_user_model
import qrcode
from io import BytesIO
from django.core.files import File

User = get_user_model()

class Wallet(models.Model):
    """User wallet for multiple currencies"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    currency = models.CharField(max_length=10)  # USD, EUR, BTC, ETH, etc.
    balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    locked_balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'currency']

class Transaction(models.Model):
    """Record all financial transactions"""
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('trade', 'Trade'),
        ('transfer', 'Transfer'),
        ('loan', 'Loan'),
        ('loan_repayment', 'Loan Repayment'),
        ('referral_bonus', 'Referral Bonus'),
        ('signal_purchase', 'Signal Purchase')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    currency = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference_id = models.CharField(max_length=100, unique=True)
    external_id = models.CharField(max_length=100, blank=True)  # Payment processor ID
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class Deposit(models.Model):
    """Deposit requests"""
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('card', 'Credit/Debit Card'),
            ('crypto', 'Cryptocurrency')
        ]
    )
    payment_details = models.JSONField()  # Store payment-specific data
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        verbose_name = 'Deposit'
        verbose_name_plural = 'Deposits'

class Withdrawal(models.Model):
    """Withdrawal requests"""
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)
    destination_type = models.CharField(
        max_length=20,
        choices=[
            ('bank_account', 'Bank Account'),
            ('crypto_wallet', 'Crypto Wallet')
        ]
    )
    destination_details = models.JSONField()
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_withdrawals'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)


class CryptoWalletAddress(models.Model):
    """Unique crypto addresses for user deposits"""
    
    NETWORK_CHOICES = [
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum (ERC-20)'),
        ('BSC', 'Binance Smart Chain (BEP-20)'),
        ('TRC20', 'Tron (TRC-20)'),
    ]
    
    CURRENCY_CHOICES = [
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('USDT', 'Tether USD'),
        ('USDC', 'USD Coin'),
        ('BNB', 'Binance Coin'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crypto_addresses')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES)
    network = models.CharField(max_length=10, choices=NETWORK_CHOICES)
    address = models.CharField(max_length=100, unique=True, db_index=True)
    
    # QR Code
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    
    # Address derivation info
    derivation_path = models.CharField(max_length=100, blank=True)
    address_index = models.IntegerField(default=0)
    
    # Tracking
    total_received = models.DecimalField(max_digits=30, decimal_places=18, default=0)
    total_deposits = models.IntegerField(default=0)
    last_checked = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'currency', 'network']
        indexes = [
            models.Index(fields=['address']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.currency} ({self.network})"
    
    def generate_qr_code(self):
        """Generate QR code for deposit address"""
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Add address to QR code
        # For crypto wallets, use appropriate URI scheme
        if self.currency == 'BTC':
            qr_data = f"bitcoin:{self.address}"
        elif self.currency == 'ETH':
            qr_data = f"ethereum:{self.address}"
        elif self.currency in ['USDT', 'USDC'] and self.network == 'ETH':
            qr_data = f"ethereum:{self.address}"
        elif self.network == 'BSC':
            qr_data = self.address  # BSC uses same format as ETH
        else:
            qr_data = self.address
        
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Save to model
        filename = f'qr_{self.currency}_{self.network}_{self.user.id}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        buffer.close()
    
    def save(self, *args, **kwargs):
        # Generate QR code if address exists and QR doesn't
        if self.address and not self.qr_code:
            self.generate_qr_code()
        super().save(*args, **kwargs)


class PendingDeposit(models.Model):
    """Track pending crypto deposits"""
    
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('confirming', 'Confirming'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet_address = models.ForeignKey(CryptoWalletAddress, on_delete=models.CASCADE)
    
    currency = models.CharField(max_length=10)
    network = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=18)
    
    # Transaction details
    tx_hash = models.CharField(max_length=100, unique=True, db_index=True)
    from_address = models.CharField(max_length=100)
    block_number = models.BigIntegerField(null=True, blank=True)
    
    # Confirmation tracking
    confirmations = models.IntegerField(default=0)
    required_confirmations = models.IntegerField(default=3)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    
    detected_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Link to transaction after completion
    transaction = models.ForeignKey(
        'Transaction', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['tx_hash']),
            models.Index(fields=['status', 'detected_at']),
        ]
    
    def __str__(self):
        return f"{self.currency} deposit: {self.amount} ({self.status})"


class DepositMethod(models.Model):
    """Available deposit methods and their configurations"""
    
    currency = models.CharField(max_length=10)
    network = models.CharField(max_length=20)
    name = models.CharField(max_length=100)  # e.g., "USDT (ERC-20)"
    
    # Settings
    min_deposit = models.DecimalField(max_digits=30, decimal_places=18)
    max_deposit = models.DecimalField(max_digits=30, decimal_places=18, null=True, blank=True)
    deposit_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    deposit_fee_fixed = models.DecimalField(max_digits=30, decimal_places=18, default=0)
    
    # Blockchain settings
    required_confirmations = models.IntegerField(default=3)
    block_time_seconds = models.IntegerField(default=15)
    
    # Contract address for tokens
    contract_address = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['currency', 'network']
        ordering = ['order', 'currency']
    
    def __str__(self):
        return f"{self.currency} - {self.network}"