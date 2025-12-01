# users/models.py
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from django.db import transaction
from encrypted_fields.fields import EncryptedCharField
from django.core.validators import MinValueValidator, MaxValueValidator


class Country(models.Model):
    name = models.CharField(max_length=100)
    iso = models.CharField(max_length=3, unique=True)
    phone_code = models.CharField(max_length=10)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (+{self.phone_code})"


class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """Extended user model with trading platform features"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    username = models.CharField(_('username'), max_length=150, unique=True)  # ADD THIS
    first_name = models.CharField(_('first name'), max_length=150) 
    last_name = models.CharField(_('last name'), max_length=150) 
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    country = models.ForeignKey('Country', on_delete=models.SET_NULL, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('not_submitted', 'Not Submitted')
        ],
        default='not_submitted'
    )   
    
    # FIX: Remove default=timezone.now since auto_now_add is present
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ADD THREE REQUIRED FIELDS FOR AbstractBaseUser
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
    
    def get_profile(self):
        """Safely get or create user profile"""
        from users.models import Profile
        profile, created = Profile.objects.get_or_create(user=self)
        return profile
    
    def get_account(self):
        """Safely get or create user profile"""
        from users.models import Account
        account, created = Account.objects.get_or_create(user=self)
        return account
   
class Account(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_DISABLED = 'disabled'
    STATUS_PENALIZED = 'penalized'
    STATUS_BLOCKED = 'blocked'
    STATUS_UNDER_REVIEW = 'under_review'

    ACCOUNT_STATUSES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_SUSPENDED, 'Suspended'),
        (STATUS_DISABLED, 'Disabled'),
        (STATUS_PENALIZED, 'Penalized'),
        (STATUS_BLOCKED, 'Blocked'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
    ]

    # User relationship
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account')
    
    # Investment Balance Fields
    available_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Balance available for withdrawal or new investments"
    )
    
    trading_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Balance available for trading"
    )
    
    investment_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Balance available for investment"
    )
    invested_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total amount currently in active investments"
    )
    pending_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Balance pending confirmation or processing"
    )
    
    pending_deposit = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Deposit pending confirmation or processing"
    )
    
    pending_withdrawal = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Withdrawal pending confirmation or processing"
    )
    
    locked_trading_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Trading balance locked in open orders"
    )
    
    # Investment Statistics
    total_invested = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total amount invested across all time"
    )
    active_investments = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Current active investment amount"
    )
    total_earned = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total earnings from investments"
    )
    
    deposit_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total deposit balance"
    )
    
    # Transaction Statistics
    total_deposits = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total deposits made"
    )
    total_withdrawals = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total withdrawals made"
    )
    pending_withdrawals = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Amount in pending withdrawals"
    )
    
    # Account Status and Security
    status = models.CharField(
        max_length=20, 
        choices=ACCOUNT_STATUSES, 
        default=STATUS_ACTIVE
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)
    last_investment = models.DateTimeField(null=True, blank=True)
    last_withdrawal = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_account'
        verbose_name = 'User Account'
        verbose_name_plural = 'User Accounts'

    def __str__(self):
        return f"Account: {self.user.username} (Balance: ${self.available_balance})"

    @property
    def total_balance(self):
        """Calculate total balance including all assets"""
        return (
            self.available_balance +
            self.invested_balance +
            self.pending_balance +
            self.trading_balance +
            self.locked_trading_balance +
            self.investment_balance
        )
    
    @property
    def available_trading_balance(self):
        """✅ NEW: Get actual available trading balance (excluding locked)"""
        return self.trading_balance - self.locked_trading_balance
    

    def can_withdraw(self, amount):
        """Check if withdrawal is allowed"""
        if self.status != self.STATUS_ACTIVE:
            return False, "Account is not active"
            
        if amount > self.available_balance:
            return False, "Insufficient balance"
            

        return True, "Withdrawal allowed"

    @transaction.atomic
    def process_deposit(self, amount):
        """Process a new deposit"""
        # self.available_balance += amount
        self.pending_deposit += amount
        self.pending_balance += amount
        self.total_deposits += amount
        self.save()

    @property
    def calculate_active_investments(self):
        """Calculate total active investments from actual investment records"""
        from django.db.models import Sum
        return Investment.objects.filter(
            user=self.user,
            completed=False,
            status='approved',
            end_date__gt=timezone.now()
        ).aggregate(
            total_active=Sum('amount')
        )['total_active'] or Decimal('0.00')

    def update_active_investments(self):
        """Update active_investments field based on actual investment records"""
        self.active_investments = self.calculate_active_investments
        self.save(update_fields=['active_investments'])

    @transaction.atomic
    def process_investment(self, amount, plan):
        """Process a new investment"""
        if amount > self.investment_balance:
            raise ValueError("Insufficient balance for investment")

        # Deduct from available balance
        self.investment_balance -= amount
        
        # Add to total invested (lifetime total)
        self.total_invested += amount
        
        # Update timestamp
        self.last_investment = timezone.now()
        
        # Save the changes
        self.save(update_fields=['investment_balance', 'total_invested', 'last_investment'])
        
        # Update active investments based on actual records
        self.update_active_investments()

    @transaction.atomic
    def process_roi(self, investment_id, roi_amount):
        """Process ROI from an investment"""
        self.investment_balance += roi_amount
        self.total_earned += roi_amount
        self.save()

    @transaction.atomic
    def process_withdrawal(self, amount):
        """Process a withdrawal"""
        success, message = self.can_withdraw(amount)
        if not success:
            raise ValueError(message)

        self.available_balance -= amount
        self.total_withdrawals += amount
        self.last_withdrawal = timezone.now()
        self.save()

    def update_status(self, new_status, reason=None):
        """Update account status"""
        if new_status not in dict(self.ACCOUNT_STATUSES):
            raise ValueError("Invalid status")
            
        self.status = new_status
        self.save()



class KYCDocument(models.Model):
    """Store KYC verification documents"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('passport', 'Passport'),
            ('drivers_license', 'Driver\'s License'),
            ('national_id', 'National ID')
        ]
    )
    document_number = EncryptedCharField(max_length=100)
    document_front = models.FileField(upload_to='kyc/documents/')
    document_back = models.FileField(upload_to='kyc/documents/', null=True)
    selfie = models.FileField(upload_to='kyc/selfies/')
    address_proof = models.FileField(upload_to='kyc/address/')
    date_of_birth = models.DateField()
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kyc_reviews'
    )
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f"KYC Document for {self.user.email} - {self.document_type}"

