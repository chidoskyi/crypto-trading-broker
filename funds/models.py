# funds/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

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