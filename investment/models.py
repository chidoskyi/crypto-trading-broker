from django.db import models
# from django.contrib.auth.models import User
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum
from users.models import Account
from django.db.models.signals import post_save
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
import pyotp
# from tinymce.models import HTMLField
from core import settings
from django.db import transaction
import uuid
import logging
import secrets
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
import qrcode
from io import BytesIO
from django.core.files import File

logger = logging.getLogger(__name__)

User = get_user_model()

class PaymentMethod(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)
    icon = models.ImageField(upload_to='payment_methods/', null=True, blank=True, help_text="Payment method icon")
    is_active = models.BooleanField(default=True)
    min_amount = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Minimum amount allowed for this payment method"
    )
    max_amount = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('999999.99'),
        help_text="Maximum amount allowed for this payment method"
    )
    processing_time = models.CharField(
        max_length=100,
        default="24-48 hours",
        help_text="Estimated processing time"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'

    @property
    def is_available(self):
        return self.is_active

    @property
    def icon_url(self):
        if self.icon:
            return self.icon.url
        return None


class Deposit(models.Model):
    CRYPTO_CHOICES = [
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('USDT', 'Tether'),
        ('LTC', 'Litecoin'),
        ('BNB', 'Binance Coin'),
    ]

    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    REJECTED = "Rejected"
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected')
    ]
    
    deposit_id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True,  
        blank=True, 
        default=None
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_proof = models.ImageField(upload_to="deposit/proofs/", null=False, blank=False)  
    has_deposited = models.BooleanField(default=False) 
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    wallet = models.ForeignKey('Wallet', on_delete=models.CASCADE)
    payment_method = models.ForeignKey(
        PaymentMethod, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        default=None
    )
    
    # New field to track selected cryptocurrency
    selected_crypto = models.CharField(max_length=10, choices=CRYPTO_CHOICES, default='BTC')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.wallet.user.email} - {self.selected_crypto}"
    
    def get_admin_wallet_address(self):
        """Get the admin's wallet address based on selected cryptocurrency"""
        wallet = Wallet.get_wallet()
        wallet_mapping = {
            'BTC': wallet.btc_wallet,
            'ETH': wallet.eth_wallet,
            'USDT': wallet.usdt_wallet,
            'LTC': wallet.ltc_wallet,
            'BNB': wallet.bnb_wallet,
        }
        return wallet_mapping.get(self.selected_crypto)
    

    def __str__(self):
        return f"Deposit: {self.amount} {self.selected_crypto}"