class Profile(models.Model):
    """User profile model"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    kyc = models.OneToOneField(KYCDocument, on_delete=models.SET_NULL, null=True, blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        help_text="User profile picture"
    )
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
    
    def __str__(self):
        return f"{self.user.email}'s Profile"

    @property
    def is_complete(self):
        """Check if profile has required fields filled"""
        return bool(self.bio and self.location)

class Referral(models.Model):
    """User referral model with commission tier system"""
    
    # Commission tiers
    STARTER = 'starter'
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    ELITE = 'elite'
    
    TIER_CHOICES = [
        (STARTER, 'Starter (0-9 referrals) - 5%'),
        (BRONZE, 'Bronze (10-24 referrals) - 7%'),
        (SILVER, 'Silver (25-49 referrals) - 10%'),
        (GOLD, 'Gold (50-99 referrals) - 12%'),
        (ELITE, 'Elite (100+ referrals) - 15%'),
    ]
    
    # Tier thresholds and commission rates
    TIER_CONFIG = {
        STARTER: {'min': 0, 'max': 9, 'commission': 5},
        BRONZE: {'min': 10, 'max': 24, 'commission': 7},
        SILVER: {'min': 25, 'max': 49, 'commission': 10},
        GOLD: {'min': 50, 'max': 99, 'commission': 12},
        ELITE: {'min': 100, 'max': float('inf'), 'commission': 15},
    }
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    user = models.OneToOneField(
        'User',  # Use string reference to avoid circular import
        on_delete=models.CASCADE,
        related_name='referral'
    )
    referral_code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Unique referral code for this user"
    )
    referred_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users',
        help_text="User who referred this user"
    )
    total_referrals = models.PositiveIntegerField(
        default=0,
        help_text="Total number of successful referrals"
    )
    current_tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default=STARTER,
        help_text="Current commission tier"
    )
    total_commission_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Total commission earned from referrals"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_referrals', '-created_at']
        verbose_name = 'Referral'
        verbose_name_plural = 'Referrals'
        indexes = [
            models.Index(fields=['referral_code']),
            models.Index(fields=['current_tier']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.referral_code} ({self.current_tier})"
    
    def get_commission_rate(self):
        """Get the current commission rate percentage"""
        return self.TIER_CONFIG[self.current_tier]['commission']
    
    def calculate_tier(self):
        """Calculate tier based on total referrals"""
        for tier, config in self.TIER_CONFIG.items():
            if config['min'] <= self.total_referrals <= config['max']:
                return tier
        return self.STARTER
    
    def update_tier(self):
        """Update the tier based on current referral count"""
        new_tier = self.calculate_tier()
        if new_tier != self.current_tier:
            old_tier = self.current_tier
            self.current_tier = new_tier
            self.save(update_fields=['current_tier', 'updated_at'])
            return {
                'tier_changed': True,
                'old_tier': old_tier,
                'new_tier': new_tier,
                'new_commission_rate': self.get_commission_rate()
            }
        return {'tier_changed': False}
    
    def add_referral(self):
        """Increment referral count and update tier"""
        self.total_referrals += 1
        self.save(update_fields=['total_referrals', 'updated_at'])
        return self.update_tier()
    
    def add_commission(self, amount):
        """Add commission earnings"""
        self.total_commission_earned += amount
        self.save(update_fields=['total_commission_earned', 'updated_at'])
    
    def get_next_tier_info(self):
        """Get information about the next tier"""
        tier_order = [self.STARTER, self.BRONZE, self.SILVER, self.GOLD, self.ELITE]
        current_index = tier_order.index(self.current_tier)
        
        if current_index >= len(tier_order) - 1:
            return {
                'is_max_tier': True,
                'message': 'You are at the highest tier!'
            }
        
        next_tier = tier_order[current_index + 1]
        next_config = self.TIER_CONFIG[next_tier]
        referrals_needed = next_config['min'] - self.total_referrals
        
        return {
            'is_max_tier': False,
            'next_tier': next_tier,
            'next_commission_rate': next_config['commission'],
            'referrals_needed': referrals_needed,
            'current_referrals': self.total_referrals,
            'target_referrals': next_config['min']
        }
    
    @property
    def commission_percentage(self):
        """Property to get commission rate as percentage string"""
        return f"{self.get_commission_rate()}%"


class ReferralEarning(models.Model):
    """Track individual referral earnings"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    referrer = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='referral_earnings'
    )
    referred_user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='generated_earnings'
    )
    transaction_type = models.CharField(
        max_length=50,
        help_text="Type of transaction that generated commission"
    )
    transaction_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Commission rate applied (percentage)"
    )
    commission_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Commission amount earned"
    )
    tier_at_earning = models.CharField(
        max_length=20,
        choices=Referral.TIER_CHOICES,
        help_text="Referrer's tier when commission was earned"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Referral Earning'
        verbose_name_plural = 'Referral Earnings'
        indexes = [
            models.Index(fields=['referrer', '-created_at']),
            models.Index(fields=['referred_user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.referrer.email} earned ${self.commission_earned} from {self.referred_user.email}"
    
    def save(self, *args, **kwargs):
        """Calculate commission before saving"""
        if not self.commission_earned:
            self.commission_earned = (self.transaction_amount * self.commission_rate) / 100
        super().save(*args, **kwargs)

        