class WithdrawalCode(models.Model):
    """Model to store withdrawal codes requested by users"""
    code_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal_codes')
    code = models.CharField(max_length=6, unique=True)
    is_used = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)  # Admin must approve
    expiry_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.code}"
    
    @classmethod
    def generate_code(cls, user):
        """Generate a unique 6-digit code"""
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not cls.objects.filter(code=code).exists():
                return code
    
    def is_valid(self):
        """Check if code is valid (not used, not expired, and approved)"""
        return (
            not self.is_used 
            and self.is_approved 
            and timezone.now() < self.expiry_date
        )
    
    def mark_as_used(self):
        """Mark code as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])
    
    class Meta:
        ordering = ['-created_at']

class Withdrawal(models.Model):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    REJECTED = "Rejected"
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected')
    ]

    withdrawal_id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    wallet = models.ForeignKey('Wallet', on_delete=models.CASCADE)  # Add this
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    wallet_address = models.CharField(max_length=100)
    payment_method = models.ForeignKey(
        'PaymentMethod', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        default=None
    )
    withdrawal_code = models.ForeignKey(
        WithdrawalCode,
        on_delete=models.SET_NULL,
        null=True,
        related_name='withdrawals'
    )
    code_verified = models.BooleanField(default=False)
    code_expiry = models.DateTimeField(null=True, blank=True)
    pending_withdrawals = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Withdrawal: {self.amount} - {self.status}"
    
    def generate_withdrawal_code(self):
        """Generate 6-digit withdrawal code"""
        import random
        import string
        self.withdraw_code = ''.join(random.choices(string.digits, k=6))
        self.code_expiry = timezone.now() + timedelta(minutes=10)  # Code expires in 10 minutes
        self.code_verified = False
        self.save(update_fields=['withdraw_code', 'code_expiry', 'code_verified'])
        return self.withdraw_code
    
    def verify_code(self, code):
        """Verify withdrawal code"""
        if not self.code_expiry or timezone.now() > self.code_expiry:
            return False, "Code has expired"
        
        if self.withdraw_code == code:
            self.code_verified = True
            self.save(update_fields=['code_verified'])
            return True, "Code verified successfully"
        
        return False, "Invalid code"
    
    def is_code_expired(self):
        """Check if code is expired"""
        if not self.code_expiry:
            return True
        return timezone.now() > self.code_expiry

    class Meta:
        ordering = ['-created_at']


# Model for different investment plans
class InvestmentPlan(models.Model):
    FIRST = '1st Plan'
    SECOND = '2nd Plan'
    ThRID = '3rd Plan'
    FOURTH = '4th Plan'
    FIFTH = '5th Plan'

    PLAN_TYPES = [
        (FIRST, '1st Plan'),
        (SECOND, '2nd Plan'),
        (ThRID, '3rd Plan'),
        (FOURTH, '4th Plan'),
        (FIFTH, '5th Plan'),
    ]

    DURATION_UNIT_HOURS = 'hours'
    DURATION_UNIT_DAYS = 'days'
    
    DURATION_UNITS = [
        (DURATION_UNIT_HOURS, 'Hours'),
        (DURATION_UNIT_DAYS, 'Days'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # In percentage
    duration = models.PositiveIntegerField()  # Duration value
    duration_unit = models.CharField(
        max_length=5,
        choices=DURATION_UNITS,
        default=DURATION_UNIT_DAYS
    )
    plan_types = models.CharField(max_length=50, choices=PLAN_TYPES, default=FIRST)
    min_investment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_investment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.interest_rate}% after {self.get_duration_display()})"
    
    class Meta:
        ordering = ['created_at']

    def get_duration_display(self):
        """Return a human-readable duration string"""
        if self.duration_unit == self.DURATION_UNIT_HOURS:
            if self.duration == 24:
                return "24 hours"
            elif self.duration == 48:
                return "48 hours"
            elif self.duration == 72:
                return "72 hours"
            else:
                return f"{self.duration} hours"
        else:
            return f"{self.duration} days"

    def get_duration_in_hours(self):
        """Get the total duration in hours"""
        if self.duration_unit == self.DURATION_UNIT_HOURS:
            return self.duration
        return self.duration * 24

    def get_hourly_rate(self):
        """Calculate the hourly interest rate"""
        total_hours = self.get_duration_in_hours()
        if total_hours > 0:
            return self.interest_rate / total_hours
        return Decimal('0.0')

    def save(self, *args, **kwargs):
        if not self.pk:  # Only for new instances
            # Convert legacy duration_in_days to new format if needed
            if hasattr(self, 'duration_in_days'):
                self.duration = self.duration_in_days
                self.duration_unit = self.DURATION_UNIT_DAYS
                delattr(self, 'duration_in_days')
        super().save(*args, **kwargs)

    @property
    def daily_rate(self):
        """Calculate the daily interest rate for compatibility"""
        if self.duration_unit == self.DURATION_UNIT_HOURS:
            return self.interest_rate / Decimal(str(self.duration / 24))
        return self.interest_rate / Decimal(str(self.duration)) if self.duration > 0 else Decimal('0.0')


# Model to store user investments
class Investment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey('InvestmentPlan', on_delete=models.CASCADE, related_name='investments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    roi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)  # Allow null temporarily for save method
    completed = models.BooleanField(default=False)
    is_running = models.BooleanField(default=False)
    is_reinvestment = models.BooleanField(default=False)
    progress_percentage = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'start_date', 'status']),
        ]
    
    def clean(self):
        """Validate the investment data"""
        if not isinstance(self.amount, Decimal):
            try:
                self.amount = Decimal(str(self.amount))
            except (TypeError, InvalidOperation):
                raise ValidationError({'amount': 'Invalid amount value'})
        
        if self.amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than zero'})
        
        # Validate plan exists
        if not self.plan:
            raise ValidationError({'plan': 'Investment plan is required'})
        
        # Validate plan has required fields
        if not hasattr(self.plan, 'duration') or not self.plan.duration:
            raise ValidationError({'plan': 'Investment plan has invalid duration'})
        
        if not hasattr(self.plan, 'duration_unit') or not self.plan.duration_unit:
            raise ValidationError({'plan': 'Investment plan has invalid duration unit'})
    
    def calculate_end_date(self):
        """
        Calculate end_date based on start_date and plan duration
        
        Returns:
            datetime: The calculated end date
        """
        if not self.plan:
            raise ValidationError('Investment plan is required to calculate end date')
        
        if not self.start_date:
            self.start_date = timezone.now()
        
        try:
            duration_value = int(self.plan.duration)
            
            if duration_value <= 0:
                raise ValidationError(f'Invalid plan duration: {duration_value}')
            
            if self.plan.duration_unit == 'hours':
                end_date = self.start_date + timezone.timedelta(hours=duration_value)
            elif self.plan.duration_unit == 'days':
                end_date = self.start_date + timezone.timedelta(days=duration_value)
            else:
                raise ValidationError(f'Invalid duration unit: {self.plan.duration_unit}')
            
            return end_date
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating end_date: {str(e)}")
            raise ValidationError(f'Failed to calculate end date: {str(e)}')
    
    def save(self, *args, **kwargs):
        """Override save to automatically calculate end_date if not set"""
        
        # Run validation
        self.clean()
        
        # Calculate end_date if not already set
        if not self.end_date:
            try:
                self.end_date = self.calculate_end_date()
                logger.info(f"Auto-calculated end_date: {self.end_date} for investment")
            except Exception as e:
                logger.error(f"Failed to calculate end_date in save(): {str(e)}")
                raise
        
        # Ensure end_date is not None before saving
        if not self.end_date:
            raise ValidationError('end_date cannot be None')
        
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"Investment({self.user.username}, {self.amount}, Plan: {self.plan.name})"

    def is_active(self):
        """Check if the investment is still within its active period."""
        now = timezone.now()
        return self.start_date <= now <= self.end_date and not self.completed
    
    def calculate_return(self):
        """
        Calculate the Return on Investment (ROI) for this investment.
        
        The ROI is calculated based on the plan's duration unit (hours/days):
        - For hourly plans: amount * (hourly_rate/100) * hours
        - For daily plans: amount * (daily_rate/100) * days
        
        Returns:
            Decimal: The calculated ROI rounded to 2 decimal places
        """
        try:
            if self.plan.duration_unit == 'hours':
                hourly_rate = self.plan.interest_rate / Decimal(str(self.plan.duration))
                roi = self.amount * (hourly_rate / Decimal('100')) * Decimal(str(self.plan.duration))
            else:  # daily
                daily_rate = self.plan.interest_rate / Decimal(str(self.plan.duration))
                roi = self.amount * (daily_rate / Decimal('100')) * Decimal(str(self.plan.duration))
            
            return Decimal(str(round(float(roi), 2)))
        except Exception as e:
            logger.error(f"ROI calculation error for investment {self.id}: {str(e)}")
            return Decimal('0.00')
    
    def process_roi(self):
        """Process ROI for this investment when it reaches end date."""
        if self.completed:
            return False

        now = timezone.now()
        if now >= self.end_date:
            try:
                # Calculate final ROI
                self.roi = self.calculate_return()
                self.completed = True
                self.save()

                # Update user's account
                account = Account.objects.get(user=self.user)
                account.total_earned += self.roi
                account.investment_balance += self.roi
                account.save(update_fields=['total_earned', 'investment_balance'])

                # Create notification
                from notifications.models import Notification
                Notification.create_notification(
                    user=self.user,
                    title="Investment ROI Credited",
                    message=f"Your investment in {self.plan.name} has matured. ROI of ${self.roi} has been credited to your account.",
                    notification_type='transaction',
                    link='/user/investments/'
                )

                return True
            except Exception as e:
                logger.error(f"Error processing ROI for investment {self.id}: {str(e)}")
                return False

        return False
    
    def get_remaining_seconds(self):
        if not self.is_running or self.completed:
            return 0
        now = timezone.now()
        if now > self.end_date:
            return 0
        return int((self.end_date - now).total_seconds())

    def get_progress_percentage(self):
        if not self.is_running:
            return 0
        total_duration = (self.end_date - self.start_date).total_seconds()
        if total_duration <= 0:
            return 100
        elapsed = (timezone.now() - self.start_date).total_seconds()
        progress = (elapsed / total_duration) * 100
        return min(round(progress, 2), 100)
    
    def update_progress(self):
        """Update the progress_percentage field in database"""
        if self.is_running and not self.completed:
            calculated_progress = min(self.get_progress_percentage(), 100)
            if calculated_progress != self.progress_percentage:
                self.progress_percentage = calculated_progress
                self.save(update_fields=['progress_percentage'])
                return True
        return False


    def update_status(self):
        """
        Update investment status and process matured investments
        
        When an investment matures:
        - Principal + ROI is credited to investment_balance (NOT available_balance)
        - Amount is removed from invested_balance
        - Investment is marked as completed
        """
        now = timezone.now()
        if self.status == self.STATUS_APPROVED and self.is_running:
            # Update progress percentage
            self.progress_percentage = self.get_progress_percentage()
            
            if now >= self.end_date:
                try:
                    # Validate amount before proceeding
                    if not self.amount or self.amount <= 0:
                        logger.error(f"Invalid amount for investment {self.id}: {self.amount}")
                        return False

                    with transaction.atomic():
                        # Get user account with lock
                        account = Account.objects.select_for_update().get(user=self.user)
                        
                        # Calculate ROI if not already calculated
                        if not self.roi:
                            self.roi = self.calculate_return()
                            if not self.roi or self.roi < 0:
                                logger.error(f"Invalid ROI calculated for investment {self.id}: {self.roi}")
                                return False
                        
                        # ✅ Update account balances
                        # Credit principal + ROI to investment_balance (destination for matured investments)
                        account.investment_balance += (self.amount + self.roi)
                        
                        # Remove from invested_balance (no longer actively invested)
                        account.invested_balance -= self.amount
                        
                        # ✅ DEDUCT from active_investments when investment completes
                        account.active_investments -= self.amount
                        
                        # Add ROI to total earnings
                        account.total_earned += self.roi
                        
                        # Save account changes
                        account.save(update_fields=[
                            'investment_balance',
                            'invested_balance',
                            'active_investments',
                            'total_earned'
                        ])
                        
                        # ✅ Update investment status - Mark as completed and stop running
                        self.completed = True
                        self.is_running = False
                        self.progress_percentage = 100  # Set to 100% when completed
                        self.save(update_fields=['completed', 'is_running', 'progress_percentage'])

                        # Send email notification
                        try:
                            from django.core.mail import send_mail
                            from django.template.loader import render_to_string
                            from django.conf import settings
                            
                            context = {
                                'username': self.user.username,
                                'plan_name': self.plan.name,
                                'amount': self.amount,
                                'roi': self.roi,
                                'total_return': self.amount + self.roi,
                                'completion_date': now.strftime('%Y-%m-%d %H:%M:%S'),
                                'investment_balance': account.investment_balance
                            }
                            
                            email_body = render_to_string('emails/investment_completed.html', context)
                            
                            send_mail(
                                subject=f"Investment in {self.plan.name} Plan Completed",
                                message=email_body,
                                from_email=settings.ADMIN_EMAIL,
                                recipient_list=[self.user.email],
                                fail_silently=False,
                                html_message=email_body
                            )
                            logger.info(f"Investment completion email sent to {self.user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send investment completion email: {str(e)}")
                        
                        logger.info(
                            f"INVESTMENT MATURED: ID={self.id}, User={self.user.username}, "
                            f"Principal=${self.amount}, ROI=${self.roi}, "
                            f"New Investment Balance=${account.investment_balance}, "
                            f"Active Investments=${account.active_investments}"
                        )
                        
                        return True
                        
                except Exception as e:
                    logger.error(f"Error completing investment {self.id}: {str(e)}")
                    logger.exception(e)
                    return False
                    
            else:
                # Investment is still running - update progress in database
                # Only save if progress has actually changed to avoid unnecessary DB writes
                current_progress = self.get_progress_percentage()
                if current_progress != self.progress_percentage:
                    self.progress_percentage = current_progress
                    self.save(update_fields=['progress_percentage'])
        
        return False
        

        
class InvestmentTransaction(models.Model):
    DEPOSIT = 'deposit'
    WITHDRAWAL = 'withdrawal'
    INVESTMENT = 'investment'
    REINVESTMENT = 'reinvestment'

    TRANSACTION_TYPES = [
        (DEPOSIT, 'Deposit'),
        (WITHDRAWAL, 'Withdrawal'),
        (INVESTMENT, 'Investment'),
        (REINVESTMENT, 'Reinvestment'),
    ]
    
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    REJECTED = "Rejected"
    REINVESTED = "Reinvested"
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('reinvested', 'Reinvested'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transactionid = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    investment_plan = models.ForeignKey('InvestmentPlan', on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=100, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.ForeignKey(
        'PaymentMethod', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        default=None
    )
    wallet_used = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        payment_method_name = self.payment_method.name if self.payment_method else 'N/A'
        return f"Transaction({self.user.username}, {self.transaction_type}, {self.amount}, Method: {payment_method_name}, Status: {self.status})"

    def save(self, *args, **kwargs):
            
        # Handle payment method for reinvestments
        if self.transaction_type == self.REINVESTMENT and not self.payment_method:
            balance_method, _ = PaymentMethod.objects.get_or_create(
                code='BALANCE',
                defaults={
                    'name': 'Account Balance',
                    'is_active': True,
                    'min_amount': '0.00',
                    'max_amount': '999999.99',
                    'processing_time': 'Instant'
                }
            )
            self.payment_method = balance_method
            
        super().save(*args, **kwargs)

    @classmethod
    def create_transaction(cls, user, transaction_type, amount, payment_method=None, **kwargs):
        """Helper method to create transactions with proper payment method handling"""
        try:
            # If no payment method provided but it's a reinvestment, get or create BALANCE payment method
            if payment_method is None and transaction_type == cls.REINVESTMENT:
                payment_method, _ = PaymentMethod.objects.get_or_create(
                    code='BALANCE',
                    defaults={
                        'name': 'Account Balance',
                        'is_active': True,
                        'min_amount': '0.00',
                        'max_amount': '999999.99',
                        'processing_time': 'Instant'
                    }
                )
            
            return cls.objects.create(
                user=user,
                transaction_type=transaction_type,
                amount=amount,
                payment_method=payment_method,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error creating transaction: {str(e)}")
            raise



class InvestmentTransactions(models.Model):
    DEPOSIT = 'deposit'
    WITHDRAWAL = 'withdrawal'
    INVESTMENT = 'investment'
    REINVESTMENT = 'reinvestment'

    TRANSACTION_TYPES = [
        (DEPOSIT, 'Deposit'),
        (WITHDRAWAL, 'Withdrawal'),
        (INVESTMENT, 'Investment'),
        (REINVESTMENT, 'Reinvestment'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('reinvested', 'Reinvested'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions_confirmations')
    transactionid = models.CharField(max_length=12, unique=True, editable=False)
    investment_plan = models.ForeignKey('InvestmentPlan', on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=100, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.SET_NULL, null=True)
    wallet_used = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        payment_method_name = self.payment_method.name if self.payment_method else 'N/A'
        return f"Transaction({self.user.username}, {self.transaction_type}, {self.amount}, Method: {payment_method_name}, Status: {self.status})"
    
    class Meta:
        verbose_name = "Transactions Confirmed/Rejected"

    def save(self, *args, **kwargs):
        if not self.transactionid:
            self.transactionid = self.generate_transaction_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_transaction_id():
        return secrets.token_urlsafe(9).upper().replace('-', '').replace('_', '')[:12]



class TransactionHistory(models.Model):
    transaction = models.ForeignKey(InvestmentTransaction, on_delete=models.CASCADE, default=1)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    investment_plan = models.ForeignKey(InvestmentPlan, on_delete=models.SET_NULL, null=True, blank=True)
    investment = models.ForeignKey(Investment, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=100, choices=InvestmentTransaction.TRANSACTION_TYPES)
    status = models.CharField(max_length=10, choices=InvestmentTransaction.STATUS_CHOICES, default="pending")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        payment_method_name = self.payment_method.name if self.payment_method else 'N/A'
        return f"{self.transaction_type.capitalize()} - {self.amount} by {self.user.username} via {payment_method_name} on {self.created_at}"

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create_transaction(cls, user, transaction_type, amount, status, investment, investment_plan, payment_method, description=None):
        """Method to create a transaction history record."""
        cls.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            status=status,
            description=description,
            investment=investment,
            investment_plan=investment_plan,
            payment_method=payment_method,
        )

    @classmethod
    def get_user_transaction_history(cls, user):
        """Method to get transaction history for a specific user."""
        return cls.objects.filter(user=user)


 
class Wallet(models.Model):
    """Admin's wallet addresses for receiving deposits"""
    # Wallet addresses
    btc_wallet = models.CharField(max_length=255, blank=True, null=True, help_text="Admin's Bitcoin wallet address")
    eth_wallet = models.CharField(max_length=255, blank=True, null=True, help_text="Admin's Ethereum wallet address")
    usdt_wallet = models.CharField(max_length=255, blank=True, null=True, help_text="Admin's USDT wallet address")
    ltc_wallet = models.CharField(max_length=255, blank=True, null=True, help_text="Admin's Litecoin wallet address")
    bnb_wallet = models.CharField(max_length=255, blank=True, null=True, help_text="Admin's Binance Coin wallet address")
    
    # QR Code images
    btc_qr = models.ImageField(upload_to='wallet_qr/', blank=True, null=True)
    eth_qr = models.ImageField(upload_to='wallet_qr/', blank=True, null=True)
    usdt_qr = models.ImageField(upload_to='wallet_qr/', blank=True, null=True)
    ltc_qr = models.ImageField(upload_to='wallet_qr/', blank=True, null=True)
    bnb_qr = models.ImageField(upload_to='wallet_qr/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Admin Wallet Addresses"
    
    class Meta:
        verbose_name = "Admin Wallet"
        verbose_name_plural = "Admin Wallets"

    def generate_qr_code(self, data):
        """Generate QR code from wallet address"""
        if not data:
            return None
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return ContentFile(buffer.read())

    def save(self, *args, **kwargs):
        """Override save to automatically generate QR codes"""
        # Generate QR code for BTC wallet
        if self.btc_wallet:
            qr_content = self.generate_qr_code(self.btc_wallet)
            if qr_content:
                self.btc_qr.save(f'btc_qr.png', qr_content, save=False)
        elif not self.btc_wallet and self.btc_qr:
            self.btc_qr.delete(save=False)
        
        # Generate QR code for ETH wallet
        if self.eth_wallet:
            qr_content = self.generate_qr_code(self.eth_wallet)
            if qr_content:
                self.eth_qr.save(f'eth_qr.png', qr_content, save=False)
        elif not self.eth_wallet and self.eth_qr:
            self.eth_qr.delete(save=False)
        
        # Generate QR code for USDT wallet
        if self.usdt_wallet:
            qr_content = self.generate_qr_code(self.usdt_wallet)
            if qr_content:
                self.usdt_qr.save(f'usdt_qr.png', qr_content, save=False)
        elif not self.usdt_wallet and self.usdt_qr:
            self.usdt_qr.delete(save=False)
        
        # Generate QR code for LTC wallet
        if self.ltc_wallet:
            qr_content = self.generate_qr_code(self.ltc_wallet)
            if qr_content:
                self.ltc_qr.save(f'ltc_qr.png', qr_content, save=False)
        elif not self.ltc_wallet and self.ltc_qr:
            self.ltc_qr.delete(save=False)
        
        # Generate QR code for BNB wallet
        if self.bnb_wallet:
            qr_content = self.generate_qr_code(self.bnb_wallet)
            if qr_content:
                self.bnb_qr.save(f'bnb_qr.png', qr_content, save=False)
        elif not self.bnb_wallet and self.bnb_qr:
            self.bnb_qr.delete(save=False)
        
        super().save(*args, **kwargs)

    @classmethod
    def get_wallet(cls):
        """Get or create the single admin wallet instance"""
        wallet, created = cls.objects.get_or_create(pk=1)
        return wallet
