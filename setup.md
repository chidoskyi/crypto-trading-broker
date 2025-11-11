# Trading Platform Backend - Technical Specification

## 1. System Architecture

### 1.1 Technology Stack
- **Framework**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL (primary), Redis (cache/queue)
- **Task Queue**: Celery with Redis broker
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **WebSocket**: Django Channels for real-time updates
- **Payment Processing**: Stripe/PayPal integration
- **KYC Provider**: Onfido/Jumio API integration

### 1.2 High-Level Architecture
```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │◄────►│  Django API  │◄────►│  Database   │
│(Web/Mobile) │      │   Gateway    │      │ PostgreSQL  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Celery    │
                     │   Workers    │
                     └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Market     │    │  Copy Trade  │    │   AI Bot     │
│   Engine     │    │   Engine     │    │   Engine     │
└──────────────┘    └──────────────┘    └──────────────┘
        │
        ▼
┌──────────────┐
│ External APIs│
│(Binance,etc) │
└──────────────┘
```

## 2. Database Models

### 2.1 User Management

```python
# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """Extended user model with trading platform features"""
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
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
    referral_code = models.CharField(max_length=10, unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class KYCDocument(models.Model):
    """Store KYC verification documents"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('passport', 'Passport'),
            ('drivers_license', 'Driver\'s License'),
            ('national_id', 'National ID')
        ]
    )
    document_number = models.CharField(max_length=100, encrypted=True)
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
```

### 2.2 Fund Management

```python
# funds/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

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
```

### 2.3 Trading System

```python
# trading/models.py
from django.db import models
from decimal import Decimal

class TradingPair(models.Model):
    """Available trading pairs"""
    symbol = models.CharField(max_length=20, unique=True)  # BTC/USD, ETH/USD
    base_currency = models.CharField(max_length=10)
    quote_currency = models.CharField(max_length=10)
    market_type = models.CharField(
        max_length=10,
        choices=[('crypto', 'Crypto'), ('forex', 'Forex')]
    )
    is_active = models.BooleanField(default=True)
    min_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    max_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    price_precision = models.IntegerField(default=2)
    quantity_precision = models.IntegerField(default=8)
    trading_fee_percentage = models.DecimalField(max_digits=5, decimal_places=4)

class Order(models.Model):
    """Trading orders"""
    ORDER_TYPES = [
        ('market', 'Market'),
        ('limit', 'Limit'),
        ('stop_loss', 'Stop Loss'),
        ('take_profit', 'Take Profit')
    ]
    
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('partially_filled', 'Partially Filled'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected')
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    filled_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0')
    )
    average_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    source = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('bot', 'AI Bot'),
            ('copy_trade', 'Copy Trade'),
            ('signal', 'Signal')
        ],
        default='manual'
    )
    source_id = models.IntegerField(null=True)  # ID of bot/trader/signal
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)

class Trade(models.Model):
    """Executed trades"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    external_trade_id = models.CharField(max_length=100, blank=True)

class Position(models.Model):
    """Open positions for users"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    side = models.CharField(max_length=4, choices=[('long', 'Long'), ('short', 'Short')])
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    leverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 2.4 Copy Trading

```python
# copy_trading/models.py
from django.db import models

class Trader(models.Model):
    """Master traders that others can copy"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    total_followers = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2)
    profit_percentage = models.DecimalField(max_digits=10, decimal_places=2)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_trades = models.IntegerField(default=0)
    risk_score = models.IntegerField(default=5)  # 1-10
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CopyTradingSubscription(models.Model):
    """User subscriptions to copy traders"""
    follower = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='following'
    )
    trader = models.ForeignKey(
        Trader,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    is_active = models.BooleanField(default=True)
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )  # % of capital to allocate
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    stop_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['follower', 'trader']

class CopiedTrade(models.Model):
    """Record of trades copied from master traders"""
    subscription = models.ForeignKey(CopyTradingSubscription, on_delete=models.CASCADE)
    master_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='master_order')
    follower_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='follower_order')
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.5 AI Trading Bots

```python
# bots/models.py
from django.db import models

class TradingBot(models.Model):
    """AI trading bot configurations"""
    STRATEGY_CHOICES = [
        ('moving_average', 'Moving Average Crossover'),
        ('rsi', 'RSI Strategy'),
        ('macd', 'MACD Strategy'),
        ('bollinger', 'Bollinger Bands'),
        ('arbitrage', 'Arbitrage'),
        ('ml_model', 'Machine Learning Model'),
        ('custom', 'Custom Strategy')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=False)
    is_paper_trading = models.BooleanField(default=True)
    
    # Risk management
    max_position_size = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    take_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Strategy parameters (JSON for flexibility)
    parameters = models.JSONField(default=dict)
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

class BotTrade(models.Model):
    """Trades executed by bots"""
    bot = models.ForeignKey(TradingBot, on_delete=models.CASCADE)
    order = models.ForeignKey('trading.Order', on_delete=models.CASCADE)
    signal_data = models.JSONField()  # Store the signal that triggered the trade
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.6 Premium Signals

```python
# signals/models.py
from django.db import models

class SignalProvider(models.Model):
    """Signal provider information"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('in_house', 'In-House'),
            ('third_party', 'Third Party')
        ]
    )
    accuracy_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_signals = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalPlan(models.Model):
    """Subscription plans for signals"""
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    max_signals_per_day = models.IntegerField()
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalSubscription(models.Model):
    """User subscriptions to signal plans"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    plan = models.ForeignKey(SignalPlan, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled')
        ],
        default='active'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

class TradingSignal(models.Model):
    """Trading signals"""
    SIGNAL_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('close', 'Close Position')
    ]
    
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    trading_pair = models.ForeignKey('trading.TradingPair', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    timeframe = models.CharField(max_length=20)  # 1h, 4h, 1d, etc.
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    analysis = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('hit_tp', 'Take Profit Hit'),
            ('hit_sl', 'Stop Loss Hit'),
            ('closed', 'Manually Closed'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class SignalNotification(models.Model):
    """Track signal notifications sent to users"""
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acted_on = models.BooleanField(default=False)
```

### 2.7 Loan Management

```python
# loans/models.py
from django.db import models
from decimal import Decimal

class LoanProduct(models.Model):
    """Available loan products"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Annual %
    term_days = models.IntegerField()
    collateral_ratio = models.DecimalField(max_digits=5, decimal_places=2)  # %
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    """User loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_days = models.IntegerField()
    collateral_amount = models.DecimalField(max_digits=20, decimal_places=2)
    collateral_currency = models.CharField(max_length=10)
    outstanding_balance = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_loans'
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    repaid_at = models.DateTimeField(null=True, blank=True)

class LoanRepayment(models.Model):
    """Loan repayment transactions"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.ForeignKey('funds.Transaction', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.8 Referral System

```python
# referrals/models.py
from django.db import models

class ReferralTier(models.Model):
    """Referral reward tiers"""
    name = models.CharField(max_length=100)
    min_referrals = models.IntegerField()
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferralReward(models.Model):
    """Track referral rewards"""
    referrer = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_rewards'
    )
    referred_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_source'
    )
    reward_type = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'Signup Bonus'),
            ('first_deposit', 'First Deposit Bonus'),
            ('trading_commission', 'Trading Commission')
        ]
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    transaction = models.ForeignKey(
        'funds.Transaction',
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

## 3. API Endpoints

### 3.1 Authentication
```
POST   /api/v1/auth/register/          - User registration
POST   /api/v1/auth/login/             - User login
POST   /api/v1/auth/logout/            - User logout
POST   /api/v1/auth/refresh/           - Refresh JWT token
POST   /api/v1/auth/password-reset/    - Request password reset
POST   /api/v1/auth/password-reset-confirm/ - Confirm password reset
GET    /api/v1/auth/me/                - Get current user
PATCH  /api/v1/auth/me/                - Update current user
```

### 3.2 KYC
```
POST   /api/v1/kyc/submit/             - Submit KYC documents
GET    /api/v1/kyc/status/             - Get KYC status
GET    /api/v1/kyc/pending/            - List pending KYC (admin)
POST   /api/v1/kyc/{id}/approve/       - Approve KYC (admin)
POST   /api/v1/kyc/{id}/reject/        - Reject KYC (admin)
```

### 3.3 Funds
```
GET    /api/v1/wallets/                - List user wallets
GET    /api/v1/wallets/{currency}/     - Get specific wallet
POST   /api/v1/deposits/               - Create deposit
GET    /api/v1/deposits/               - List deposits
POST   /api/v1/withdrawals/            - Request withdrawal
GET    /api/v1/withdrawals/            - List withdrawals
POST   /api/v1/transfers/              - Internal transfer
GET    /api/v1/transactions/           - Transaction history
```

### 3.4 Trading
```
GET    /api/v1/trading-pairs/          - List trading pairs
GET    /api/v1/market-data/{symbol}/   - Get market data
POST   /api/v1/orders/                 - Create order
GET    /api/v1/orders/                 - List orders
GET    /api/v1/orders/{id}/            - Get order details
DELETE /api/v1/orders/{id}/            - Cancel order
GET    /api/v1/trades/                 - Trade history
GET    /api/v1/positions/              - Open positions
POST   /api/v1/positions/{id}/close/   - Close position
```

### 3.5 Copy Trading
```
GET    /api/v1/traders/                - List master traders
GET    /api/v1/traders/{id}/           - Trader details
POST   /api/v1/copy-trading/subscribe/ - Subscribe to trader
DELETE /api/v1/copy-trading/subscribe/{id}/ - Unsubscribe
GET    /api/v1/copy-trading/subscriptions/ - My subscriptions
PATCH  /api/v1/copy-trading/subscriptions/{id}/ - Update subscription
GET    /api/v1/copy-trading/performance/ - Copy trading performance
```

### 3.6 AI Bots
```
GET    /api/v1/bots/                   - List bots
POST   /api/v1/bots/                   - Create bot
GET    /api/v1/bots/{id}/              - Bot details
PATCH  /api/v1/bots/{id}/              - Update bot
DELETE /api/v1/bots/{id}/              - Delete bot
POST   /api/v1/bots/{id}/start/        - Start bot
POST   /api/v1/bots/{id}/stop/         - Stop bot
GET    /api/v1/bots/{id}/performance/  - Bot performance
GET    /api/v1/bot-strategies/         - Available strategie


# Trading Platform Backend - Technical Specification

## 1. System Architecture

### 1.1 Technology Stack
- **Framework**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL (primary), Redis (cache/queue)
- **Task Queue**: Celery with Redis broker
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **WebSocket**: Django Channels for real-time updates
- **Payment Processing**: Stripe/PayPal integration
- **KYC Provider**: Onfido/Jumio API integration

### 1.2 High-Level Architecture
```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │◄────►│  Django API  │◄────►│  Database   │
│(Web/Mobile) │      │   Gateway    │      │ PostgreSQL  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Celery    │
                     │   Workers    │
                     └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Market     │    │  Copy Trade  │    │   AI Bot     │
│   Engine     │    │   Engine     │    │   Engine     │
└──────────────┘    └──────────────┘    └──────────────┘
        │
        ▼
┌──────────────┐
│ External APIs│
│(Binance,etc) │
└──────────────┘
```

## 2. Database Models

### 2.1 User Management

```python
# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """Extended user model with trading platform features"""
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
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
    referral_code = models.CharField(max_length=10, unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class KYCDocument(models.Model):
    """Store KYC verification documents"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('passport', 'Passport'),
            ('drivers_license', 'Driver\'s License'),
            ('national_id', 'National ID')
        ]
    )
    document_number = models.CharField(max_length=100, encrypted=True)
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
```

### 2.2 Fund Management

```python
# funds/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

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
```

### 2.3 Trading System

```python
# trading/models.py
from django.db import models
from decimal import Decimal

class TradingPair(models.Model):
    """Available trading pairs"""
    symbol = models.CharField(max_length=20, unique=True)  # BTC/USD, ETH/USD
    base_currency = models.CharField(max_length=10)
    quote_currency = models.CharField(max_length=10)
    market_type = models.CharField(
        max_length=10,
        choices=[('crypto', 'Crypto'), ('forex', 'Forex')]
    )
    is_active = models.BooleanField(default=True)
    min_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    max_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    price_precision = models.IntegerField(default=2)
    quantity_precision = models.IntegerField(default=8)
    trading_fee_percentage = models.DecimalField(max_digits=5, decimal_places=4)

class Order(models.Model):
    """Trading orders"""
    ORDER_TYPES = [
        ('market', 'Market'),
        ('limit', 'Limit'),
        ('stop_loss', 'Stop Loss'),
        ('take_profit', 'Take Profit')
    ]
    
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('partially_filled', 'Partially Filled'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected')
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    filled_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0')
    )
    average_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    source = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('bot', 'AI Bot'),
            ('copy_trade', 'Copy Trade'),
            ('signal', 'Signal')
        ],
        default='manual'
    )
    source_id = models.IntegerField(null=True)  # ID of bot/trader/signal
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)

class Trade(models.Model):
    """Executed trades"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    external_trade_id = models.CharField(max_length=100, blank=True)

class Position(models.Model):
    """Open positions for users"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    side = models.CharField(max_length=4, choices=[('long', 'Long'), ('short', 'Short')])
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    leverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 2.4 Copy Trading

```python
# copy_trading/models.py
from django.db import models

class Trader(models.Model):
    """Master traders that others can copy"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    total_followers = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2)
    profit_percentage = models.DecimalField(max_digits=10, decimal_places=2)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_trades = models.IntegerField(default=0)
    risk_score = models.IntegerField(default=5)  # 1-10
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CopyTradingSubscription(models.Model):
    """User subscriptions to copy traders"""
    follower = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='following'
    )
    trader = models.ForeignKey(
        Trader,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    is_active = models.BooleanField(default=True)
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )  # % of capital to allocate
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    stop_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['follower', 'trader']

class CopiedTrade(models.Model):
    """Record of trades copied from master traders"""
    subscription = models.ForeignKey(CopyTradingSubscription, on_delete=models.CASCADE)
    master_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='master_order')
    follower_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='follower_order')
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.5 AI Trading Bots

```python
# bots/models.py
from django.db import models

class TradingBot(models.Model):
    """AI trading bot configurations"""
    STRATEGY_CHOICES = [
        ('moving_average', 'Moving Average Crossover'),
        ('rsi', 'RSI Strategy'),
        ('macd', 'MACD Strategy'),
        ('bollinger', 'Bollinger Bands'),
        ('arbitrage', 'Arbitrage'),
        ('ml_model', 'Machine Learning Model'),
        ('custom', 'Custom Strategy')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=False)
    is_paper_trading = models.BooleanField(default=True)
    
    # Risk management
    max_position_size = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    take_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Strategy parameters (JSON for flexibility)
    parameters = models.JSONField(default=dict)
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

class BotTrade(models.Model):
    """Trades executed by bots"""
    bot = models.ForeignKey(TradingBot, on_delete=models.CASCADE)
    order = models.ForeignKey('trading.Order', on_delete=models.CASCADE)
    signal_data = models.JSONField()  # Store the signal that triggered the trade
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.6 Premium Signals

```python
# signals/models.py
from django.db import models

class SignalProvider(models.Model):
    """Signal provider information"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('in_house', 'In-House'),
            ('third_party', 'Third Party')
        ]
    )
    accuracy_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_signals = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalPlan(models.Model):
    """Subscription plans for signals"""
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    max_signals_per_day = models.IntegerField()
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalSubscription(models.Model):
    """User subscriptions to signal plans"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    plan = models.ForeignKey(SignalPlan, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled')
        ],
        default='active'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

class TradingSignal(models.Model):
    """Trading signals"""
    SIGNAL_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('close', 'Close Position')
    ]
    
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    trading_pair = models.ForeignKey('trading.TradingPair', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    timeframe = models.CharField(max_length=20)  # 1h, 4h, 1d, etc.
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    analysis = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('hit_tp', 'Take Profit Hit'),
            ('hit_sl', 'Stop Loss Hit'),
            ('closed', 'Manually Closed'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class SignalNotification(models.Model):
    """Track signal notifications sent to users"""
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acted_on = models.BooleanField(default=False)
```

### 2.7 Loan Management

```python
# loans/models.py
from django.db import models
from decimal import Decimal

class LoanProduct(models.Model):
    """Available loan products"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Annual %
    term_days = models.IntegerField()
    collateral_ratio = models.DecimalField(max_digits=5, decimal_places=2)  # %
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    """User loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_days = models.IntegerField()
    collateral_amount = models.DecimalField(max_digits=20, decimal_places=2)
    collateral_currency = models.CharField(max_length=10)
    outstanding_balance = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_loans'
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    repaid_at = models.DateTimeField(null=True, blank=True)

class LoanRepayment(models.Model):
    """Loan repayment transactions"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.ForeignKey('funds.Transaction', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.8 Referral System

```python
# referrals/models.py
from django.db import models

class ReferralTier(models.Model):
    """Referral reward tiers"""
    name = models.CharField(max_length=100)
    min_referrals = models.IntegerField()
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferralReward(models.Model):
    """Track referral rewards"""
    referrer = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_rewards'
    )
    referred_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_source'
    )
    reward_type = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'Signup Bonus'),
            ('first_deposit', 'First Deposit Bonus'),
            ('trading_commission', 'Trading Commission')
        ]
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    transaction = models.ForeignKey(
        'funds.Transaction',
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

## 3. API Endpoints

### 3.1 Authentication
```
POST   /api/v1/auth/register/          - User registration
POST   /api/v1/auth/login/             - User login
POST   /api/v1/auth/logout/            - User logout
POST   /api/v1/auth/refresh/           - Refresh JWT token
POST   /api/v1/auth/password-reset/    - Request password reset
POST   /api/v1/auth/password-reset-confirm/ - Confirm password reset
GET    /api/v1/auth/me/                - Get current user
PATCH  /api/v1/auth/me/                - Update current user
```

### 3.2 KYC
```
POST   /api/v1/kyc/submit/             - Submit KYC documents
GET    /api/v1/kyc/status/             - Get KYC status
GET    /api/v1/kyc/pending/            - List pending KYC (admin)
POST   /api/v1/kyc/{id}/approve/       - Approve KYC (admin)
POST   /api/v1/kyc/{id}/reject/        - Reject KYC (admin)
```

### 3.3 Funds
```
GET    /api/v1/wallets/                - List user wallets
GET    /api/v1/wallets/{currency}/     - Get specific wallet
POST   /api/v1/deposits/               - Create deposit
GET    /api/v1/deposits/               - List deposits
POST   /api/v1/withdrawals/            - Request withdrawal
GET    /api/v1/withdrawals/            - List withdrawals
POST   /api/v1/transfers/              - Internal transfer
GET    /api/v1/transactions/           - Transaction history
```

### 3.4 Trading
```
GET    /api/v1/trading-pairs/          - List trading pairs
GET    /api/v1/market-data/{symbol}/   - Get market data
POST   /api/v1/orders/                 - Create order
GET    /api/v1/orders/                 - List orders
GET    /api/v1/orders/{id}/            - Get order details
DELETE /api/v1/orders/{id}/            - Cancel order
GET    /api/v1/trades/                 - Trade history
GET    /api/v1/positions/              - Open positions
POST   /api/v1/positions/{id}/close/   - Close position
```

### 3.5 Copy Trading
```
GET    /api/v1/traders/                - List master traders
GET    /api/v1/traders/{id}/           - Trader details
POST   /api/v1/copy-trading/subscribe/ - Subscribe to trader
DELETE /api/v1/copy-trading/subscribe/{id}/ - Unsubscribe
GET    /api/v1/copy-trading/subscriptions/ - My subscriptions
PATCH  /api/v1/copy-trading/subscriptions/{id}/ - Update subscription
GET    /api/v1/copy-trading/performance/ - Copy trading performance
```

### 3.6 AI Bots
```
GET    /api/v1/bots/                   - List bots
POST   /api/v1/bots/                   - Create bot
GET    /api/v1/bots/{id}/              - Bot details
PATCH  /api/v1/bots/{id}/              - Update bot
DELETE /api/v1/bots/{id}/              - Delete bot
POST   /api/v1/bots/{id}/start/        - Start bot
POST   /api/v1/bots/{id}/stop/         - Stop bot
GET    /api/v1/bots/{id}/performance/  - Bot performance
GET    /api/v1/bot-strategies/         - Available strategies
```

### 3.7 Signals
```
GET    /api/v1/signal-providers/       - List providers
GET    /api/v1/signal-plans/           - Available plans
POST   /api/v1/signal-subscriptions/   - Subscribe to plan
GET    /api/v1/signal-subscriptions/   - My subscriptions
DELETE /api/v1/signal-subscriptions/{id}/ - Cancel subscription
GET    /api/v1/signals/                - My signals
GET    /api/v1/signals/{id}/           - Signal details
POST   /api/v1/signals/{id}/execute/   - Execute signal
```

### 3.8 Loans
```
GET    /api/v1/loan-products/          - Available products
POST   /api/v1/loans/                  - Apply for loan
GET    /api/v1/loans/                  - My loans
GET    /api/v1/loans/{id}/             - Loan details
POST   /api/v1/loans/{id}/repay/       - Make repayment
GET    /api/v1/loans/pending/          - Pending loans (admin)
POST   /api/v1/loans/{id}/approve/     - Approve loan (admin)
POST   /api/v1/loans/{id}/reject/      - Reject loan (admin)
```

### 3.9 Referrals
```
GET    /api/v1/referrals/code/         - Get referral code
GET    /api/v1/referrals/stats/        - Referral statistics
GET    /api/v1/referrals/rewards/      - Referral rewards
GET    /api/v1/referrals/referred-users/ - List referred users
```

## 4. Implementation Details

### 4.1 Market Data Integration

```python
# trading/services/market_service.py
import ccxt
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

class MarketDataService:
    """Service for fetching real-time market data"""
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET_KEY,
            'enableRateLimit': True,
        })
    
    def get_ticker(self, symbol):
        """Get current ticker data"""
        cache_key = f'ticker:{symbol}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        ticker = self.exchange.fetch_ticker(symbol)
        data = {
            'symbol': symbol,
            'last_price': Decimal(str(ticker['last'])),
            'bid': Decimal(str(ticker['bid'])),
            'ask': Decimal(str(ticker['ask'])),
            'volume': Decimal(str(ticker['volume'])),
            'change_24h': Decimal(str(ticker['percentage'])),
            'high_24h': Decimal(str(ticker['high'])),
            'low_24h': Decimal(str(ticker['low'])),
        }
        
        cache.set(cache_key, data, timeout=5)  # 5 seconds cache
        return data
    
    def get_orderbook(self, symbol, limit=20):
        """Get order book"""
        orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
        return {
            'bids': orderbook['bids'],
            'asks': orderbook['asks'],
        }
    
    def get_historical_data(self, symbol, timeframe='1h', limit=100):
        """Get historical OHLCV data"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [{
            'timestamp': candle[0],
            'open': Decimal(str(candle[1])),
            'high': Decimal(str(candle[2])),
            'low': Decimal(str(candle[3])),
            'close': Decimal(str(candle[4])),
            'volume': Decimal(str(candle[5])),
        } for candle in ohlcv]
```

### 4.2 Order Execution Engine

```python
# trading/services/order_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from trading.models import Order, Trade, Position
from funds.models import Wallet, Transaction
from trading.services.market_service import MarketDataService

class OrderExecutionService:
    """Handle order execution and position management"""
    
    def __init__(self):
        self.market_service = MarketDataService()
    
    @transaction.atomic
    def create_order(self, user, order_data):
        """Create and validate a new order"""
        trading_pair = order_data['trading_pair']
        side = order_data['side']
        quantity = Decimal(str(order_data['quantity']))
        
        # Validate user has sufficient balance
        if side == 'buy':
            required_balance = self._calculate_required_balance(
                trading_pair, quantity, order_data.get('price')
            )
            wallet = Wallet.objects.get(
                user=user,
                currency=trading_pair.quote_currency
            )
            if wallet.balance < required_balance:
                raise ValueError("Insufficient balance")
            
            # Lock the funds
            wallet.balance -= required_balance
            wallet.locked_balance += required_balance
            wallet.save()
        else:  # sell
            # Check if user has the asset
            wallet = Wallet.objects.get(
                user=user,
                currency=trading_pair.base_currency
            )
            if wallet.balance < quantity:
                raise ValueError("Insufficient asset balance")
            
            wallet.balance -= quantity
            wallet.locked_balance += quantity
            wallet.save()
        
        # Create the order
        order = Order.objects.create(
            user=user,
            **order_data,
            status='open'
        )
        
        # Execute market orders immediately
        if order.order_type == 'market':
            self._execute_market_order(order)
        
        return order
    
    def _execute_market_order(self, order):
        """Execute a market order"""
        ticker = self.market_service.get_ticker(
            order.trading_pair.symbol
        )
        
        execution_price = ticker['ask'] if order.side == 'buy' else ticker['bid']
        fee = self._calculate_fee(order, execution_price)
        
        # Create trade record
        trade = Trade.objects.create(
            order=order,
            quantity=order.quantity,
            price=execution_price,
            fee=fee,
            executed_at=timezone.now()
        )
        
        # Update order status
        order.filled_quantity = order.quantity
        order.average_price = execution_price
        order.fee = fee
        order.status = 'filled'
        order.executed_at = timezone.now()
        order.save()
        
        # Update user wallets
        self._settle_trade(order, trade)
        
        # Update or create position
        self._update_position(order)
    
    @transaction.atomic
    def _settle_trade(self, order, trade):
        """Settle the trade in user wallets"""
        user = order.user
        trading_pair = order.trading_pair
        
        if order.side == 'buy':
            # Unlock quote currency
            quote_wallet = Wallet.objects.select_for_update().get(
                user=user,
                currency=trading_pair.quote_currency
            )
            cost = trade.quantity * trade.price + trade.fee
            quote_wallet.locked_balance -= cost
            quote_wallet.save()
            
            # Add base currency
            base_wallet, _ = Wallet.objects.get_or_create(
                user=user,
                currency=trading_pair.base_currency
            )
            base_wallet.balance += trade.quantity
            base_wallet.save()
        else:  # sell
            # Unlock base currency
            base_wallet = Wallet.objects.select_for_update().get(
                user=user,
                currency=trading_pair.base_currency
            )
            base_wallet.locked_balance -= trade.quantity
            base_wallet.save()
            
            # Add quote currency
            quote_wallet, _ = Wallet.objects.get_or_create(
                user=user,
                currency=trading_pair.quote_currency
            )
            proceeds = trade.quantity * trade.price - trade.fee
            quote_wallet.balance += proceeds
            quote_wallet.save()
        
        # Create transaction record
        Transaction.objects.create(
            user=user,
            transaction_type='trade',
            currency=trading_pair.quote_currency,
            amount=trade.quantity * trade.price,
            fee=trade.fee,
            status='completed',
            reference_id=f'TRADE-{trade.id}',
            completed_at=timezone.now()
        )
    
    def _calculate_fee(self, order, price):
        """Calculate trading fee"""
        trading_pair = order.trading_pair
        return (order.quantity * price * 
                trading_pair.trading_fee_percentage / 100)
    
    def _calculate_required_balance(self, trading_pair, quantity, price=None):
        """Calculate required balance for an order"""
        if price is None:
            ticker = self.market_service.get_ticker(trading_pair.symbol)
            price = ticker['ask']
        
        cost = quantity * price
        fee = cost * trading_pair.trading_fee_percentage / 100
        return cost + fee
    
    def _update_position(self, order):
        """Update or create position after trade execution"""
        # Implementation for position tracking
        pass
```

### 4.3 Copy Trading Engine

```python
# copy_trading/services/copy_service.py
from decimal import Decimal
from django.db import transaction
from copy_trading.models import CopyTradingSubscription, CopiedTrade
from trading.services.order_service import OrderExecutionService

class CopyTradingService:
    """Service for executing copy trades"""
    
    def __init__(self):
        self.order_service = OrderExecutionService()
    
    def replicate_trade(self, master_order):
        """Replicate a master trader's order to all followers"""
        trader = master_order.user.trader
        
        # Get active subscribers
        subscriptions = CopyTradingSubscription.objects.filter(
            trader=trader,
            is_active=True
        ).select_related('follower')
        
        for subscription in subscriptions:
            try:
                self._copy_order_for_follower(master_order, subscription)
            except Exception as e:
                # Log error but continue with other followers
                print(f"Error copying trade for {subscription.follower}: {e}")
    
    @transaction.atomic
    def _copy_order_for_follower(self, master_order, subscription):
        """Copy an order for a specific follower"""
        follower = subscription.follower
        
        # Calculate position size based on follower's settings
        follower_quantity = self._calculate_follower_quantity(
            master_order,
            subscription
        )
        
        if follower_quantity <= 0:
            return
        
        # Create order data
        order_data = {
            'trading_pair': master_order.trading_pair,
            'order_type': master_order.order_type,
            'side': master_order.side,
            'quantity': follower_quantity,
            'price': master_order.price,
            'stop_price': master_order.stop_price,
            'source': 'copy_trade',
            'source_id': master_order.id
        }
        
        # Execute the order
        follower_order = self.order_service.create_order(
            follower,
            order_data
        )
        
        # Record the copied trade
        CopiedTrade.objects.create(
            subscription=subscription,
            master_order=master_order,
            follower_order=follower_order
        )
    
    def _calculate_follower_quantity(self, master_order, subscription):
        """Calculate appropriate quantity for follower"""
        # Get follower's available balance
        follower_wallet = subscription.follower.wallet_set.get(
            currency=master_order.trading_pair.quote_currency
        )
        
        # Calculate based on copy percentage
        max_allocation = (follower_wallet.balance * 
                         subscription.copy_percentage / 100)
        
        # Apply max position size if set
        if subscription.max_position_size:
            max_allocation = min(max_allocation, 
                               subscription.max_position_size)
        
        # Calculate quantity
        if master_order.price:
            quantity = max_allocation / master_order.price
        else:
            # Use current market price for market orders
            ticker = self.order_service.market_service.get_ticker(
                master_order.trading_pair.symbol
            )
            quantity = max_allocation / ticker['ask']
        
        return quantity
```

### 4.4 AI Bot Engine

```python
# bots/services/bot_engine.py
import numpy as np
import pandas as pd
from decimal import Decimal
from django.utils import timezone
from bots.models import TradingBot, BotTrade
from trading.services.order_service import OrderExecutionService
from trading.services.market_service import MarketDataService

class BotEngine:
    """Execute trading bot strategies"""
    
    def __init__(self, bot):
        self.bot = bot
        self.market_service = MarketDataService()
        self.order_service = OrderExecutionService()
    
    def run(self):
        """Execute bot trading logic"""
        if not self.bot.is_active:
            return
        
        # Check daily loss limit
        if self._check_daily_loss_limit():
            self.bot.is_active = False
            self.bot.save()
            return
        
        # Run strategy for each trading pair
        for trading_pair in self.bot.trading_pairs.all():
            try:
                signal = self._generate_signal(trading_pair)
                if signal:
                    self._execute_signal(signal, trading_pair)
            except Exception as e:
                print(f"Error running bot {self.bot.id}: {e}")
        
        self.bot.last_run_at = timezone.now()
        self.bot.save()
    
    def _generate_signal(self, trading_pair):
        """Generate trading signal based on strategy"""
        if self.bot.strategy == 'moving_average':
            return self._moving_average_strategy(trading_pair)
        elif self.bot.strategy == 'rsi':
            return self._rsi_strategy(trading_pair)
        elif self.bot.strategy == 'macd':
            return self._macd_strategy(trading_pair)
        # Add more strategies...
        return None
    
    def _moving_average_strategy(self, trading_pair):
        """Moving Average Crossover Strategy"""
        params = self.bot.parameters
        short_period = params.get('short_period', 20)
        long_period = params.get('long_period', 50)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=long_period + 10
        )
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(historical_data)
        
        # Calculate moving averages
        df['sma_short'] = df['close'].rolling(window=short_period).mean()
        df['sma_long'] = df['close'].rolling(window=long_period).mean()
        
        # Get last two rows to detect crossover
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish crossover
        if (previous['sma_short'] <= previous['sma_long'] and 
            current['sma_short'] > current['sma_long']):
            return {
                'action': 'buy',
                'price': current['close'],
                'reason': 'MA Bullish Crossover'
            }
        
        # Bearish crossover
        elif (previous['sma_short'] >= previous['sma_long'] and 
              current['sma_short'] < current['sma_long']):
            return {
                'action': 'sell',
                'price': current['close'],
                'reason': 'MA Bearish Crossover'
            }
        
        return None
    
    def _rsi_strategy(self, trading_pair):
        """RSI Strategy"""
        params = self.bot.parameters
        period = params.get('rsi_period', 14)
        oversold = params.get('oversold_level', 30)
        overbought = params.get('overbought_level', 70)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=period + 10
        )
        
        df = pd.DataFrame(historical_data)
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Buy signal
        if current_rsi < oversold:
            return {
                'action': 'buy',
                'price': current_price,
                'reason': f'RSI Oversold: {current_rsi:.2f}'
            }
        
        # Sell signal
        elif current_rsi > overbought:
            return {
                'action': 'sell',
                'price': current_price,
                'reason': f'RSI Overbought: {current_rsi:.2f}'
            }
        
        return None
    
    def _execute_signal(self, signal, trading_pair):
        """Execute trading signal"""
        # Calculate position size
        quantity = self._calculate_position_size(trading_pair, signal['price'])
        
        if quantity <= 0:
            return
        
        # Create order
        order_data = {
            'trading_pair': trading_pair,
            'order_type': 'market',
            'side': signal['action'],
            'quantity': quantity,
            'source': 'bot',
            'source_id': self.bot.id
        }
        
        # Add stop loss and take profit
        if signal['action'] == 'buy':
            order_data['stop_price'] = (
                signal['price'] * (1 - self.bot.stop_loss_percentage / 100)
            )
        
        try:
            order = self.order_service.create_order(
                self.bot.user,
                order_data
            )
            
            # Record bot trade
            BotTrade.objects.create(
                bot=self.bot,
                order=order,
                signal_data=signal
            )
            
            # Update bot statistics
            self.bot.total_trades += 1
            self.bot.save()
            
        except Exception as e:
            print(f"Error executing bot signal: {e}")
    
    def _calculate_position_size(self, trading_pair, price):
        """Calculate position size based on risk management"""
        wallet = self.bot.user.wallet_set.get(
            currency=trading_pair.quote_currency
        )
        
        # Use configured max position size
        max_allocation = min(
            wallet.balance * Decimal('0.1'),  # Max 10% per trade
            self.bot.max_position_size
        )
        
        return max_allocation / Decimal(str(price))
    
    def _check_daily_loss_limit(self):
        """Check if daily loss limit exceeded"""
        today = timezone.now().date()
        
        # Calculate today's P&L
        today_trades = BotTrade.objects.filter(
            bot=self.bot,
            created_at__date=today
        ).select_related('order')
        
        total_pnl = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.order.price)
            for trade in today_trades
            if trade.order.status == 'filled'
        )
        
        return total_pnl < -self.bot.max_daily_loss
```

### 4.5 Signal Notification System

```python
# signals/services/notification_service.py
from django.core.mail import send_mail
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from signals.models import SignalNotification, SignalSubscription

class SignalNotificationService:
    """Send trading signals to subscribed users"""
    
    def notify_subscribers(self, signal):
        """Send signal to all active subscribers"""
        # Get active subscriptions for this provider
        subscriptions = SignalSubscription.objects.filter(
            plan__provider=signal.provider,
            status='active',
            expires_at__gt=timezone.now()
        ).select_related('user')
        
        for subscription in subscriptions:
            # Check if signal's trading pair is in plan
            if signal.trading_pair in subscription.plan.trading_pairs.all():
                self._send_notification(subscription.user, signal)
    
    def _send_notification(self, user, signal):
        """Send notification to a specific user"""
        # Create notification record
        notification = SignalNotification.objects.create(
            signal=signal,
            user=user
        )
        
        # Send via WebSocket
        self._send_websocket(user, signal)
        
        # Send email if user has email notifications enabled
        if user.profile.email_notifications:
            self._send_email(user, signal)
        
        # Send push notification if mobile app
        if user.profile.push_notifications:
            self._send_push(user, signal)
    
    def _send_websocket(self, user, signal):
        """Send real-time WebSocket notification"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}',
            {
                'type': 'trading_signal',
                'signal': {
                    'id': signal.id,
                    'trading_pair': signal.trading_pair.symbol,
                    'type': signal.signal_type,
                    'entry_price': str(signal.entry_price),
                    'stop_loss': str(signal.stop_loss),
                    'take_profit': str(signal.take_profit),
                    'confidence': str(signal.confidence),
                    'analysis': signal.analysis
                }
            }
        )
    
    def _send_email(self, user, signal):
        """Send email notification"""
        subject = f'New Trading Signal: {signal.trading_pair.symbol}'
        message = f"""
        New {signal.signal_type.upper()} signal for {signal.trading_pair.symbol}
        
        Entry Price: {signal.entry_price}
        Stop Loss: {signal.stop_loss}
        Take Profit: {signal.take_profit}
        Confidence: {signal.confidence}%
        
        Analysis:
        {signal.analysis}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )
```

### 4.6 Celery Tasks

```python
# tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def update_market_prices():
    """Update market prices for all active trading pairs"""
    from trading.models import TradingPair
    from trading.services.market_service import MarketDataService
    
    market_service = MarketDataService()
    active_pairs = TradingPair.objects.filter(is_active=True)
    
    for pair in active_pairs:
        try:
            ticker = market_service.get_ticker(pair.symbol)
            # Update cached prices or database as needed
        except Exception as e:
            print(f"Error updating {pair.symbol}: {e}")

@shared_task
def execute_pending_orders():
    """Check and execute pending limit orders"""
    from trading.models import Order
    from trading.services.order_service import OrderExecutionService
    
    order_service = OrderExecutionService()
    pending_orders = Order.objects.filter(
        status='open',
        order_type__in=['limit', 'stop_loss', 'take_profit']
    )
    
    for order in pending_orders:
        try:
            order_service.check_and_execute_order(order)
        except Exception as e:
            print(f"Error executing order {order.id}: {e}")

@shared_task
def run_trading_bots():
    """Execute all active trading bots"""
    from bots.models import TradingBot
    from bots.services.bot_engine import BotEngine
    
    active_bots = TradingBot.objects.filter(
        is_active=True,
        is_paper_trading=False
    )
    
    for bot in active_bots:
        try:
            engine = BotEngine(bot)
            engine.run()
        except Exception as e:
            print(f"Error running bot {bot.id}: {e}")

@shared_task
def process_copy_trades():
    """Process copy trading orders"""
    from trading.models import Order
    from copy_trading.services.copy_service import CopyTradingService
    
    copy_service = CopyTradingService()
    
    # Get recently filled orders from master traders
    recent_orders = Order.objects.filter(
        status='filled',
        user__trader__isnull=False,
        executed_at__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(
        source='copy_trade'  # Don't copy already copied trades
    )
    
    for order in recent_orders:
        copy_service.replicate_trade(order)

@shared_task
def calculate_loan_interest():
    """Calculate and apply interest to active loans"""
    from loans.models import Loan
    from decimal import Decimal
    
    active_loans = Loan.objects.filter(status='active')
    
    for loan in active_loans:
        # Calculate daily interest
        daily_rate = loan.interest_rate / 365 / 100
        interest = loan.outstanding_balance * Decimal(str(daily_rate))
        
        loan.outstanding_balance += interest
        loan.save()

@shared_task
def process_referral_rewards():
    """Process referral rewards for completed actions"""
    from referrals.models import ReferralReward
    from funds.models import Transaction, Wallet
    
    # Process pending rewards
    pending_rewards = ReferralReward.objects.filter(
        transaction__isnull=True
    )
    
    for reward in pending_rewards:
        try:
            # Credit wallet
            wallet, _ = Wallet.objects.get_or_create(
                user=reward.referrer,
                currency=reward.currency
            )
            wallet.balance += reward.amount
            wallet.save()
            
            # Create transaction
            transaction = Transaction.objects.create(
                user=reward.referrer,
                transaction_type='referral_bonus',
                currency=reward.currency,
                amount=reward.amount,
                status='completed',
                reference_id=f'REF-{reward.id}',
                completed_at=timezone.now()
            )
            
            reward.transaction = transaction
            reward.save()
        except Exception as e:
            print(f"Error processing reward {reward.id}: {e}")

@shared_task
def check_kyc_expiry():
    """Check for expired KYC documents"""
    from users.models import User, KYCDocument
    from datetime import timedelta
    
    # KYC documents older than 2 years need reverification
    expiry_date = timezone.now() - timedelta(days=730)
    
    expired_kyc = KYCDocument.objects.filter(
        submitted_at__lt=expiry_date,
        user__kyc_status='approved'
    )
    
    for kyc in expired_kyc:
        kyc.user.kyc_status = 'not_submitted'
        kyc.user.save()
        # Send notification to user
```

## 5. API Views

### 5.1 Trading Views

```python
# trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from trading.models import Order, TradingPair, Position
from trading.serializers import (
    OrderSerializer, TradingPairSerializer, PositionSerializer
)
from trading.services.order_service import OrderExecutionService

class TradingPairViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading pairs endpoints"""
    queryset = TradingPair.objects.filter(is_active=True)
    serializer_class = TradingPairSerializer
    
    @action(detail=True, methods=['get'])
    def market_data(self, request, pk=None):
        """Get real-time market data"""
        trading_pair = self.get_object()
        market_service = MarketDataService()
        
        data = market_service.get_ticker(trading_pair.symbol)
        return Response(data)

class OrderViewSet(viewsets.ModelViewSet):
    """Order management endpoints"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Create a new order"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_service = OrderExecutionService()
        
        try:
            order = order_service.create_order(
                request.user,
                serializer.validated_data
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an open order"""
        order = self.get_object()
        
        if order.status not in ['open', 'partially_filled']:
            return Response(
                {'error': 'Order cannot be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        # Unlock funds
        # Implementation here...
        
        return Response(OrderSerializer(order).data)

class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """Position management endpoints"""
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Position.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):


# Trading Platform Backend - Technical Specification

## 1. System Architecture

### 1.1 Technology Stack
- **Framework**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL (primary), Redis (cache/queue)
- **Task Queue**: Celery with Redis broker
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **WebSocket**: Django Channels for real-time updates
- **Payment Processing**: Stripe/PayPal integration
- **KYC Provider**: Onfido/Jumio API integration

### 1.2 High-Level Architecture
```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │◄────►│  Django API  │◄────►│  Database   │
│(Web/Mobile) │      │   Gateway    │      │ PostgreSQL  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Celery    │
                     │   Workers    │
                     └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Market     │    │  Copy Trade  │    │   AI Bot     │
│   Engine     │    │   Engine     │    │   Engine     │
└──────────────┘    └──────────────┘    └──────────────┘
        │
        ▼
┌──────────────┐
│ External APIs│
│(Binance,etc) │
└──────────────┘
```

## 2. Database Models

### 2.1 User Management

```python
# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """Extended user model with trading platform features"""
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
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
    referral_code = models.CharField(max_length=10, unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class KYCDocument(models.Model):
    """Store KYC verification documents"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('passport', 'Passport'),
            ('drivers_license', 'Driver\'s License'),
            ('national_id', 'National ID')
        ]
    )
    document_number = models.CharField(max_length=100, encrypted=True)
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
```

### 2.2 Fund Management

```python
# funds/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

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
```

### 2.3 Trading System

```python
# trading/models.py
from django.db import models
from decimal import Decimal

class TradingPair(models.Model):
    """Available trading pairs"""
    symbol = models.CharField(max_length=20, unique=True)  # BTC/USD, ETH/USD
    base_currency = models.CharField(max_length=10)
    quote_currency = models.CharField(max_length=10)
    market_type = models.CharField(
        max_length=10,
        choices=[('crypto', 'Crypto'), ('forex', 'Forex')]
    )
    is_active = models.BooleanField(default=True)
    min_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    max_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    price_precision = models.IntegerField(default=2)
    quantity_precision = models.IntegerField(default=8)
    trading_fee_percentage = models.DecimalField(max_digits=5, decimal_places=4)

class Order(models.Model):
    """Trading orders"""
    ORDER_TYPES = [
        ('market', 'Market'),
        ('limit', 'Limit'),
        ('stop_loss', 'Stop Loss'),
        ('take_profit', 'Take Profit')
    ]
    
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('partially_filled', 'Partially Filled'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected')
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    filled_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0')
    )
    average_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    source = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('bot', 'AI Bot'),
            ('copy_trade', 'Copy Trade'),
            ('signal', 'Signal')
        ],
        default='manual'
    )
    source_id = models.IntegerField(null=True)  # ID of bot/trader/signal
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)

class Trade(models.Model):
    """Executed trades"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    external_trade_id = models.CharField(max_length=100, blank=True)

class Position(models.Model):
    """Open positions for users"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    side = models.CharField(max_length=4, choices=[('long', 'Long'), ('short', 'Short')])
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    leverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 2.4 Copy Trading

```python
# copy_trading/models.py
from django.db import models

class Trader(models.Model):
    """Master traders that others can copy"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    total_followers = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2)
    profit_percentage = models.DecimalField(max_digits=10, decimal_places=2)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_trades = models.IntegerField(default=0)
    risk_score = models.IntegerField(default=5)  # 1-10
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CopyTradingSubscription(models.Model):
    """User subscriptions to copy traders"""
    follower = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='following'
    )
    trader = models.ForeignKey(
        Trader,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    is_active = models.BooleanField(default=True)
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )  # % of capital to allocate
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    stop_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['follower', 'trader']

class CopiedTrade(models.Model):
    """Record of trades copied from master traders"""
    subscription = models.ForeignKey(CopyTradingSubscription, on_delete=models.CASCADE)
    master_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='master_order')
    follower_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='follower_order')
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.5 AI Trading Bots

```python
# bots/models.py
from django.db import models

class TradingBot(models.Model):
    """AI trading bot configurations"""
    STRATEGY_CHOICES = [
        ('moving_average', 'Moving Average Crossover'),
        ('rsi', 'RSI Strategy'),
        ('macd', 'MACD Strategy'),
        ('bollinger', 'Bollinger Bands'),
        ('arbitrage', 'Arbitrage'),
        ('ml_model', 'Machine Learning Model'),
        ('custom', 'Custom Strategy')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=False)
    is_paper_trading = models.BooleanField(default=True)
    
    # Risk management
    max_position_size = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    take_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Strategy parameters (JSON for flexibility)
    parameters = models.JSONField(default=dict)
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

class BotTrade(models.Model):
    """Trades executed by bots"""
    bot = models.ForeignKey(TradingBot, on_delete=models.CASCADE)
    order = models.ForeignKey('trading.Order', on_delete=models.CASCADE)
    signal_data = models.JSONField()  # Store the signal that triggered the trade
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.6 Premium Signals

```python
# signals/models.py
from django.db import models

class SignalProvider(models.Model):
    """Signal provider information"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('in_house', 'In-House'),
            ('third_party', 'Third Party')
        ]
    )
    accuracy_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_signals = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalPlan(models.Model):
    """Subscription plans for signals"""
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    max_signals_per_day = models.IntegerField()
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalSubscription(models.Model):
    """User subscriptions to signal plans"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    plan = models.ForeignKey(SignalPlan, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled')
        ],
        default='active'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

class TradingSignal(models.Model):
    """Trading signals"""
    SIGNAL_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('close', 'Close Position')
    ]
    
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    trading_pair = models.ForeignKey('trading.TradingPair', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    timeframe = models.CharField(max_length=20)  # 1h, 4h, 1d, etc.
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    analysis = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('hit_tp', 'Take Profit Hit'),
            ('hit_sl', 'Stop Loss Hit'),
            ('closed', 'Manually Closed'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class SignalNotification(models.Model):
    """Track signal notifications sent to users"""
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acted_on = models.BooleanField(default=False)
```

### 2.7 Loan Management

```python
# loans/models.py
from django.db import models
from decimal import Decimal

class LoanProduct(models.Model):
    """Available loan products"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Annual %
    term_days = models.IntegerField()
    collateral_ratio = models.DecimalField(max_digits=5, decimal_places=2)  # %
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    """User loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_days = models.IntegerField()
    collateral_amount = models.DecimalField(max_digits=20, decimal_places=2)
    collateral_currency = models.CharField(max_length=10)
    outstanding_balance = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_loans'
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    repaid_at = models.DateTimeField(null=True, blank=True)

class LoanRepayment(models.Model):
    """Loan repayment transactions"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.ForeignKey('funds.Transaction', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.8 Referral System

```python
# referrals/models.py
from django.db import models

class ReferralTier(models.Model):
    """Referral reward tiers"""
    name = models.CharField(max_length=100)
    min_referrals = models.IntegerField()
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferralReward(models.Model):
    """Track referral rewards"""
    referrer = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_rewards'
    )
    referred_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_source'
    )
    reward_type = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'Signup Bonus'),
            ('first_deposit', 'First Deposit Bonus'),
            ('trading_commission', 'Trading Commission')
        ]
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    transaction = models.ForeignKey(
        'funds.Transaction',
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

## 3. API Endpoints

### 3.1 Authentication
```
POST   /api/v1/auth/register/          - User registration
POST   /api/v1/auth/login/             - User login
POST   /api/v1/auth/logout/            - User logout
POST   /api/v1/auth/refresh/           - Refresh JWT token
POST   /api/v1/auth/password-reset/    - Request password reset
POST   /api/v1/auth/password-reset-confirm/ - Confirm password reset
GET    /api/v1/auth/me/                - Get current user
PATCH  /api/v1/auth/me/                - Update current user
```

### 3.2 KYC
```
POST   /api/v1/kyc/submit/             - Submit KYC documents
GET    /api/v1/kyc/status/             - Get KYC status
GET    /api/v1/kyc/pending/            - List pending KYC (admin)
POST   /api/v1/kyc/{id}/approve/       - Approve KYC (admin)
POST   /api/v1/kyc/{id}/reject/        - Reject KYC (admin)
```

### 3.3 Funds
```
GET    /api/v1/wallets/                - List user wallets
GET    /api/v1/wallets/{currency}/     - Get specific wallet
POST   /api/v1/deposits/               - Create deposit
GET    /api/v1/deposits/               - List deposits
POST   /api/v1/withdrawals/            - Request withdrawal
GET    /api/v1/withdrawals/            - List withdrawals
POST   /api/v1/transfers/              - Internal transfer
GET    /api/v1/transactions/           - Transaction history
```

### 3.4 Trading
```
GET    /api/v1/trading-pairs/          - List trading pairs
GET    /api/v1/market-data/{symbol}/   - Get market data
POST   /api/v1/orders/                 - Create order
GET    /api/v1/orders/                 - List orders
GET    /api/v1/orders/{id}/            - Get order details
DELETE /api/v1/orders/{id}/            - Cancel order
GET    /api/v1/trades/                 - Trade history
GET    /api/v1/positions/              - Open positions
POST   /api/v1/positions/{id}/close/   - Close position
```

### 3.5 Copy Trading
```
GET    /api/v1/traders/                - List master traders
GET    /api/v1/traders/{id}/           - Trader details
POST   /api/v1/copy-trading/subscribe/ - Subscribe to trader
DELETE /api/v1/copy-trading/subscribe/{id}/ - Unsubscribe
GET    /api/v1/copy-trading/subscriptions/ - My subscriptions
PATCH  /api/v1/copy-trading/subscriptions/{id}/ - Update subscription
GET    /api/v1/copy-trading/performance/ - Copy trading performance
```

### 3.6 AI Bots
```
GET    /api/v1/bots/                   - List bots
POST   /api/v1/bots/                   - Create bot
GET    /api/v1/bots/{id}/              - Bot details
PATCH  /api/v1/bots/{id}/              - Update bot
DELETE /api/v1/bots/{id}/              - Delete bot
POST   /api/v1/bots/{id}/start/        - Start bot
POST   /api/v1/bots/{id}/stop/         - Stop bot
GET    /api/v1/bots/{id}/performance/  - Bot performance
GET    /api/v1/bot-strategies/         - Available strategies
```

### 3.7 Signals
```
GET    /api/v1/signal-providers/       - List providers
GET    /api/v1/signal-plans/           - Available plans
POST   /api/v1/signal-subscriptions/   - Subscribe to plan
GET    /api/v1/signal-subscriptions/   - My subscriptions
DELETE /api/v1/signal-subscriptions/{id}/ - Cancel subscription
GET    /api/v1/signals/                - My signals
GET    /api/v1/signals/{id}/           - Signal details
POST   /api/v1/signals/{id}/execute/   - Execute signal
```

### 3.8 Loans
```
GET    /api/v1/loan-products/          - Available products
POST   /api/v1/loans/                  - Apply for loan
GET    /api/v1/loans/                  - My loans
GET    /api/v1/loans/{id}/             - Loan details
POST   /api/v1/loans/{id}/repay/       - Make repayment
GET    /api/v1/loans/pending/          - Pending loans (admin)
POST   /api/v1/loans/{id}/approve/     - Approve loan (admin)
POST   /api/v1/loans/{id}/reject/      - Reject loan (admin)
```

### 3.9 Referrals
```
GET    /api/v1/referrals/code/         - Get referral code
GET    /api/v1/referrals/stats/        - Referral statistics
GET    /api/v1/referrals/rewards/      - Referral rewards
GET    /api/v1/referrals/referred-users/ - List referred users
```

## 4. Implementation Details

### 4.1 Market Data Integration

```python
# trading/services/market_service.py
import ccxt
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

class MarketDataService:
    """Service for fetching real-time market data"""
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET_KEY,
            'enableRateLimit': True,
        })
    
    def get_ticker(self, symbol):
        """Get current ticker data"""
        cache_key = f'ticker:{symbol}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        ticker = self.exchange.fetch_ticker(symbol)
        data = {
            'symbol': symbol,
            'last_price': Decimal(str(ticker['last'])),
            'bid': Decimal(str(ticker['bid'])),
            'ask': Decimal(str(ticker['ask'])),
            'volume': Decimal(str(ticker['volume'])),
            'change_24h': Decimal(str(ticker['percentage'])),
            'high_24h': Decimal(str(ticker['high'])),
            'low_24h': Decimal(str(ticker['low'])),
        }
        
        cache.set(cache_key, data, timeout=5)  # 5 seconds cache
        return data
    
    def get_orderbook(self, symbol, limit=20):
        """Get order book"""
        orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
        return {
            'bids': orderbook['bids'],
            'asks': orderbook['asks'],
        }
    
    def get_historical_data(self, symbol, timeframe='1h', limit=100):
        """Get historical OHLCV data"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [{
            'timestamp': candle[0],
            'open': Decimal(str(candle[1])),
            'high': Decimal(str(candle[2])),
            'low': Decimal(str(candle[3])),
            'close': Decimal(str(candle[4])),
            'volume': Decimal(str(candle[5])),
        } for candle in ohlcv]
```

### 4.2 Order Execution Engine

```python
# trading/services/order_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from trading.models import Order, Trade, Position
from funds.models import Wallet, Transaction
from trading.services.market_service import MarketDataService

class OrderExecutionService:
    """Handle order execution and position management"""
    
    def __init__(self):
        self.market_service = MarketDataService()
    
    @transaction.atomic
    def create_order(self, user, order_data):
        """Create and validate a new order"""
        trading_pair = order_data['trading_pair']
        side = order_data['side']
        quantity = Decimal(str(order_data['quantity']))
        
        # Validate user has sufficient balance
        if side == 'buy':
            required_balance = self._calculate_required_balance(
                trading_pair, quantity, order_data.get('price')
            )
            wallet = Wallet.objects.get(
                user=user,
                currency=trading_pair.quote_currency
            )
            if wallet.balance < required_balance:
                raise ValueError("Insufficient balance")
            
            # Lock the funds
            wallet.balance -= required_balance
            wallet.locked_balance += required_balance
            wallet.save()
        else:  # sell
            # Check if user has the asset
            wallet = Wallet.objects.get(
                user=user,
                currency=trading_pair.base_currency
            )
            if wallet.balance < quantity:
                raise ValueError("Insufficient asset balance")
            
            wallet.balance -= quantity
            wallet.locked_balance += quantity
            wallet.save()
        
        # Create the order
        order = Order.objects.create(
            user=user,
            **order_data,
            status='open'
        )
        
        # Execute market orders immediately
        if order.order_type == 'market':
            self._execute_market_order(order)
        
        return order
    
    def _execute_market_order(self, order):
        """Execute a market order"""
        ticker = self.market_service.get_ticker(
            order.trading_pair.symbol
        )
        
        execution_price = ticker['ask'] if order.side == 'buy' else ticker['bid']
        fee = self._calculate_fee(order, execution_price)
        
        # Create trade record
        trade = Trade.objects.create(
            order=order,
            quantity=order.quantity,
            price=execution_price,
            fee=fee,
            executed_at=timezone.now()
        )
        
        # Update order status
        order.filled_quantity = order.quantity
        order.average_price = execution_price
        order.fee = fee
        order.status = 'filled'
        order.executed_at = timezone.now()
        order.save()
        
        # Update user wallets
        self._settle_trade(order, trade)
        
        # Update or create position
        self._update_position(order)
    
    @transaction.atomic
    def _settle_trade(self, order, trade):
        """Settle the trade in user wallets"""
        user = order.user
        trading_pair = order.trading_pair
        
        if order.side == 'buy':
            # Unlock quote currency
            quote_wallet = Wallet.objects.select_for_update().get(
                user=user,
                currency=trading_pair.quote_currency
            )
            cost = trade.quantity * trade.price + trade.fee
            quote_wallet.locked_balance -= cost
            quote_wallet.save()
            
            # Add base currency
            base_wallet, _ = Wallet.objects.get_or_create(
                user=user,
                currency=trading_pair.base_currency
            )
            base_wallet.balance += trade.quantity
            base_wallet.save()
        else:  # sell
            # Unlock base currency
            base_wallet = Wallet.objects.select_for_update().get(
                user=user,
                currency=trading_pair.base_currency
            )
            base_wallet.locked_balance -= trade.quantity
            base_wallet.save()
            
            # Add quote currency
            quote_wallet, _ = Wallet.objects.get_or_create(
                user=user,
                currency=trading_pair.quote_currency
            )
            proceeds = trade.quantity * trade.price - trade.fee
            quote_wallet.balance += proceeds
            quote_wallet.save()
        
        # Create transaction record
        Transaction.objects.create(
            user=user,
            transaction_type='trade',
            currency=trading_pair.quote_currency,
            amount=trade.quantity * trade.price,
            fee=trade.fee,
            status='completed',
            reference_id=f'TRADE-{trade.id}',
            completed_at=timezone.now()
        )
    
    def _calculate_fee(self, order, price):
        """Calculate trading fee"""
        trading_pair = order.trading_pair
        return (order.quantity * price * 
                trading_pair.trading_fee_percentage / 100)
    
    def _calculate_required_balance(self, trading_pair, quantity, price=None):
        """Calculate required balance for an order"""
        if price is None:
            ticker = self.market_service.get_ticker(trading_pair.symbol)
            price = ticker['ask']
        
        cost = quantity * price
        fee = cost * trading_pair.trading_fee_percentage / 100
        return cost + fee
    
    def _update_position(self, order):
        """Update or create position after trade execution"""
        # Implementation for position tracking
        pass
```

### 4.3 Copy Trading Engine

```python
# copy_trading/services/copy_service.py
from decimal import Decimal
from django.db import transaction
from copy_trading.models import CopyTradingSubscription, CopiedTrade
from trading.services.order_service import OrderExecutionService

class CopyTradingService:
    """Service for executing copy trades"""
    
    def __init__(self):
        self.order_service = OrderExecutionService()
    
    def replicate_trade(self, master_order):
        """Replicate a master trader's order to all followers"""
        trader = master_order.user.trader
        
        # Get active subscribers
        subscriptions = CopyTradingSubscription.objects.filter(
            trader=trader,
            is_active=True
        ).select_related('follower')
        
        for subscription in subscriptions:
            try:
                self._copy_order_for_follower(master_order, subscription)
            except Exception as e:
                # Log error but continue with other followers
                print(f"Error copying trade for {subscription.follower}: {e}")
    
    @transaction.atomic
    def _copy_order_for_follower(self, master_order, subscription):
        """Copy an order for a specific follower"""
        follower = subscription.follower
        
        # Calculate position size based on follower's settings
        follower_quantity = self._calculate_follower_quantity(
            master_order,
            subscription
        )
        
        if follower_quantity <= 0:
            return
        
        # Create order data
        order_data = {
            'trading_pair': master_order.trading_pair,
            'order_type': master_order.order_type,
            'side': master_order.side,
            'quantity': follower_quantity,
            'price': master_order.price,
            'stop_price': master_order.stop_price,
            'source': 'copy_trade',
            'source_id': master_order.id
        }
        
        # Execute the order
        follower_order = self.order_service.create_order(
            follower,
            order_data
        )
        
        # Record the copied trade
        CopiedTrade.objects.create(
            subscription=subscription,
            master_order=master_order,
            follower_order=follower_order
        )
    
    def _calculate_follower_quantity(self, master_order, subscription):
        """Calculate appropriate quantity for follower"""
        # Get follower's available balance
        follower_wallet = subscription.follower.wallet_set.get(
            currency=master_order.trading_pair.quote_currency
        )
        
        # Calculate based on copy percentage
        max_allocation = (follower_wallet.balance * 
                         subscription.copy_percentage / 100)
        
        # Apply max position size if set
        if subscription.max_position_size:
            max_allocation = min(max_allocation, 
                               subscription.max_position_size)
        
        # Calculate quantity
        if master_order.price:
            quantity = max_allocation / master_order.price
        else:
            # Use current market price for market orders
            ticker = self.order_service.market_service.get_ticker(
                master_order.trading_pair.symbol
            )
            quantity = max_allocation / ticker['ask']
        
        return quantity
```

### 4.4 AI Bot Engine

```python
# bots/services/bot_engine.py
import numpy as np
import pandas as pd
from decimal import Decimal
from django.utils import timezone
from bots.models import TradingBot, BotTrade
from trading.services.order_service import OrderExecutionService
from trading.services.market_service import MarketDataService

class BotEngine:
    """Execute trading bot strategies"""
    
    def __init__(self, bot):
        self.bot = bot
        self.market_service = MarketDataService()
        self.order_service = OrderExecutionService()
    
    def run(self):
        """Execute bot trading logic"""
        if not self.bot.is_active:
            return
        
        # Check daily loss limit
        if self._check_daily_loss_limit():
            self.bot.is_active = False
            self.bot.save()
            return
        
        # Run strategy for each trading pair
        for trading_pair in self.bot.trading_pairs.all():
            try:
                signal = self._generate_signal(trading_pair)
                if signal:
                    self._execute_signal(signal, trading_pair)
            except Exception as e:
                print(f"Error running bot {self.bot.id}: {e}")
        
        self.bot.last_run_at = timezone.now()
        self.bot.save()
    
    def _generate_signal(self, trading_pair):
        """Generate trading signal based on strategy"""
        if self.bot.strategy == 'moving_average':
            return self._moving_average_strategy(trading_pair)
        elif self.bot.strategy == 'rsi':
            return self._rsi_strategy(trading_pair)
        elif self.bot.strategy == 'macd':
            return self._macd_strategy(trading_pair)
        # Add more strategies...
        return None
    
    def _moving_average_strategy(self, trading_pair):
        """Moving Average Crossover Strategy"""
        params = self.bot.parameters
        short_period = params.get('short_period', 20)
        long_period = params.get('long_period', 50)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=long_period + 10
        )
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(historical_data)
        
        # Calculate moving averages
        df['sma_short'] = df['close'].rolling(window=short_period).mean()
        df['sma_long'] = df['close'].rolling(window=long_period).mean()
        
        # Get last two rows to detect crossover
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish crossover
        if (previous['sma_short'] <= previous['sma_long'] and 
            current['sma_short'] > current['sma_long']):
            return {
                'action': 'buy',
                'price': current['close'],
                'reason': 'MA Bullish Crossover'
            }
        
        # Bearish crossover
        elif (previous['sma_short'] >= previous['sma_long'] and 
              current['sma_short'] < current['sma_long']):
            return {
                'action': 'sell',
                'price': current['close'],
                'reason': 'MA Bearish Crossover'
            }
        
        return None
    
    def _rsi_strategy(self, trading_pair):
        """RSI Strategy"""
        params = self.bot.parameters
        period = params.get('rsi_period', 14)
        oversold = params.get('oversold_level', 30)
        overbought = params.get('overbought_level', 70)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=period + 10
        )
        
        df = pd.DataFrame(historical_data)
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Buy signal
        if current_rsi < oversold:
            return {
                'action': 'buy',
                'price': current_price,
                'reason': f'RSI Oversold: {current_rsi:.2f}'
            }
        
        # Sell signal
        elif current_rsi > overbought:
            return {
                'action': 'sell',
                'price': current_price,
                'reason': f'RSI Overbought: {current_rsi:.2f}'
            }
        
        return None
    
    def _execute_signal(self, signal, trading_pair):
        """Execute trading signal"""
        # Calculate position size
        quantity = self._calculate_position_size(trading_pair, signal['price'])
        
        if quantity <= 0:
            return
        
        # Create order
        order_data = {
            'trading_pair': trading_pair,
            'order_type': 'market',
            'side': signal['action'],
            'quantity': quantity,
            'source': 'bot',
            'source_id': self.bot.id
        }
        
        # Add stop loss and take profit
        if signal['action'] == 'buy':
            order_data['stop_price'] = (
                signal['price'] * (1 - self.bot.stop_loss_percentage / 100)
            )
        
        try:
            order = self.order_service.create_order(
                self.bot.user,
                order_data
            )
            
            # Record bot trade
            BotTrade.objects.create(
                bot=self.bot,
                order=order,
                signal_data=signal
            )
            
            # Update bot statistics
            self.bot.total_trades += 1
            self.bot.save()
            
        except Exception as e:
            print(f"Error executing bot signal: {e}")
    
    def _calculate_position_size(self, trading_pair, price):
        """Calculate position size based on risk management"""
        wallet = self.bot.user.wallet_set.get(
            currency=trading_pair.quote_currency
        )
        
        # Use configured max position size
        max_allocation = min(
            wallet.balance * Decimal('0.1'),  # Max 10% per trade
            self.bot.max_position_size
        )
        
        return max_allocation / Decimal(str(price))
    
    def _check_daily_loss_limit(self):
        """Check if daily loss limit exceeded"""
        today = timezone.now().date()
        
        # Calculate today's P&L
        today_trades = BotTrade.objects.filter(
            bot=self.bot,
            created_at__date=today
        ).select_related('order')
        
        total_pnl = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.order.price)
            for trade in today_trades
            if trade.order.status == 'filled'
        )
        
        return total_pnl < -self.bot.max_daily_loss
```

### 4.5 Signal Notification System

```python
# signals/services/notification_service.py
from django.core.mail import send_mail
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from signals.models import SignalNotification, SignalSubscription

class SignalNotificationService:
    """Send trading signals to subscribed users"""
    
    def notify_subscribers(self, signal):
        """Send signal to all active subscribers"""
        # Get active subscriptions for this provider
        subscriptions = SignalSubscription.objects.filter(
            plan__provider=signal.provider,
            status='active',
            expires_at__gt=timezone.now()
        ).select_related('user')
        
        for subscription in subscriptions:
            # Check if signal's trading pair is in plan
            if signal.trading_pair in subscription.plan.trading_pairs.all():
                self._send_notification(subscription.user, signal)
    
    def _send_notification(self, user, signal):
        """Send notification to a specific user"""
        # Create notification record
        notification = SignalNotification.objects.create(
            signal=signal,
            user=user
        )
        
        # Send via WebSocket
        self._send_websocket(user, signal)
        
        # Send email if user has email notifications enabled
        if user.profile.email_notifications:
            self._send_email(user, signal)
        
        # Send push notification if mobile app
        if user.profile.push_notifications:
            self._send_push(user, signal)
    
    def _send_websocket(self, user, signal):
        """Send real-time WebSocket notification"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}',
            {
                'type': 'trading_signal',
                'signal': {
                    'id': signal.id,
                    'trading_pair': signal.trading_pair.symbol,
                    'type': signal.signal_type,
                    'entry_price': str(signal.entry_price),
                    'stop_loss': str(signal.stop_loss),
                    'take_profit': str(signal.take_profit),
                    'confidence': str(signal.confidence),
                    'analysis': signal.analysis
                }
            }
        )
    
    def _send_email(self, user, signal):
        """Send email notification"""
        subject = f'New Trading Signal: {signal.trading_pair.symbol}'
        message = f"""
        New {signal.signal_type.upper()} signal for {signal.trading_pair.symbol}
        
        Entry Price: {signal.entry_price}
        Stop Loss: {signal.stop_loss}
        Take Profit: {signal.take_profit}
        Confidence: {signal.confidence}%
        
        Analysis:
        {signal.analysis}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )
```

### 4.6 Celery Tasks

```python
# tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def update_market_prices():
    """Update market prices for all active trading pairs"""
    from trading.models import TradingPair
    from trading.services.market_service import MarketDataService
    
    market_service = MarketDataService()
    active_pairs = TradingPair.objects.filter(is_active=True)
    
    for pair in active_pairs:
        try:
            ticker = market_service.get_ticker(pair.symbol)
            # Update cached prices or database as needed
        except Exception as e:
            print(f"Error updating {pair.symbol}: {e}")

@shared_task
def execute_pending_orders():
    """Check and execute pending limit orders"""
    from trading.models import Order
    from trading.services.order_service import OrderExecutionService
    
    order_service = OrderExecutionService()
    pending_orders = Order.objects.filter(
        status='open',
        order_type__in=['limit', 'stop_loss', 'take_profit']
    )
    
    for order in pending_orders:
        try:
            order_service.check_and_execute_order(order)
        except Exception as e:
            print(f"Error executing order {order.id}: {e}")

@shared_task
def run_trading_bots():
    """Execute all active trading bots"""
    from bots.models import TradingBot
    from bots.services.bot_engine import BotEngine
    
    active_bots = TradingBot.objects.filter(
        is_active=True,
        is_paper_trading=False
    )
    
    for bot in active_bots:
        try:
            engine = BotEngine(bot)
            engine.run()
        except Exception as e:
            print(f"Error running bot {bot.id}: {e}")

@shared_task
def process_copy_trades():
    """Process copy trading orders"""
    from trading.models import Order
    from copy_trading.services.copy_service import CopyTradingService
    
    copy_service = CopyTradingService()
    
    # Get recently filled orders from master traders
    recent_orders = Order.objects.filter(
        status='filled',
        user__trader__isnull=False,
        executed_at__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(
        source='copy_trade'  # Don't copy already copied trades
    )
    
    for order in recent_orders:
        copy_service.replicate_trade(order)

@shared_task
def calculate_loan_interest():
    """Calculate and apply interest to active loans"""
    from loans.models import Loan
    from decimal import Decimal
    
    active_loans = Loan.objects.filter(status='active')
    
    for loan in active_loans:
        # Calculate daily interest
        daily_rate = loan.interest_rate / 365 / 100
        interest = loan.outstanding_balance * Decimal(str(daily_rate))
        
        loan.outstanding_balance += interest
        loan.save()

@shared_task
def process_referral_rewards():
    """Process referral rewards for completed actions"""
    from referrals.models import ReferralReward
    from funds.models import Transaction, Wallet
    
    # Process pending rewards
    pending_rewards = ReferralReward.objects.filter(
        transaction__isnull=True
    )
    
    for reward in pending_rewards:
        try:
            # Credit wallet
            wallet, _ = Wallet.objects.get_or_create(
                user=reward.referrer,
                currency=reward.currency
            )
            wallet.balance += reward.amount
            wallet.save()
            
            # Create transaction
            transaction = Transaction.objects.create(
                user=reward.referrer,
                transaction_type='referral_bonus',
                currency=reward.currency,
                amount=reward.amount,
                status='completed',
                reference_id=f'REF-{reward.id}',
                completed_at=timezone.now()
            )
            
            reward.transaction = transaction
            reward.save()
        except Exception as e:
            print(f"Error processing reward {reward.id}: {e}")

@shared_task
def check_kyc_expiry():
    """Check for expired KYC documents"""
    from users.models import User, KYCDocument
    from datetime import timedelta
    
    # KYC documents older than 2 years need reverification
    expiry_date = timezone.now() - timedelta(days=730)
    
    expired_kyc = KYCDocument.objects.filter(
        submitted_at__lt=expiry_date,
        user__kyc_status='approved'
    )
    
    for kyc in expired_kyc:
        kyc.user.kyc_status = 'not_submitted'
        kyc.user.save()
        # Send notification to user
```

## 5. API Views

### 5.1 Trading Views

```python
# trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from trading.models import Order, TradingPair, Position
from trading.serializers import (
    OrderSerializer, TradingPairSerializer, PositionSerializer
)
from trading.services.order_service import OrderExecutionService

class TradingPairViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading pairs endpoints"""
    queryset = TradingPair.objects.filter(is_active=True)
    serializer_class = TradingPairSerializer
    
    @action(detail=True, methods=['get'])
    def market_data(self, request, pk=None):
        """Get real-time market data"""
        trading_pair = self.get_object()
        market_service = MarketDataService()
        
        data = market_service.get_ticker(trading_pair.symbol)
        return Response(data)

class OrderViewSet(viewsets.ModelViewSet):
    """Order management endpoints"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Create a new order"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_service = OrderExecutionService()
        
        try:
            order = order_service.create_order(
                request.user,
                serializer.validated_data
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an open order"""
        order = self.get_object()
        
        if order.status not in ['open', 'partially_filled']:
            return Response(
                {'error': 'Order cannot be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        # Unlock funds
        # Implementation here...
        
        return Response(OrderSerializer(order).data)

class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """Position management endpoints"""
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Position.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a position"""
        position = self.get_object()
        
        # Create closing order
        order_service = OrderExecutionService()
        order_data = {
            'trading_pair': position.trading_pair,
            'order_type': 'market',
            'side': 'sell' if position.side == 'long' else 'buy',
            'quantity': position.quantity
        }
        
        order = order_service.create_order(request.user, order_data)
        
        return Response({
            'message': 'Position closed',
            'order': OrderSerializer(order).data
        })
```

## 6. Django Templates & jQuery Integration

Since you're using Django full-stack without a separate frontend, here's how to integrate the APIs with jQuery:

### 6.1 Base Template Setup

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Trading Platform{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'home' %}">Trading Platform</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    {% if user.is_authenticated %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'dashboard' %}">Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'trading' %}">Trading</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'wallets' %}">Wallets</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'bots' %}">Bots</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'signals' %}">Signals</a></li>
                        <li class="nav-item">
                            <span class="nav-link">Balance: $<span id="total-balance">0.00</span></span>
                        </li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'logout' %}">Logout</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'login' %}">Login</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'register' %}">Register</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="container mt-4">
        {% if messages %}
            <div id="messages">
                {% for message in messages %}
                    <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </main>

    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- API Helper -->
    <script>
        // CSRF Token setup for Django
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        
        const csrftoken = getCookie('csrftoken');
        
        // Setup jQuery AJAX defaults
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                    // Only send the token to relative URLs i.e. locally.
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                }
            }
        });
        
        // API Helper functions
        const API = {
            baseUrl: '/api/v1',
            
            // Generic request method
            request: function(method, endpoint, data = null) {
                return $.ajax({
                    url: this.baseUrl + endpoint,
                    method: method,
                    data: data ? JSON.stringify(data) : null,
                    contentType: 'application/json',
                    dataType: 'json'
                });
            },
            
            get: function(endpoint) {
                return this.request('GET', endpoint);
            },
            
            post: function(endpoint, data) {
                return this.request('POST', endpoint, data);
            },
            
            patch: function(endpoint, data) {
                return this.request('PATCH', endpoint, data);
            },
            
            delete: function(endpoint) {
                return this.request('DELETE', endpoint);
            },
            
            // Show message helper
            showMessage: function(message, type = 'success') {
                const alertHtml = `
                    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                        ${message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                `;
                $('#messages').html(alertHtml);
                
                // Auto-dismiss after 5 seconds
                setTimeout(function() {
                    $('.alert').alert('close');
                }, 5000);
            },
            
            // Error handler
            handleError: function(xhr) {
                let message = 'An error occurred';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    message = xhr.responseJSON.error;
                } else if (xhr.responseJSON) {
                    message = JSON.stringify(xhr.responseJSON);
                }
                this.showMessage(message, 'danger');
            }
        };
    </script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### 6.2 Trading Page with jQuery

```html
<!-- templates/trading/trading.html -->
{% extends 'base.html' %}

{% block title %}Trading - Platform{% endblock %}

{% block content %}
<div class="row">
    <!-- Trading Pairs List -->
    <div class="col-md-3">
        <div class="card">
            <div class="card-header">
                <h5>Trading Pairs</h5>
                <input type="text" id="pair-search" class="form-control form-control-sm mt-2" placeholder="Search...">
            </div>
            <div class="card-body p-0">
                <div id="trading-pairs-list" class="list-group list-group-flush" style="max-height: 600px; overflow-y: auto;">
                    <!-- Pairs will be loaded here -->
                </div>
            </div>
        </div>
    </div>
    
    <!-- Chart & Order Form -->
    <div class="col-md-6">
        <div class="card mb-3">
            <div class="card-header">
                <h5 id="current-pair">Select a trading pair</h5>
                <div class="d-flex justify-content-between align-items-center mt-2">
                    <div>
                        <span class="text-muted">Price:</span>
                        <strong id="current-price">$0.00</strong>
                    </div>
                    <div>
                        <span class="text-muted">24h Change:</span>
                        <strong id="price-change" class="text-success">+0.00%</strong>
                    </div>
                    <div>
                        <span class="text-muted">Volume:</span>
                        <strong id="volume">0</strong>
                    </div>
                </div>
            </div>
            <div class="card-body">
                <!-- TradingView Chart or custom chart -->
                <div id="price-chart" style="height: 400px; background: #f8f9fa;">
                    <p class="text-center pt-5">Chart will be displayed here</p>
                </div>
            </div>
        </div>
        
        <!-- Order Form -->
        <div class="card">
            <div class="card-header">
                <ul class="nav nav-tabs card-header-tabs" role="tablist">
                    <li class="nav-item">
                        <a class="nav-link active" data-bs-toggle="tab" href="#buy-tab">Buy</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-bs-toggle="tab" href="#sell-tab">Sell</a>
                    </li>
                </ul>
            </div>
            <div class="card-body">
                <div class="tab-content">
                    <!-- Buy Tab -->
                    <div class="tab-pane fade show active" id="buy-tab">
                        <form id="buy-form">
                            <div class="mb-3">
                                <label class="form-label">Order Type</label>
                                <select class="form-select" id="buy-order-type">
                                    <option value="market">Market</option>
                                    <option value="limit">Limit</option>
                                </select>
                            </div>
                            <div class="mb-3 limit-price-group" style="display: none;">
                                <label class="form-label">Price</label>
                                <input type="number" class="form-control" id="buy-price" step="0.01">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Amount</label>
                                <input type="number" class="form-control" id="buy-amount" step="0.00000001" required>
                                <small class="text-muted">Available: <span id="buy-available">0</span> USD</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Total</label>
                                <input type="number" class="form-control" id="buy-total" readonly>
                            </div>
                            <button type="submit" class="btn btn-success w-100">Buy</button>
                        </form>
                    </div>
                    
                    <!-- Sell Tab -->
                    <div class="tab-pane fade" id="sell-tab">
                        <form id="sell-form">
                            <div class="mb-3">
                                <label class="form-label">Order Type</label>
                                <select class="form-select" id="sell-order-type">
                                    <option value="market">Market</option>
                                    <option value="limit">Limit</option>
                                </select>
                            </div>
                            <div class="mb-3 limit-price-group" style="display: none;">
                                <label class="form-label">Price</label>
                                <input type="number" class="form-control" id="sell-price" step="0.01">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Amount</label>
                                <input type="number" class="form-control" id="sell-amount" step="0.00000001" required>
                                <small class="text-muted">Available: <span id="sell-available">0</span> BTC</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Total</label>
                                <input type="number" class="form-control" id="sell-total" readonly>
                            </div>
                            <button type="submit" class="btn btn-danger w-100">Sell</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Order Book & Recent Trades -->
    <div class="col-md-3">
        <div class="card mb-3">
            <div class="card-header">
                <h6>Order Book</h6>
            </div>
            <div class="card-body p-0">
                <div id="order-book" style="max-height: 300px; overflow-y: auto;">
                    <!-- Order book will be loaded here -->
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h6>Recent Trades</h6>
            </div>
            <div class="card-body p-0">
                <div id="recent-trades" style="max-height: 300px; overflow-y: auto;">
                    <!-- Recent trades will be loaded here -->
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Open Orders -->
<div class="row mt-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5>Open Orders</h5>
            </div>
            <div class="card-body">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Pair</th>
                            <th>Type</th>
                            <th>Side</th>
                            <th>Price</th>
                            <th>Amount</th>
                            <th>Filled</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="open-orders">
                        <!-- Orders will be loaded here -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
$(document).ready(function() {
    let currentPair = null;
    let currentPrice = 0;
    
    // Load trading pairs
    function loadTradingPairs() {
        API.get('/trading-pairs/')
            .done(function(data) {
                const pairsList = $('#trading-pairs-list');
                pairsList.empty();
                
                data.forEach(function(pair) {
                    const pairHtml = `
                        <a href="#" class="list-group-item list-group-item-action pair-item" data-pair-id="${pair.id}" data-symbol="${pair.symbol}">
                            <div class="d-flex justify-content-between">
                                <strong>${pair.symbol}</strong>
                                <span class="price-${pair.id}">$0.00</span>
                            </div>
                        </a>
                    `;
                    pairsList.append(pairHtml);
                });
                
                // Select first pair by default
                if (data.length > 0) {
                    selectPair(data[0].id, data[0].symbol);
                }
            })
            .fail(API.handleError);
    }
    
    // Select trading pair
    function selectPair(pairId, symbol) {
        currentPair = pairId;
        $('#current-pair').text(symbol);
        
        // Highlight selected pair
        $('.pair-item').removeClass('active');
        $(`.pair-item[data-pair-id="${pairId}"]`).addClass('active');
        
        // Load market data
        loadMarketData(pairId);
        
        // Load order book
        loadOrderBook(symbol);
        
        // Load user balances
        loadBalances(symbol);
    }
    
    // Load market data
    function loadMarketData(pairId) {
        API.get(`/trading-pairs/${pairId}/market_data/`)
            .done(function(data) {
                currentPrice = parseFloat(data.last_price);
                $('#current-price').text(' + currentPrice.toFixed(2));
                $('#price-change').text(data.change_24h + '%')
                    .removeClass('text-success text-danger')
                    .addClass(data.change_24h >= 0 ? 'text-success' : 'text-danger');
                $('#volume').text(parseFloat(data.volume).toFixed(2));
            });
    }
    
    // Load order book
    function loadOrderBook(symbol) {
        // This would call your backend which calls the market API
        // For now, placeholder
        $('#order-book').html('<p class="text-center text-muted p-3">Loading...</p>');
    }
    
    // Load user balances
    function loadBalances(symbol) {
        API.get('/wallets/')
            .done(function(data) {
                // Update available balances for buy/sell
                const usdWallet = data.find(w => w.currency === 'USD');
                const baseWallet = data.find(w => w.currency === symbol.split('/')[0]);
                
                if (usdWallet) {
                    $('#buy-available').text(parseFloat(usdWallet.balance).toFixed(2));
                }
                if (baseWallet) {
                    $('#sell-available').text(parseFloat(baseWallet.balance).toFixed(8));
                }
            });
    }
    
    // Load open orders
    function loadOpenOrders() {
        API.get('/orders/?status=open')
            .done(function(data) {
                const tbody = $('#open-orders');
                tbody.empty();
                
                if (data.length === 0) {
                    tbody.html('<tr><td colspan="9" class="text-center text-muted">No open orders</td></tr>');
                    return;
                }
                
                data.forEach(function(order) {
                    const row = `
                        <tr>
                            <td>${new Date(order.created_at).toLocaleString()}</td>
                            <td>${order.trading_pair.symbol}</td>
                            <td>${order.order_type}</td>
                            <td><span class="badge bg-${order.side === 'buy' ? 'success' : 'danger'}">${order.side}</span></td>
                            <td>${parseFloat(order.price).toFixed(2)}</td>
                            <td>${parseFloat(order.quantity).toFixed(8)}</td>
                            <td>${parseFloat(order.filled_quantity).toFixed(8)}</td>
                            <td><span class="badge bg-warning">${order.status}</span></td>
                            <td>
                                <button class="btn btn-sm btn-danger cancel-order" data-order-id="${order.id}">Cancel</button>
                            </td>
                        </tr>
                    `;
                    tbody.append(row);
                });
            });
    }
    
    // Handle order type change
    $('#buy-order-type, #sell-order-type').on('change', function() {
        const form = $(this).closest('form');
        if ($(this).val() === 'limit') {
            form.find('.limit-price-group').show();
        } else {
            form.find('.limit-price-group').hide();
        }
    });
    
    // Calculate total
    $('#buy-amount, #buy-price').on('input', function() {
        const amount = parseFloat($('#buy-amount').val()) || 0;
        const price = $('#buy-order-type').val() === 'market' 
            ? currentPrice 
            : (parseFloat($('#buy-price').val()) || 0);
        $('#buy-total').val((amount * price).toFixed(2));
    });
    
    $('#sell-amount, #sell-price').on('input', function() {
        const amount = parseFloat($('#sell-amount').val()) || 0;
        const price = $('#sell-order-type').val() === 'market' 
            ? currentPrice 
            : (parseFloat($('#sell-price').val()) || 0);
        $('#sell-total').val((amount * price).toFixed(2));
    });
    
    // Handle buy form submission
    $('#buy-form').on('submit', function(e) {
        e.preventDefault();
        
        const orderData = {
            trading_pair: currentPair,
            order_type: $('#buy-order-type').val(),
            side: 'buy',
            quantity: $('#buy-amount').val(),
            price: $('#buy-order-type').val() === 'limit' ? $('#buy-price').val() : null
        };
        
        API.post('/orders/', orderData)
            .done(function(data) {
                API.showMessage('Buy order placed successfully!', 'success');
                $('#buy-form')[0].reset();
                loadOpenOrders();
                loadBalances($('#current-pair').text());
            })
            .fail(API.handleError);
    });
    
    // Handle sell form submission
    $('#sell-form').on('submit', function(e) {
        e.preventDefault();
        
        const orderData = {
            trading_pair: currentPair,
            order_type: $('#sell-order-type').val(),
            side: 'sell',
            quantity: $('#sell-amount').val(),
            price: $('#sell-order-type').val() === 'limit' ? $('#sell-price').val() : null
        };
        
        API.post('/orders/', orderData)
            .done(function(data) {
                API.showMessage('Sell order placed successfully!', 'success');
                $('#sell-form')[0].reset();
                loadOpenOrders();
                loadBalances($('#current-pair').text());
            })
            .fail(API.handleError);
    });
    
    // Handle order cancellation
    $(document).on('click', '.cancel-order', function() {
        const orderId = $(this).data('order-id');
        
        if (confirm('Are you sure you want to cancel this order?')) {
            API.post(`/orders/${orderId}/cancel/`)
                .done(function(data) {
                    API.showMessage('Order cancelled successfully!', 'success');
                    loadOpenOrders();
                })
                .fail(API.handleError);
        }
    });
    
    // Pair search
    $('#pair-search').on('input', function() {
        const search = $(this).val().toLowerCase();
        $('.pair-item').each(function() {
            const symbol = $(this).data('symbol').toLowerCase();
            $(this).toggle(symbol.includes(search));
        });
    });
    
    // Handle pair click
    $(document).on('click', '.pair-item', function(e) {
        e.preventDefault();
        const pairId = $(this).data('pair-id');
        const symbol = $(this).data('symbol');
        selectPair(pairId, symbol);
    });
    
    // Initialize
    loadTradingPairs();
    loadOpenOrders();
    
    // Refresh data periodically
    setInterval(function() {
        if (currentPair) {
            loadMarketData(currentPair);
        }
        loadOpenOrders();
    }, 5000);
});
</script>
{% endblock %}
```

Now let me complete the remaining backend components:

## 7. Serializers

### 7.1 User Serializers

```python
# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from users.models import User, KYCDocument

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 
                  'phone_number', 'is_verified', 'kyc_status', 'referral_code',
                  'created_at']
        read_only_fields = ['id', 'is_verified', 'kyc_status', 'referral_code', 
                           'created_at']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    referred_by_code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password_confirm', 
                  'first_name', 'last_name', 'phone_number', 'referred_by_code']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        # Generate unique referral code
        import random
        import string
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Handle referral
        referred_by = None
        if referred_by_code:
            try:
                referred_by = User.objects.get(referral_code=referred_by_code)
            except User.DoesNotExist:
                pass
        
        user = User.objects.create_user(
            **validated_data,
            referral_code=referral_code,
            referred_by=referred_by
        )
        
        return user

class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ['id', 'document_type', 'document_number', 'document_front',
                  'document_back', 'selfie', 'address_proof', 'date_of_birth',
                  'address', 'city', 'country', 'postal_code', 'submitted_at',
                  'rejection_reason']
        read_only_fields = ['id', 'submitted_at', 'rejection_reason']
```

### 7.2 Trading Serializers

```python
# trading/serializers.py
from rest_framework import serializers
from trading.models import TradingPair, Order, Trade, Position

class TradingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingPair
        fields = ['id', 'symbol', 'base_currency', 'quote_currency', 
                  'market_type', 'is_active', 'min_order_size', 'max_order_size',
                  'price_precision', 'quantity_precision', 'trading_fee_percentage']

class OrderSerializer(serializers.ModelSerializer):
    trading_pair = serializers.PrimaryKeyRelatedField(
        queryset=TradingPair.objects.all()
    )
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'trading_pair', 'trading_pair_detail', 'order_type', 
                  'side', 'quantity', 'price', 'stop_price', 'filled_quantity',
                  'average_price', 'status', 'fee', 'source', 'created_at',
                  'updated_at', 'executed_at']
        read_only_fields = ['id', 'filled_quantity', 'average_price', 'status',
                           'fee', 'created_at', 'updated_at', 'executed_at']
    
    def validate(self, attrs):
        trading_pair = attrs['trading_pair']
        quantity = attrs['quantity']
        
        # Validate order size
        if quantity < trading_pair.min_order_size:
            raise serializers.ValidationError(
                f"Quantity must be at least {trading_pair.min_order_size}"
            )
        
        if quantity > trading_pair.max_order_size:
            raise serializers.ValidationError(
                f"Quantity must not exceed {trading_pair.max_order_size}"
            )
        
        # Validate price for limit orders
        if attrs['order_type'] == 'limit' and not attrs.get('price'):
            raise serializers.ValidationError("Price is required for limit orders")
        
        return attrs

class TradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = Trade
        fields = ['id', 'order', 'order_detail', 'quantity', 'price', 'fee',
                  'executed_at', 'external_trade_id']

class PositionSerializer(serializers.ModelSerializer):
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = Position
        fields = ['id', 'trading_pair', 'trading_pair_detail', 'side', 'quantity',
                  'entry_price', 'current_price', 'unrealized_pnl', 'leverage',
                  'stop_loss', 'take_profit', 'opened_at', 'updated_at']
```

### 7.3 Funds Serializers

```python
# funds/serializers.py
from rest_framework import serializers
from funds.models import Wallet, Transaction, Deposit, Withdrawal

class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = ['id', 'currency', 'balance', 'locked_balance', 
                  'available_balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'locked_balance', 'created_at', 
                           'updated_at']
    
    def get_available_balance(self, obj):
        return obj.balance - obj.locked_balance

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_type', 'currency', 'amount', 'fee', 
                  'status', 'reference_id', 'external_id', 'notes',
                  'created_at', 'completed_at']
        read_only_fields = ['id', 'status', 'reference_id', 'created_at', 
                           'completed_at']

class DepositSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    
    class Meta:
        model = Deposit
        fields = ['id', 'transaction', 'payment_method', 'payment_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='deposit',
            currency=validated_data.get('currency', 'USD'),
            amount=validated_data.get('amount'),
            status='pending',
            reference_id=f'DEP-{uuid.uuid4().hex[:12].upper()}'
        )
        
        # Create deposit record
        deposit = Deposit.objects.create(
            transaction=transaction,
            payment_method=validated_data['payment_method'],
            payment_details=validated_data['payment_details']
        )
        
        return deposit

class WithdrawalSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = ['id', 'transaction', 'destination_type', 'destination_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        amount = validated_data.get('amount')
        currency = validated_data.get('currency', 'USD')
        
        # Check balance
        wallet = Wallet.objects.get(user=user, currency=currency)
        if wallet.balance < amount:
            raise serializers.ValidationError("Insufficient balance")
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='withdrawal',
            currency=currency,
            amount=amount,
            status='pending',
            reference_id=f'WDR-{uuid.uuid4().hex[:12].upper()}'
        )
        
        # Lock funds
        wallet.balance -= amount
        wallet.locked_balance += amount
        wallet.save()
        
        # Create withdrawal record
        withdrawal = Withdrawal.objects.create(
            transaction=transaction,
            destination_type=validated_data['destination_type'],
            destination_details=validated_data['destination_details']
        )
        
        return withdrawal
```

### 7.4 Bot Serializers

```python
# bots/serializers.py
from rest_framework import serializers
from bots.models import TradingBot, BotTrade

class TradingBotSerializer(serializers.ModelSerializer):
    trading_pairs = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=TradingPair.objects.all()
    )
    win_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TradingBot
        fields = ['id', 'name', 'description', 'strategy', 'trading_pairs',
                  'is_active', 'is_paper_trading', 'max_position_size',
                  'stop_loss_percentage', 'take_profit_percentage',
                  'max_daily_loss', 'parameters', 'total_trades',
                  'winning_trades', 'total_profit', 'win_rate',
                  'created_at', 'updated_at', 'last_run_at']
        read_only_fields = ['id', 'total_trades', 'winning_trades', 
                           'total_profit', 'created_at', 'updated_at', 
                           'last_run_at']
    
    def get_win_rate(self, obj):
        if obj.total_trades == 0:
            return 0
        return (obj.winning_trades / obj.total_trades) * 100

class BotTradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = BotTrade
        fields = ['id', 'bot', 'order', 'order_detail', 'signal_data', 
                  'created_at']
```

### 7.5 Copy Trading Serializers

```python
# copy_trading/serializers.py
from rest_framework import serializers
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade

class TraderSerializer(serializers.ModelSerializer):
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Trader
        fields = ['id', 'user', 'user_info', 'display_name', 'bio', 
                  'is_active', 'total_followers', 'total_profit',
                  'profit_percentage', 'win_rate', 'total_trades',
                  'risk_score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_followers', 'total_profit',
                           'profit_percentage', 'win_rate', 'total_trades',
                           'created_at', 'updated_at']

class CopyTradingSubscriptionSerializer(serializers.ModelSerializer):
    trader_detail = TraderSerializer(source='trader', read_only=True)
    
    class Meta:
        model = CopyTradingSubscription
        fields = ['id', 'trader', 'trader_detail', 'is_active', 
                  'copy_percentage', 'max_position_size',
                  'stop_loss_percentage', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        # Ensure user doesn't subscribe to themselves
        if attrs['trader'].user == self.context['request'].user:
            raise serializers.ValidationError("Cannot copy your own trades")
        
        return attrs

class CopiedTradeSerializer(serializers.ModelSerializer):
    subscription_detail = CopyTradingSubscriptionSerializer(
        source='subscription', 
        read_only=True
    )
    master_order_detail = OrderSerializer(source='master_order', read_only=True)
    follower_order_detail = OrderSerializer(source='follower_order', read_only=True)
    
    class Meta:
        model = CopiedTrade
        fields = ['id', 'subscription', 'subscription_detail', 'master_order',
                  'master_order_detail', 'follower_order', 'follower_order_detail',
                  'created_at']
```

### 7.6 Signals Serializers

```python
# signals/serializers.py
from rest_framework import serializers
from signals.models import (
    SignalProvider, SignalPlan, SignalSubscription, 
    TradingSignal, SignalNotification
)

class SignalProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignalProvider
        fields = ['id', 'name', 'description', 'provider_type', 'accuracy_rate',
                  'total_signals', 'is_active', 'created_at']

class SignalPlanSerializer(serializers.ModelSerializer):
    provider_detail = SignalProviderSerializer(source='provider', read_only=True)
    
    class Meta:
        model = SignalPlan
        fields = ['id', 'provider', 'provider_detail', 'name', 'description',
                  'price', 'duration_days', 'max_signals_per_day',
                  'trading_pairs', 'is_active', 'created_at']

class SignalSubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = SignalPlanSerializer(source='plan', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = SignalSubscription
        fields = ['id', 'plan', 'plan_detail', 'status', 'started_at',
                  'expires_at', 'auto_renew', 'days_remaining']
        read_only_fields = ['id', 'started_at', 'expires_at']
    
    def get_days_remaining(self, obj):
        from datetime import datetime
        if obj.expires_at:
            delta = obj.expires_at - datetime.now(obj.expires_at.tzinfo)
            return max(0, delta.days)
        return 0

class TradingSignalSerializer(serializers.ModelSerializer):
    provider_detail = SignalProviderSerializer(source='provider', read_only=True)
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = TradingSignal
        fields = ['id', 'provider', 'provider_detail', 'trading_pair',
                  'trading_pair_detail', 'signal_type', 'entry_price',
                  'stop_loss', 'take_profit', 'timeframe', 'confidence',
                  'analysis', 'status', 'created_at', 'closed_at']

class SignalNotificationSerializer(serializers.ModelSerializer):
    signal_detail = TradingSignalSerializer(source='signal', read_only=True)
    
    class Meta:
        model = SignalNotification
        fields = ['id', 'signal', 'signal_detail', 'sent_at', 'read_at', 
                  'acted_on']
```

### 7.7 Loan Serializers

```python
# loans/serializers.py
from rest_framework import serializers
from loans.models import LoanProduct, Loan, LoanRepayment

class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = ['id', 'name', 'description', 'min_amount', 'max_amount',
                  'interest_rate', 'term_days', 'collateral_ratio',
                  'is_active', 'created_at']

class LoanSerializer(serializers.ModelSerializer):
    product_detail = LoanProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = Loan
        fields = ['id', 'product', 'product_detail', 'amount', 'interest_rate',
                  'term_days', 'collateral_amount', 'collateral_currency',
                  'outstanding_balance', 'status', 'applied_at', 'approved_at',
                  'disbursed_at', 'due_date', 'repaid_at']
        read_only_fields = ['id', 'interest_rate', 'outstanding_balance', 
                           'status', 'applied_at', 'approved_at', 'disbursed_at',
                           'due_date', 'repaid_at']
    
    def validate(self, attrs):
        product = attrs['product']
        amount = attrs['amount']
        
        if amount < product.min_amount or amount > product.max_amount:
            raise serializers.ValidationError(
                f"Amount must be between {product.min_amount} and {product.max_amount}"
            )
        
        # Calculate required collateral
        required_collateral = amount * product.collateral_ratio / 100
        if attrs['collateral_amount'] < required_collateral:
            raise serializers.ValidationError(
                f"Minimum collateral required: {required_collateral}"
            )
        
        return attrs

class LoanRepaymentSerializer(serializers.ModelSerializer):
    transaction_detail = TransactionSerializer(source='transaction', read_only=True)
    
    class Meta:
        model = LoanRepayment
        fields = ['id', 'loan', 'amount', 'principal_amount', 'interest_amount',
                  'transaction', 'transaction_detail', 'created_at']
        read_only_fields = ['id', 'principal_amount', 'interest_amount', 
                           'created_at']
```

## 8. Complete ViewSets

### 8.1 Authentication Views

```python
# users/views.py
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from users.serializers import (
    UserSerializer, UserRegistrationSerializer, KYCDocumentSerializer
)
from users.models import KYCDocument

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)

class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class KYCViewSet(viewsets.ModelViewSet):
    """KYC verification endpoints"""
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return KYCDocument.objects.all()
        return KYCDocument.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Submit KYC documents"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user already submitted KYC
        if KYCDocument.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'KYC already submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        kyc = serializer.save(user=request.user)
        request.user.kyc_status = 'pending'
        request.user.save()
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve KYC (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kyc = self.get_object()
        kyc.user.kyc_status = 'approved'
        kyc.user.is_verified = True
        kyc.user.save()
        
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.save()
        
        return Response({'message': 'KYC approved'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject KYC (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kyc = self.get_object()
        kyc.user.kyc_status = 'rejected'
        kyc.user.save()
        
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = request.data.get('reason', '')
        kyc.save()
        
        return Response({'message': 'KYC rejected'})
```

### 8.2 Funds Views

```python
# funds/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from funds.models import Wallet, Transaction, Deposit, Withdrawal
from funds.serializers import (
    WalletSerializer, TransactionSerializer, 
    DepositSerializer, WithdrawalSerializer
)

class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    """Wallet management endpoints"""
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Transaction history endpoints"""
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['transaction_type', 'currency', 'status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

class DepositViewSet(viewsets.ModelViewSet):
    """Deposit management endpoints"""
    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Deposit.objects.filter(transaction__user=self.request.user)

class WithdrawalViewSet(viewsets.ModelViewSet):
    """Withdrawal management endpoints"""
    serializer_class = WithdrawalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Withdrawal.objects.filter(transaction__user=self.request.user)
```

### 8.3 Bot Views

```python
# bots/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from bots.models import TradingBot, BotTrade
from bots.serializers import TradingBotSerializer, BotTradeSerializer
from bots.services.bot_engine import BotEngine

class TradingBotViewSet(viewsets.ModelViewSet):
    """Trading bot management endpoints"""
    serializer_class = TradingBotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return TradingBot.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a trading bot"""
        bot = self.get_object()
        
        if bot.is_active:
            return Response(
                {'error': 'Bot is already running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bot.is_active = True
        bot.save()
        
        return Response({'message': 'Bot started successfully'})
    
    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """Stop a trading bot"""
        bot = self.get_object()
        
        if not bot.is_active:
            return Response(
                {'error': 'Bot is not running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bot.is_active = False
        bot.save()
        
        return Response({'message': 'Bot stopped successfully'})
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get bot performance metrics"""
        bot = self.get_object()
        
        trades = BotTrade.objects.filter(bot=bot).select_related('order')
        
        # Calculate metrics
        total_profit = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.signal_data.get('price', 0))
            for trade in trades
            if trade.order.status == 'filled'
        )
        
        return Response({
            'total_trades': bot.total_trades,
            'winning_trades': bot.winning_trades,
            'total_profit': bot.total_profit,
            'win_rate': (bot.winning_trades / bot.total_trades * 100) 
                       if bot.total_trades > 0 else 0,
            'recent_trades': BotTradeSerializer(trades[:10], many=True).data
        })

class BotTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Bot trade history endpoints"""
    serializer_class = BotTradeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BotTrade.objects.filter(bot__user=self.request.user)
```

### 8.4 Copy Trading Views

```python
# copy_trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade
from copy_trading.serializers import (
    TraderSerializer, CopyTradingSubscriptionSerializer, CopiedTradeSerializer
)

class TraderViewSet(viewsets.ReadOnlyModelViewSet):
    """Master trader listing endpoints"""
    serializer_class = TraderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Trader.objects.filter(is_active=True)
    filterset_fields = ['risk_score']
    ordering_fields = ['total_followers', 'profit_percentage', 'win_rate']
    ordering = ['-total_followers']

class CopyTradingSubscriptionViewSet(viewsets.ModelViewSet):
    """Copy trading subscription management"""
    serializer_class = CopyTradingSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CopyTradingSubscription.objects.filter(follower=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(follower=self.request.user)
        
        # Increment trader's follower count
        trader = serializer.validated_data['trader']
        trader.total_followers += 1
        trader.save()
    
    def perform_destroy(self, instance):
        # Decrement trader's follower count
        instance.trader.total_followers -= 1
        instance.trader.save()
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Get copy trading performance"""
        subscriptions = self.get_queryset().filter(is_active=True)
        
        total_profit = 0
        for sub in subscriptions:
            copied_trades = CopiedTrade.objects.filter(
                subscription=sub
            ).select_related('follower_order')
            
            for trade in copied_trades:
                if trade.follower_order.status == 'filled':
                    # Calculate profit
                    pass
        
        return Response({
            'active_subscriptions': subscriptions.count(),
            'total_



# Trading Platform Backend - Technical Specification

## 1. System Architecture

### 1.1 Technology Stack
- **Framework**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL (primary), Redis (cache/queue)
- **Task Queue**: Celery with Redis broker
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **WebSocket**: Django Channels for real-time updates
- **Payment Processing**: Stripe/PayPal integration
- **KYC Provider**: Onfido/Jumio API integration

### 1.2 High-Level Architecture
```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │◄────►│  Django API  │◄────►│  Database   │
│(Web/Mobile) │      │   Gateway    │      │ PostgreSQL  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Celery    │
                     │   Workers    │
                     └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Market     │    │  Copy Trade  │    │   AI Bot     │
│   Engine     │    │   Engine     │    │   Engine     │
└──────────────┘    └──────────────┘    └──────────────┘
        │
        ▼
┌──────────────┐
│ External APIs│
│(Binance,etc) │
└──────────────┘
```

## 2. Database Models

### 2.1 User Management

```python
# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """Extended user model with trading platform features"""
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
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
    referral_code = models.CharField(max_length=10, unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class KYCDocument(models.Model):
    """Store KYC verification documents"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('passport', 'Passport'),
            ('drivers_license', 'Driver\'s License'),
            ('national_id', 'National ID')
        ]
    )
    document_number = models.CharField(max_length=100, encrypted=True)
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
```

### 2.2 Fund Management

```python
# funds/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

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
```

### 2.3 Trading System

```python
# trading/models.py
from django.db import models
from decimal import Decimal

class TradingPair(models.Model):
    """Available trading pairs"""
    symbol = models.CharField(max_length=20, unique=True)  # BTC/USD, ETH/USD
    base_currency = models.CharField(max_length=10)
    quote_currency = models.CharField(max_length=10)
    market_type = models.CharField(
        max_length=10,
        choices=[('crypto', 'Crypto'), ('forex', 'Forex')]
    )
    is_active = models.BooleanField(default=True)
    min_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    max_order_size = models.DecimalField(max_digits=20, decimal_places=8)
    price_precision = models.IntegerField(default=2)
    quantity_precision = models.IntegerField(default=8)
    trading_fee_percentage = models.DecimalField(max_digits=5, decimal_places=4)

class Order(models.Model):
    """Trading orders"""
    ORDER_TYPES = [
        ('market', 'Market'),
        ('limit', 'Limit'),
        ('stop_loss', 'Stop Loss'),
        ('take_profit', 'Take Profit')
    ]
    
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('partially_filled', 'Partially Filled'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected')
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    filled_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0')
    )
    average_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    source = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('bot', 'AI Bot'),
            ('copy_trade', 'Copy Trade'),
            ('signal', 'Signal')
        ],
        default='manual'
    )
    source_id = models.IntegerField(null=True)  # ID of bot/trader/signal
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)

class Trade(models.Model):
    """Executed trades"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    executed_at = models.DateTimeField(auto_now_add=True)
    external_trade_id = models.CharField(max_length=100, blank=True)

class Position(models.Model):
    """Open positions for users"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE)
    side = models.CharField(max_length=4, choices=[('long', 'Long'), ('short', 'Short')])
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    leverage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 2.4 Copy Trading

```python
# copy_trading/models.py
from django.db import models

class Trader(models.Model):
    """Master traders that others can copy"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    total_followers = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2)
    profit_percentage = models.DecimalField(max_digits=10, decimal_places=2)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_trades = models.IntegerField(default=0)
    risk_score = models.IntegerField(default=5)  # 1-10
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CopyTradingSubscription(models.Model):
    """User subscriptions to copy traders"""
    follower = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='following'
    )
    trader = models.ForeignKey(
        Trader,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    is_active = models.BooleanField(default=True)
    copy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )  # % of capital to allocate
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True
    )
    stop_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['follower', 'trader']

class CopiedTrade(models.Model):
    """Record of trades copied from master traders"""
    subscription = models.ForeignKey(CopyTradingSubscription, on_delete=models.CASCADE)
    master_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='master_order')
    follower_order = models.ForeignKey('trading.Order', on_delete=models.CASCADE, related_name='follower_order')
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.5 AI Trading Bots

```python
# bots/models.py
from django.db import models

class TradingBot(models.Model):
    """AI trading bot configurations"""
    STRATEGY_CHOICES = [
        ('moving_average', 'Moving Average Crossover'),
        ('rsi', 'RSI Strategy'),
        ('macd', 'MACD Strategy'),
        ('bollinger', 'Bollinger Bands'),
        ('arbitrage', 'Arbitrage'),
        ('ml_model', 'Machine Learning Model'),
        ('custom', 'Custom Strategy')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=False)
    is_paper_trading = models.BooleanField(default=True)
    
    # Risk management
    max_position_size = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    take_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Strategy parameters (JSON for flexibility)
    parameters = models.JSONField(default=dict)
    
    # Performance metrics
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

class BotTrade(models.Model):
    """Trades executed by bots"""
    bot = models.ForeignKey(TradingBot, on_delete=models.CASCADE)
    order = models.ForeignKey('trading.Order', on_delete=models.CASCADE)
    signal_data = models.JSONField()  # Store the signal that triggered the trade
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.6 Premium Signals

```python
# signals/models.py
from django.db import models

class SignalProvider(models.Model):
    """Signal provider information"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('in_house', 'In-House'),
            ('third_party', 'Third Party')
        ]
    )
    accuracy_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_signals = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalPlan(models.Model):
    """Subscription plans for signals"""
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    max_signals_per_day = models.IntegerField()
    trading_pairs = models.ManyToManyField('trading.TradingPair')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SignalSubscription(models.Model):
    """User subscriptions to signal plans"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    plan = models.ForeignKey(SignalPlan, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled')
        ],
        default='active'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

class TradingSignal(models.Model):
    """Trading signals"""
    SIGNAL_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('close', 'Close Position')
    ]
    
    provider = models.ForeignKey(SignalProvider, on_delete=models.CASCADE)
    trading_pair = models.ForeignKey('trading.TradingPair', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    timeframe = models.CharField(max_length=20)  # 1h, 4h, 1d, etc.
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    analysis = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('hit_tp', 'Take Profit Hit'),
            ('hit_sl', 'Stop Loss Hit'),
            ('closed', 'Manually Closed'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class SignalNotification(models.Model):
    """Track signal notifications sent to users"""
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acted_on = models.BooleanField(default=False)
```

### 2.7 Loan Management

```python
# loans/models.py
from django.db import models
from decimal import Decimal

class LoanProduct(models.Model):
    """Available loan products"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Annual %
    term_days = models.IntegerField()
    collateral_ratio = models.DecimalField(max_digits=5, decimal_places=2)  # %
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    """User loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_days = models.IntegerField()
    collateral_amount = models.DecimalField(max_digits=20, decimal_places=2)
    collateral_currency = models.CharField(max_length=10)
    outstanding_balance = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_loans'
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    repaid_at = models.DateTimeField(null=True, blank=True)

class LoanRepayment(models.Model):
    """Loan repayment transactions"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.ForeignKey('funds.Transaction', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2.8 Referral System

```python
# referrals/models.py
from django.db import models

class ReferralTier(models.Model):
    """Referral reward tiers"""
    name = models.CharField(max_length=100)
    min_referrals = models.IntegerField()
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferralReward(models.Model):
    """Track referral rewards"""
    referrer = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_rewards'
    )
    referred_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_source'
    )
    reward_type = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'Signup Bonus'),
            ('first_deposit', 'First Deposit Bonus'),
            ('trading_commission', 'Trading Commission')
        ]
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    transaction = models.ForeignKey(
        'funds.Transaction',
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

## 3. API Endpoints

### 3.1 Authentication
```
POST   /api/v1/auth/register/          - User registration
POST   /api/v1/auth/login/             - User login
POST   /api/v1/auth/logout/            - User logout
POST   /api/v1/auth/refresh/           - Refresh JWT token
POST   /api/v1/auth/password-reset/    - Request password reset
POST   /api/v1/auth/password-reset-confirm/ - Confirm password reset
GET    /api/v1/auth/me/                - Get current user
PATCH  /api/v1/auth/me/                - Update current user
```

### 3.2 KYC
```
POST   /api/v1/kyc/submit/             - Submit KYC documents
GET    /api/v1/kyc/status/             - Get KYC status
GET    /api/v1/kyc/pending/            - List pending KYC (admin)
POST   /api/v1/kyc/{id}/approve/       - Approve KYC (admin)
POST   /api/v1/kyc/{id}/reject/        - Reject KYC (admin)
```

### 3.3 Funds
```
GET    /api/v1/wallets/                - List user wallets
GET    /api/v1/wallets/{currency}/     - Get specific wallet
POST   /api/v1/deposits/               - Create deposit
GET    /api/v1/deposits/               - List deposits
POST   /api/v1/withdrawals/            - Request withdrawal
GET    /api/v1/withdrawals/            - List withdrawals
POST   /api/v1/transfers/              - Internal transfer
GET    /api/v1/transactions/           - Transaction history
```

### 3.4 Trading
```
GET    /api/v1/trading-pairs/          - List trading pairs
GET    /api/v1/market-data/{symbol}/   - Get market data
POST   /api/v1/orders/                 - Create order
GET    /api/v1/orders/                 - List orders
GET    /api/v1/orders/{id}/            - Get order details
DELETE /api/v1/orders/{id}/            - Cancel order
GET    /api/v1/trades/                 - Trade history
GET    /api/v1/positions/              - Open positions
POST   /api/v1/positions/{id}/close/   - Close position
```

### 3.5 Copy Trading
```
GET    /api/v1/traders/                - List master traders
GET    /api/v1/traders/{id}/           - Trader details
POST   /api/v1/copy-trading/subscribe/ - Subscribe to trader
DELETE /api/v1/copy-trading/subscribe/{id}/ - Unsubscribe
GET    /api/v1/copy-trading/subscriptions/ - My subscriptions
PATCH  /api/v1/copy-trading/subscriptions/{id}/ - Update subscription
GET    /api/v1/copy-trading/performance/ - Copy trading performance
```

### 3.6 AI Bots
```
GET    /api/v1/bots/                   - List bots
POST   /api/v1/bots/                   - Create bot
GET    /api/v1/bots/{id}/              - Bot details
PATCH  /api/v1/bots/{id}/              - Update bot
DELETE /api/v1/bots/{id}/              - Delete bot
POST   /api/v1/bots/{id}/start/        - Start bot
POST   /api/v1/bots/{id}/stop/         - Stop bot
GET    /api/v1/bots/{id}/performance/  - Bot performance
GET    /api/v1/bot-strategies/         - Available strategies
```

### 3.7 Signals
```
GET    /api/v1/signal-providers/       - List providers
GET    /api/v1/signal-plans/           - Available plans
POST   /api/v1/signal-subscriptions/   - Subscribe to plan
GET    /api/v1/signal-subscriptions/   - My subscriptions
DELETE /api/v1/signal-subscriptions/{id}/ - Cancel subscription
GET    /api/v1/signals/                - My signals
GET    /api/v1/signals/{id}/           - Signal details
POST   /api/v1/signals/{id}/execute/   - Execute signal
```

### 3.8 Loans
```
GET    /api/v1/loan-products/          - Available products
POST   /api/v1/loans/                  - Apply for loan
GET    /api/v1/loans/                  - My loans
GET    /api/v1/loans/{id}/             - Loan details
POST   /api/v1/loans/{id}/repay/       - Make repayment
GET    /api/v1/loans/pending/          - Pending loans (admin)
POST   /api/v1/loans/{id}/approve/     - Approve loan (admin)
POST   /api/v1/loans/{id}/reject/      - Reject loan (admin)
```

### 3.9 Referrals
```
GET    /api/v1/referrals/code/         - Get referral code
GET    /api/v1/referrals/stats/        - Referral statistics
GET    /api/v1/referrals/rewards/      - Referral rewards
GET    /api/v1/referrals/referred-users/ - List referred users
```

## 4. Implementation Details

### 4.1 Market Data Integration

```python
# trading/services/market_service.py
import ccxt
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

class MarketDataService:
    """Service for fetching real-time market data"""
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET_KEY,
            'enableRateLimit': True,
        })
    
    def get_ticker(self, symbol):
        """Get current ticker data"""
        cache_key = f'ticker:{symbol}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        ticker = self.exchange.fetch_ticker(symbol)
        data = {
            'symbol': symbol,
            'last_price': Decimal(str(ticker['last'])),
            'bid': Decimal(str(ticker['bid'])),
            'ask': Decimal(str(ticker['ask'])),
            'volume': Decimal(str(ticker['volume'])),
            'change_24h': Decimal(str(ticker['percentage'])),
            'high_24h': Decimal(str(ticker['high'])),
            'low_24h': Decimal(str(ticker['low'])),
        }
        
        cache.set(cache_key, data, timeout=5)  # 5 seconds cache
        return data
    
    def get_orderbook(self, symbol, limit=20):
        """Get order book"""
        orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
        return {
            'bids': orderbook['bids'],
            'asks': orderbook['asks'],
        }
    
    def get_historical_data(self, symbol, timeframe='1h', limit=100):
        """Get historical OHLCV data"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [{
            'timestamp': candle[0],
            'open': Decimal(str(candle[1])),
            'high': Decimal(str(candle[2])),
            'low': Decimal(str(candle[3])),
            'close': Decimal(str(candle[4])),
            'volume': Decimal(str(candle[5])),
        } for candle in ohlcv]
```

### 4.2 Order Execution Engine

```python
# trading/services/order_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from trading.models import Order, Trade, Position
from funds.models import Wallet, Transaction
from trading.services.market_service import MarketDataService

class OrderExecutionService:
    """Handle order execution and position management"""
    
    def __init__(self):
        self.market_service = MarketDataService()
    
    @transaction.atomic
    def create_order(self, user, order_data):
        """Create and validate a new order"""
        trading_pair = order_data['trading_pair']
        side = order_data['side']
        quantity = Decimal(str(order_data['quantity']))
        
        # Validate user has sufficient balance
        if side == 'buy':
            required_balance = self._calculate_required_balance(
                trading_pair, quantity, order_data.get('price')
            )
            wallet = Wallet.objects.get(
                user=user,
                currency=trading_pair.quote_currency
            )
            if wallet.balance < required_balance:
                raise ValueError("Insufficient balance")
            
            # Lock the funds
            wallet.balance -= required_balance
            wallet.locked_balance += required_balance
            wallet.save()
        else:  # sell
            # Check if user has the asset
            wallet = Wallet.objects.get(
                user=user,
                currency=trading_pair.base_currency
            )
            if wallet.balance < quantity:
                raise ValueError("Insufficient asset balance")
            
            wallet.balance -= quantity
            wallet.locked_balance += quantity
            wallet.save()
        
        # Create the order
        order = Order.objects.create(
            user=user,
            **order_data,
            status='open'
        )
        
        # Execute market orders immediately
        if order.order_type == 'market':
            self._execute_market_order(order)
        
        return order
    
    def _execute_market_order(self, order):
        """Execute a market order"""
        ticker = self.market_service.get_ticker(
            order.trading_pair.symbol
        )
        
        execution_price = ticker['ask'] if order.side == 'buy' else ticker['bid']
        fee = self._calculate_fee(order, execution_price)
        
        # Create trade record
        trade = Trade.objects.create(
            order=order,
            quantity=order.quantity,
            price=execution_price,
            fee=fee,
            executed_at=timezone.now()
        )
        
        # Update order status
        order.filled_quantity = order.quantity
        order.average_price = execution_price
        order.fee = fee
        order.status = 'filled'
        order.executed_at = timezone.now()
        order.save()
        
        # Update user wallets
        self._settle_trade(order, trade)
        
        # Update or create position
        self._update_position(order)
    
    @transaction.atomic
    def _settle_trade(self, order, trade):
        """Settle the trade in user wallets"""
        user = order.user
        trading_pair = order.trading_pair
        
        if order.side == 'buy':
            # Unlock quote currency
            quote_wallet = Wallet.objects.select_for_update().get(
                user=user,
                currency=trading_pair.quote_currency
            )
            cost = trade.quantity * trade.price + trade.fee
            quote_wallet.locked_balance -= cost
            quote_wallet.save()
            
            # Add base currency
            base_wallet, _ = Wallet.objects.get_or_create(
                user=user,
                currency=trading_pair.base_currency
            )
            base_wallet.balance += trade.quantity
            base_wallet.save()
        else:  # sell
            # Unlock base currency
            base_wallet = Wallet.objects.select_for_update().get(
                user=user,
                currency=trading_pair.base_currency
            )
            base_wallet.locked_balance -= trade.quantity
            base_wallet.save()
            
            # Add quote currency
            quote_wallet, _ = Wallet.objects.get_or_create(
                user=user,
                currency=trading_pair.quote_currency
            )
            proceeds = trade.quantity * trade.price - trade.fee
            quote_wallet.balance += proceeds
            quote_wallet.save()
        
        # Create transaction record
        Transaction.objects.create(
            user=user,
            transaction_type='trade',
            currency=trading_pair.quote_currency,
            amount=trade.quantity * trade.price,
            fee=trade.fee,
            status='completed',
            reference_id=f'TRADE-{trade.id}',
            completed_at=timezone.now()
        )
    
    def _calculate_fee(self, order, price):
        """Calculate trading fee"""
        trading_pair = order.trading_pair
        return (order.quantity * price * 
                trading_pair.trading_fee_percentage / 100)
    
    def _calculate_required_balance(self, trading_pair, quantity, price=None):
        """Calculate required balance for an order"""
        if price is None:
            ticker = self.market_service.get_ticker(trading_pair.symbol)
            price = ticker['ask']
        
        cost = quantity * price
        fee = cost * trading_pair.trading_fee_percentage / 100
        return cost + fee
    
    def _update_position(self, order):
        """Update or create position after trade execution"""
        # Implementation for position tracking
        pass
```

### 4.3 Copy Trading Engine

```python
# copy_trading/services/copy_service.py
from decimal import Decimal
from django.db import transaction
from copy_trading.models import CopyTradingSubscription, CopiedTrade
from trading.services.order_service import OrderExecutionService

class CopyTradingService:
    """Service for executing copy trades"""
    
    def __init__(self):
        self.order_service = OrderExecutionService()
    
    def replicate_trade(self, master_order):
        """Replicate a master trader's order to all followers"""
        trader = master_order.user.trader
        
        # Get active subscribers
        subscriptions = CopyTradingSubscription.objects.filter(
            trader=trader,
            is_active=True
        ).select_related('follower')
        
        for subscription in subscriptions:
            try:
                self._copy_order_for_follower(master_order, subscription)
            except Exception as e:
                # Log error but continue with other followers
                print(f"Error copying trade for {subscription.follower}: {e}")
    
    @transaction.atomic
    def _copy_order_for_follower(self, master_order, subscription):
        """Copy an order for a specific follower"""
        follower = subscription.follower
        
        # Calculate position size based on follower's settings
        follower_quantity = self._calculate_follower_quantity(
            master_order,
            subscription
        )
        
        if follower_quantity <= 0:
            return
        
        # Create order data
        order_data = {
            'trading_pair': master_order.trading_pair,
            'order_type': master_order.order_type,
            'side': master_order.side,
            'quantity': follower_quantity,
            'price': master_order.price,
            'stop_price': master_order.stop_price,
            'source': 'copy_trade',
            'source_id': master_order.id
        }
        
        # Execute the order
        follower_order = self.order_service.create_order(
            follower,
            order_data
        )
        
        # Record the copied trade
        CopiedTrade.objects.create(
            subscription=subscription,
            master_order=master_order,
            follower_order=follower_order
        )
    
    def _calculate_follower_quantity(self, master_order, subscription):
        """Calculate appropriate quantity for follower"""
        # Get follower's available balance
        follower_wallet = subscription.follower.wallet_set.get(
            currency=master_order.trading_pair.quote_currency
        )
        
        # Calculate based on copy percentage
        max_allocation = (follower_wallet.balance * 
                         subscription.copy_percentage / 100)
        
        # Apply max position size if set
        if subscription.max_position_size:
            max_allocation = min(max_allocation, 
                               subscription.max_position_size)
        
        # Calculate quantity
        if master_order.price:
            quantity = max_allocation / master_order.price
        else:
            # Use current market price for market orders
            ticker = self.order_service.market_service.get_ticker(
                master_order.trading_pair.symbol
            )
            quantity = max_allocation / ticker['ask']
        
        return quantity
```

### 4.4 AI Bot Engine

```python
# bots/services/bot_engine.py
import numpy as np
import pandas as pd
from decimal import Decimal
from django.utils import timezone
from bots.models import TradingBot, BotTrade
from trading.services.order_service import OrderExecutionService
from trading.services.market_service import MarketDataService

class BotEngine:
    """Execute trading bot strategies"""
    
    def __init__(self, bot):
        self.bot = bot
        self.market_service = MarketDataService()
        self.order_service = OrderExecutionService()
    
    def run(self):
        """Execute bot trading logic"""
        if not self.bot.is_active:
            return
        
        # Check daily loss limit
        if self._check_daily_loss_limit():
            self.bot.is_active = False
            self.bot.save()
            return
        
        # Run strategy for each trading pair
        for trading_pair in self.bot.trading_pairs.all():
            try:
                signal = self._generate_signal(trading_pair)
                if signal:
                    self._execute_signal(signal, trading_pair)
            except Exception as e:
                print(f"Error running bot {self.bot.id}: {e}")
        
        self.bot.last_run_at = timezone.now()
        self.bot.save()
    
    def _generate_signal(self, trading_pair):
        """Generate trading signal based on strategy"""
        if self.bot.strategy == 'moving_average':
            return self._moving_average_strategy(trading_pair)
        elif self.bot.strategy == 'rsi':
            return self._rsi_strategy(trading_pair)
        elif self.bot.strategy == 'macd':
            return self._macd_strategy(trading_pair)
        # Add more strategies...
        return None
    
    def _moving_average_strategy(self, trading_pair):
        """Moving Average Crossover Strategy"""
        params = self.bot.parameters
        short_period = params.get('short_period', 20)
        long_period = params.get('long_period', 50)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=long_period + 10
        )
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(historical_data)
        
        # Calculate moving averages
        df['sma_short'] = df['close'].rolling(window=short_period).mean()
        df['sma_long'] = df['close'].rolling(window=long_period).mean()
        
        # Get last two rows to detect crossover
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish crossover
        if (previous['sma_short'] <= previous['sma_long'] and 
            current['sma_short'] > current['sma_long']):
            return {
                'action': 'buy',
                'price': current['close'],
                'reason': 'MA Bullish Crossover'
            }
        
        # Bearish crossover
        elif (previous['sma_short'] >= previous['sma_long'] and 
              current['sma_short'] < current['sma_long']):
            return {
                'action': 'sell',
                'price': current['close'],
                'reason': 'MA Bearish Crossover'
            }
        
        return None
    
    def _rsi_strategy(self, trading_pair):
        """RSI Strategy"""
        params = self.bot.parameters
        period = params.get('rsi_period', 14)
        oversold = params.get('oversold_level', 30)
        overbought = params.get('overbought_level', 70)
        
        # Get historical data
        historical_data = self.market_service.get_historical_data(
            trading_pair.symbol,
            timeframe='1h',
            limit=period + 10
        )
        
        df = pd.DataFrame(historical_data)
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Buy signal
        if current_rsi < oversold:
            return {
                'action': 'buy',
                'price': current_price,
                'reason': f'RSI Oversold: {current_rsi:.2f}'
            }
        
        # Sell signal
        elif current_rsi > overbought:
            return {
                'action': 'sell',
                'price': current_price,
                'reason': f'RSI Overbought: {current_rsi:.2f}'
            }
        
        return None
    
    def _execute_signal(self, signal, trading_pair):
        """Execute trading signal"""
        # Calculate position size
        quantity = self._calculate_position_size(trading_pair, signal['price'])
        
        if quantity <= 0:
            return
        
        # Create order
        order_data = {
            'trading_pair': trading_pair,
            'order_type': 'market',
            'side': signal['action'],
            'quantity': quantity,
            'source': 'bot',
            'source_id': self.bot.id
        }
        
        # Add stop loss and take profit
        if signal['action'] == 'buy':
            order_data['stop_price'] = (
                signal['price'] * (1 - self.bot.stop_loss_percentage / 100)
            )
        
        try:
            order = self.order_service.create_order(
                self.bot.user,
                order_data
            )
            
            # Record bot trade
            BotTrade.objects.create(
                bot=self.bot,
                order=order,
                signal_data=signal
            )
            
            # Update bot statistics
            self.bot.total_trades += 1
            self.bot.save()
            
        except Exception as e:
            print(f"Error executing bot signal: {e}")
    
    def _calculate_position_size(self, trading_pair, price):
        """Calculate position size based on risk management"""
        wallet = self.bot.user.wallet_set.get(
            currency=trading_pair.quote_currency
        )
        
        # Use configured max position size
        max_allocation = min(
            wallet.balance * Decimal('0.1'),  # Max 10% per trade
            self.bot.max_position_size
        )
        
        return max_allocation / Decimal(str(price))
    
    def _check_daily_loss_limit(self):
        """Check if daily loss limit exceeded"""
        today = timezone.now().date()
        
        # Calculate today's P&L
        today_trades = BotTrade.objects.filter(
            bot=self.bot,
            created_at__date=today
        ).select_related('order')
        
        total_pnl = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.order.price)
            for trade in today_trades
            if trade.order.status == 'filled'
        )
        
        return total_pnl < -self.bot.max_daily_loss
```

### 4.5 Signal Notification System

```python
# signals/services/notification_service.py
from django.core.mail import send_mail
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from signals.models import SignalNotification, SignalSubscription

class SignalNotificationService:
    """Send trading signals to subscribed users"""
    
    def notify_subscribers(self, signal):
        """Send signal to all active subscribers"""
        # Get active subscriptions for this provider
        subscriptions = SignalSubscription.objects.filter(
            plan__provider=signal.provider,
            status='active',
            expires_at__gt=timezone.now()
        ).select_related('user')
        
        for subscription in subscriptions:
            # Check if signal's trading pair is in plan
            if signal.trading_pair in subscription.plan.trading_pairs.all():
                self._send_notification(subscription.user, signal)
    
    def _send_notification(self, user, signal):
        """Send notification to a specific user"""
        # Create notification record
        notification = SignalNotification.objects.create(
            signal=signal,
            user=user
        )
        
        # Send via WebSocket
        self._send_websocket(user, signal)
        
        # Send email if user has email notifications enabled
        if user.profile.email_notifications:
            self._send_email(user, signal)
        
        # Send push notification if mobile app
        if user.profile.push_notifications:
            self._send_push(user, signal)
    
    def _send_websocket(self, user, signal):
        """Send real-time WebSocket notification"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}',
            {
                'type': 'trading_signal',
                'signal': {
                    'id': signal.id,
                    'trading_pair': signal.trading_pair.symbol,
                    'type': signal.signal_type,
                    'entry_price': str(signal.entry_price),
                    'stop_loss': str(signal.stop_loss),
                    'take_profit': str(signal.take_profit),
                    'confidence': str(signal.confidence),
                    'analysis': signal.analysis
                }
            }
        )
    
    def _send_email(self, user, signal):
        """Send email notification"""
        subject = f'New Trading Signal: {signal.trading_pair.symbol}'
        message = f"""
        New {signal.signal_type.upper()} signal for {signal.trading_pair.symbol}
        
        Entry Price: {signal.entry_price}
        Stop Loss: {signal.stop_loss}
        Take Profit: {signal.take_profit}
        Confidence: {signal.confidence}%
        
        Analysis:
        {signal.analysis}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )
```

### 4.6 Celery Tasks

```python
# tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def update_market_prices():
    """Update market prices for all active trading pairs"""
    from trading.models import TradingPair
    from trading.services.market_service import MarketDataService
    
    market_service = MarketDataService()
    active_pairs = TradingPair.objects.filter(is_active=True)
    
    for pair in active_pairs:
        try:
            ticker = market_service.get_ticker(pair.symbol)
            # Update cached prices or database as needed
        except Exception as e:
            print(f"Error updating {pair.symbol}: {e}")

@shared_task
def execute_pending_orders():
    """Check and execute pending limit orders"""
    from trading.models import Order
    from trading.services.order_service import OrderExecutionService
    
    order_service = OrderExecutionService()
    pending_orders = Order.objects.filter(
        status='open',
        order_type__in=['limit', 'stop_loss', 'take_profit']
    )
    
    for order in pending_orders:
        try:
            order_service.check_and_execute_order(order)
        except Exception as e:
            print(f"Error executing order {order.id}: {e}")

@shared_task
def run_trading_bots():
    """Execute all active trading bots"""
    from bots.models import TradingBot
    from bots.services.bot_engine import BotEngine
    
    active_bots = TradingBot.objects.filter(
        is_active=True,
        is_paper_trading=False
    )
    
    for bot in active_bots:
        try:
            engine = BotEngine(bot)
            engine.run()
        except Exception as e:
            print(f"Error running bot {bot.id}: {e}")

@shared_task
def process_copy_trades():
    """Process copy trading orders"""
    from trading.models import Order
    from copy_trading.services.copy_service import CopyTradingService
    
    copy_service = CopyTradingService()
    
    # Get recently filled orders from master traders
    recent_orders = Order.objects.filter(
        status='filled',
        user__trader__isnull=False,
        executed_at__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(
        source='copy_trade'  # Don't copy already copied trades
    )
    
    for order in recent_orders:
        copy_service.replicate_trade(order)

@shared_task
def calculate_loan_interest():
    """Calculate and apply interest to active loans"""
    from loans.models import Loan
    from decimal import Decimal
    
    active_loans = Loan.objects.filter(status='active')
    
    for loan in active_loans:
        # Calculate daily interest
        daily_rate = loan.interest_rate / 365 / 100
        interest = loan.outstanding_balance * Decimal(str(daily_rate))
        
        loan.outstanding_balance += interest
        loan.save()

@shared_task
def process_referral_rewards():
    """Process referral rewards for completed actions"""
    from referrals.models import ReferralReward
    from funds.models import Transaction, Wallet
    
    # Process pending rewards
    pending_rewards = ReferralReward.objects.filter(
        transaction__isnull=True
    )
    
    for reward in pending_rewards:
        try:
            # Credit wallet
            wallet, _ = Wallet.objects.get_or_create(
                user=reward.referrer,
                currency=reward.currency
            )
            wallet.balance += reward.amount
            wallet.save()
            
            # Create transaction
            transaction = Transaction.objects.create(
                user=reward.referrer,
                transaction_type='referral_bonus',
                currency=reward.currency,
                amount=reward.amount,
                status='completed',
                reference_id=f'REF-{reward.id}',
                completed_at=timezone.now()
            )
            
            reward.transaction = transaction
            reward.save()
        except Exception as e:
            print(f"Error processing reward {reward.id}: {e}")

@shared_task
def check_kyc_expiry():
    """Check for expired KYC documents"""
    from users.models import User, KYCDocument
    from datetime import timedelta
    
    # KYC documents older than 2 years need reverification
    expiry_date = timezone.now() - timedelta(days=730)
    
    expired_kyc = KYCDocument.objects.filter(
        submitted_at__lt=expiry_date,
        user__kyc_status='approved'
    )
    
    for kyc in expired_kyc:
        kyc.user.kyc_status = 'not_submitted'
        kyc.user.save()
        # Send notification to user
```

## 5. API Views

### 5.1 Trading Views

```python
# trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from trading.models import Order, TradingPair, Position
from trading.serializers import (
    OrderSerializer, TradingPairSerializer, PositionSerializer
)
from trading.services.order_service import OrderExecutionService

class TradingPairViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading pairs endpoints"""
    queryset = TradingPair.objects.filter(is_active=True)
    serializer_class = TradingPairSerializer
    
    @action(detail=True, methods=['get'])
    def market_data(self, request, pk=None):
        """Get real-time market data"""
        trading_pair = self.get_object()
        market_service = MarketDataService()
        
        data = market_service.get_ticker(trading_pair.symbol)
        return Response(data)

class OrderViewSet(viewsets.ModelViewSet):
    """Order management endpoints"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Create a new order"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_service = OrderExecutionService()
        
        try:
            order = order_service.create_order(
                request.user,
                serializer.validated_data
            )
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an open order"""
        order = self.get_object()
        
        if order.status not in ['open', 'partially_filled']:
            return Response(
                {'error': 'Order cannot be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        # Unlock funds
        # Implementation here...
        
        return Response(OrderSerializer(order).data)

class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """Position management endpoints"""
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Position.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a position"""
        position = self.get_object()
        
        # Create closing order
        order_service = OrderExecutionService()
        order_data = {
            'trading_pair': position.trading_pair,
            'order_type': 'market',
            'side': 'sell' if position.side == 'long' else 'buy',
            'quantity': position.quantity
        }
        
        order = order_service.create_order(request.user, order_data)
        
        return Response({
            'message': 'Position closed',
            'order': OrderSerializer(order).data
        })
```

## 6. Django Templates & jQuery Integration

Since you're using Django full-stack without a separate frontend, here's how to integrate the APIs with jQuery:

### 6.1 Base Template Setup

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Trading Platform{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'home' %}">Trading Platform</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    {% if user.is_authenticated %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'dashboard' %}">Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'trading' %}">Trading</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'wallets' %}">Wallets</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'bots' %}">Bots</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'signals' %}">Signals</a></li>
                        <li class="nav-item">
                            <span class="nav-link">Balance: $<span id="total-balance">0.00</span></span>
                        </li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'logout' %}">Logout</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'login' %}">Login</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'register' %}">Register</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="container mt-4">
        {% if messages %}
            <div id="messages">
                {% for message in messages %}
                    <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </main>

    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- API Helper -->
    <script>
        // CSRF Token setup for Django
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        
        const csrftoken = getCookie('csrftoken');
        
        // Setup jQuery AJAX defaults
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                    // Only send the token to relative URLs i.e. locally.
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                }
            }
        });
        
        // API Helper functions
        const API = {
            baseUrl: '/api/v1',
            
            // Generic request method
            request: function(method, endpoint, data = null) {
                return $.ajax({
                    url: this.baseUrl + endpoint,
                    method: method,
                    data: data ? JSON.stringify(data) : null,
                    contentType: 'application/json',
                    dataType: 'json'
                });
            },
            
            get: function(endpoint) {
                return this.request('GET', endpoint);
            },
            
            post: function(endpoint, data) {
                return this.request('POST', endpoint, data);
            },
            
            patch: function(endpoint, data) {
                return this.request('PATCH', endpoint, data);
            },
            
            delete: function(endpoint) {
                return this.request('DELETE', endpoint);
            },
            
            // Show message helper
            showMessage: function(message, type = 'success') {
                const alertHtml = `
                    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                        ${message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                `;
                $('#messages').html(alertHtml);
                
                // Auto-dismiss after 5 seconds
                setTimeout(function() {
                    $('.alert').alert('close');
                }, 5000);
            },
            
            // Error handler
            handleError: function(xhr) {
                let message = 'An error occurred';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    message = xhr.responseJSON.error;
                } else if (xhr.responseJSON) {
                    message = JSON.stringify(xhr.responseJSON);
                }
                this.showMessage(message, 'danger');
            }
        };
    </script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### 6.2 Trading Page with jQuery

```html
<!-- templates/trading/trading.html -->
{% extends 'base.html' %}

{% block title %}Trading - Platform{% endblock %}

{% block content %}
<div class="row">
    <!-- Trading Pairs List -->
    <div class="col-md-3">
        <div class="card">
            <div class="card-header">
                <h5>Trading Pairs</h5>
                <input type="text" id="pair-search" class="form-control form-control-sm mt-2" placeholder="Search...">
            </div>
            <div class="card-body p-0">
                <div id="trading-pairs-list" class="list-group list-group-flush" style="max-height: 600px; overflow-y: auto;">
                    <!-- Pairs will be loaded here -->
                </div>
            </div>
        </div>
    </div>
    
    <!-- Chart & Order Form -->
    <div class="col-md-6">
        <div class="card mb-3">
            <div class="card-header">
                <h5 id="current-pair">Select a trading pair</h5>
                <div class="d-flex justify-content-between align-items-center mt-2">
                    <div>
                        <span class="text-muted">Price:</span>
                        <strong id="current-price">$0.00</strong>
                    </div>
                    <div>
                        <span class="text-muted">24h Change:</span>
                        <strong id="price-change" class="text-success">+0.00%</strong>
                    </div>
                    <div>
                        <span class="text-muted">Volume:</span>
                        <strong id="volume">0</strong>
                    </div>
                </div>
            </div>
            <div class="card-body">
                <!-- TradingView Chart or custom chart -->
                <div id="price-chart" style="height: 400px; background: #f8f9fa;">
                    <p class="text-center pt-5">Chart will be displayed here</p>
                </div>
            </div>
        </div>
        
        <!-- Order Form -->
        <div class="card">
            <div class="card-header">
                <ul class="nav nav-tabs card-header-tabs" role="tablist">
                    <li class="nav-item">
                        <a class="nav-link active" data-bs-toggle="tab" href="#buy-tab">Buy</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-bs-toggle="tab" href="#sell-tab">Sell</a>
                    </li>
                </ul>
            </div>
            <div class="card-body">
                <div class="tab-content">
                    <!-- Buy Tab -->
                    <div class="tab-pane fade show active" id="buy-tab">
                        <form id="buy-form">
                            <div class="mb-3">
                                <label class="form-label">Order Type</label>
                                <select class="form-select" id="buy-order-type">
                                    <option value="market">Market</option>
                                    <option value="limit">Limit</option>
                                </select>
                            </div>
                            <div class="mb-3 limit-price-group" style="display: none;">
                                <label class="form-label">Price</label>
                                <input type="number" class="form-control" id="buy-price" step="0.01">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Amount</label>
                                <input type="number" class="form-control" id="buy-amount" step="0.00000001" required>
                                <small class="text-muted">Available: <span id="buy-available">0</span> USD</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Total</label>
                                <input type="number" class="form-control" id="buy-total" readonly>
                            </div>
                            <button type="submit" class="btn btn-success w-100">Buy</button>
                        </form>
                    </div>
                    
                    <!-- Sell Tab -->
                    <div class="tab-pane fade" id="sell-tab">
                        <form id="sell-form">
                            <div class="mb-3">
                                <label class="form-label">Order Type</label>
                                <select class="form-select" id="sell-order-type">
                                    <option value="market">Market</option>
                                    <option value="limit">Limit</option>
                                </select>
                            </div>
                            <div class="mb-3 limit-price-group" style="display: none;">
                                <label class="form-label">Price</label>
                                <input type="number" class="form-control" id="sell-price" step="0.01">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Amount</label>
                                <input type="number" class="form-control" id="sell-amount" step="0.00000001" required>
                                <small class="text-muted">Available: <span id="sell-available">0</span> BTC</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Total</label>
                                <input type="number" class="form-control" id="sell-total" readonly>
                            </div>
                            <button type="submit" class="btn btn-danger w-100">Sell</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Order Book & Recent Trades -->
    <div class="col-md-3">
        <div class="card mb-3">
            <div class="card-header">
                <h6>Order Book</h6>
            </div>
            <div class="card-body p-0">
                <div id="order-book" style="max-height: 300px; overflow-y: auto;">
                    <!-- Order book will be loaded here -->
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h6>Recent Trades</h6>
            </div>
            <div class="card-body p-0">
                <div id="recent-trades" style="max-height: 300px; overflow-y: auto;">
                    <!-- Recent trades will be loaded here -->
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Open Orders -->
<div class="row mt-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5>Open Orders</h5>
            </div>
            <div class="card-body">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Pair</th>
                            <th>Type</th>
                            <th>Side</th>
                            <th>Price</th>
                            <th>Amount</th>
                            <th>Filled</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="open-orders">
                        <!-- Orders will be loaded here -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
$(document).ready(function() {
    let currentPair = null;
    let currentPrice = 0;
    
    // Load trading pairs
    function loadTradingPairs() {
        API.get('/trading-pairs/')
            .done(function(data) {
                const pairsList = $('#trading-pairs-list');
                pairsList.empty();
                
                data.forEach(function(pair) {
                    const pairHtml = `
                        <a href="#" class="list-group-item list-group-item-action pair-item" data-pair-id="${pair.id}" data-symbol="${pair.symbol}">
                            <div class="d-flex justify-content-between">
                                <strong>${pair.symbol}</strong>
                                <span class="price-${pair.id}">$0.00</span>
                            </div>
                        </a>
                    `;
                    pairsList.append(pairHtml);
                });
                
                // Select first pair by default
                if (data.length > 0) {
                    selectPair(data[0].id, data[0].symbol);
                }
            })
            .fail(API.handleError);
    }
    
    // Select trading pair
    function selectPair(pairId, symbol) {
        currentPair = pairId;
        $('#current-pair').text(symbol);
        
        // Highlight selected pair
        $('.pair-item').removeClass('active');
        $(`.pair-item[data-pair-id="${pairId}"]`).addClass('active');
        
        // Load market data
        loadMarketData(pairId);
        
        // Load order book
        loadOrderBook(symbol);
        
        // Load user balances
        loadBalances(symbol);
    }
    
    // Load market data
    function loadMarketData(pairId) {
        API.get(`/trading-pairs/${pairId}/market_data/`)
            .done(function(data) {
                currentPrice = parseFloat(data.last_price);
                $('#current-price').text(' + currentPrice.toFixed(2));
                $('#price-change').text(data.change_24h + '%')
                    .removeClass('text-success text-danger')
                    .addClass(data.change_24h >= 0 ? 'text-success' : 'text-danger');
                $('#volume').text(parseFloat(data.volume).toFixed(2));
            });
    }
    
    // Load order book
    function loadOrderBook(symbol) {
        // This would call your backend which calls the market API
        // For now, placeholder
        $('#order-book').html('<p class="text-center text-muted p-3">Loading...</p>');
    }
    
    // Load user balances
    function loadBalances(symbol) {
        API.get('/wallets/')
            .done(function(data) {
                // Update available balances for buy/sell
                const usdWallet = data.find(w => w.currency === 'USD');
                const baseWallet = data.find(w => w.currency === symbol.split('/')[0]);
                
                if (usdWallet) {
                    $('#buy-available').text(parseFloat(usdWallet.balance).toFixed(2));
                }
                if (baseWallet) {
                    $('#sell-available').text(parseFloat(baseWallet.balance).toFixed(8));
                }
            });
    }
    
    // Load open orders
    function loadOpenOrders() {
        API.get('/orders/?status=open')
            .done(function(data) {
                const tbody = $('#open-orders');
                tbody.empty();
                
                if (data.length === 0) {
                    tbody.html('<tr><td colspan="9" class="text-center text-muted">No open orders</td></tr>');
                    return;
                }
                
                data.forEach(function(order) {
                    const row = `
                        <tr>
                            <td>${new Date(order.created_at).toLocaleString()}</td>
                            <td>${order.trading_pair.symbol}</td>
                            <td>${order.order_type}</td>
                            <td><span class="badge bg-${order.side === 'buy' ? 'success' : 'danger'}">${order.side}</span></td>
                            <td>${parseFloat(order.price).toFixed(2)}</td>
                            <td>${parseFloat(order.quantity).toFixed(8)}</td>
                            <td>${parseFloat(order.filled_quantity).toFixed(8)}</td>
                            <td><span class="badge bg-warning">${order.status}</span></td>
                            <td>
                                <button class="btn btn-sm btn-danger cancel-order" data-order-id="${order.id}">Cancel</button>
                            </td>
                        </tr>
                    `;
                    tbody.append(row);
                });
            });
    }
    
    // Handle order type change
    $('#buy-order-type, #sell-order-type').on('change', function() {
        const form = $(this).closest('form');
        if ($(this).val() === 'limit') {
            form.find('.limit-price-group').show();
        } else {
            form.find('.limit-price-group').hide();
        }
    });
    
    // Calculate total
    $('#buy-amount, #buy-price').on('input', function() {
        const amount = parseFloat($('#buy-amount').val()) || 0;
        const price = $('#buy-order-type').val() === 'market' 
            ? currentPrice 
            : (parseFloat($('#buy-price').val()) || 0);
        $('#buy-total').val((amount * price).toFixed(2));
    });
    
    $('#sell-amount, #sell-price').on('input', function() {
        const amount = parseFloat($('#sell-amount').val()) || 0;
        const price = $('#sell-order-type').val() === 'market' 
            ? currentPrice 
            : (parseFloat($('#sell-price').val()) || 0);
        $('#sell-total').val((amount * price).toFixed(2));
    });
    
    // Handle buy form submission
    $('#buy-form').on('submit', function(e) {
        e.preventDefault();
        
        const orderData = {
            trading_pair: currentPair,
            order_type: $('#buy-order-type').val(),
            side: 'buy',
            quantity: $('#buy-amount').val(),
            price: $('#buy-order-type').val() === 'limit' ? $('#buy-price').val() : null
        };
        
        API.post('/orders/', orderData)
            .done(function(data) {
                API.showMessage('Buy order placed successfully!', 'success');
                $('#buy-form')[0].reset();
                loadOpenOrders();
                loadBalances($('#current-pair').text());
            })
            .fail(API.handleError);
    });
    
    // Handle sell form submission
    $('#sell-form').on('submit', function(e) {
        e.preventDefault();
        
        const orderData = {
            trading_pair: currentPair,
            order_type: $('#sell-order-type').val(),
            side: 'sell',
            quantity: $('#sell-amount').val(),
            price: $('#sell-order-type').val() === 'limit' ? $('#sell-price').val() : null
        };
        
        API.post('/orders/', orderData)
            .done(function(data) {
                API.showMessage('Sell order placed successfully!', 'success');
                $('#sell-form')[0].reset();
                loadOpenOrders();
                loadBalances($('#current-pair').text());
            })
            .fail(API.handleError);
    });
    
    // Handle order cancellation
    $(document).on('click', '.cancel-order', function() {
        const orderId = $(this).data('order-id');
        
        if (confirm('Are you sure you want to cancel this order?')) {
            API.post(`/orders/${orderId}/cancel/`)
                .done(function(data) {
                    API.showMessage('Order cancelled successfully!', 'success');
                    loadOpenOrders();
                })
                .fail(API.handleError);
        }
    });
    
    // Pair search
    $('#pair-search').on('input', function() {
        const search = $(this).val().toLowerCase();
        $('.pair-item').each(function() {
            const symbol = $(this).data('symbol').toLowerCase();
            $(this).toggle(symbol.includes(search));
        });
    });
    
    // Handle pair click
    $(document).on('click', '.pair-item', function(e) {
        e.preventDefault();
        const pairId = $(this).data('pair-id');
        const symbol = $(this).data('symbol');
        selectPair(pairId, symbol);
    });
    
    // Initialize
    loadTradingPairs();
    loadOpenOrders();
    
    // Refresh data periodically
    setInterval(function() {
        if (currentPair) {
            loadMarketData(currentPair);
        }
        loadOpenOrders();
    }, 5000);
});
</script>
{% endblock %}
```

Now let me complete the remaining backend components:

## 7. Serializers

### 7.1 User Serializers

```python
# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from users.models import User, KYCDocument

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 
                  'phone_number', 'is_verified', 'kyc_status', 'referral_code',
                  'created_at']
        read_only_fields = ['id', 'is_verified', 'kyc_status', 'referral_code', 
                           'created_at']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    referred_by_code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password_confirm', 
                  'first_name', 'last_name', 'phone_number', 'referred_by_code']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        # Generate unique referral code
        import random
        import string
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Handle referral
        referred_by = None
        if referred_by_code:
            try:
                referred_by = User.objects.get(referral_code=referred_by_code)
            except User.DoesNotExist:
                pass
        
        user = User.objects.create_user(
            **validated_data,
            referral_code=referral_code,
            referred_by=referred_by
        )
        
        return user

class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ['id', 'document_type', 'document_number', 'document_front',
                  'document_back', 'selfie', 'address_proof', 'date_of_birth',
                  'address', 'city', 'country', 'postal_code', 'submitted_at',
                  'rejection_reason']
        read_only_fields = ['id', 'submitted_at', 'rejection_reason']
```

### 7.2 Trading Serializers

```python
# trading/serializers.py
from rest_framework import serializers
from trading.models import TradingPair, Order, Trade, Position

class TradingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingPair
        fields = ['id', 'symbol', 'base_currency', 'quote_currency', 
                  'market_type', 'is_active', 'min_order_size', 'max_order_size',
                  'price_precision', 'quantity_precision', 'trading_fee_percentage']

class OrderSerializer(serializers.ModelSerializer):
    trading_pair = serializers.PrimaryKeyRelatedField(
        queryset=TradingPair.objects.all()
    )
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'trading_pair', 'trading_pair_detail', 'order_type', 
                  'side', 'quantity', 'price', 'stop_price', 'filled_quantity',
                  'average_price', 'status', 'fee', 'source', 'created_at',
                  'updated_at', 'executed_at']
        read_only_fields = ['id', 'filled_quantity', 'average_price', 'status',
                           'fee', 'created_at', 'updated_at', 'executed_at']
    
    def validate(self, attrs):
        trading_pair = attrs['trading_pair']
        quantity = attrs['quantity']
        
        # Validate order size
        if quantity < trading_pair.min_order_size:
            raise serializers.ValidationError(
                f"Quantity must be at least {trading_pair.min_order_size}"
            )
        
        if quantity > trading_pair.max_order_size:
            raise serializers.ValidationError(
                f"Quantity must not exceed {trading_pair.max_order_size}"
            )
        
        # Validate price for limit orders
        if attrs['order_type'] == 'limit' and not attrs.get('price'):
            raise serializers.ValidationError("Price is required for limit orders")
        
        return attrs

class TradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = Trade
        fields = ['id', 'order', 'order_detail', 'quantity', 'price', 'fee',
                  'executed_at', 'external_trade_id']

class PositionSerializer(serializers.ModelSerializer):
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = Position
        fields = ['id', 'trading_pair', 'trading_pair_detail', 'side', 'quantity',
                  'entry_price', 'current_price', 'unrealized_pnl', 'leverage',
                  'stop_loss', 'take_profit', 'opened_at', 'updated_at']
```

### 7.3 Funds Serializers

```python
# funds/serializers.py
from rest_framework import serializers
from funds.models import Wallet, Transaction, Deposit, Withdrawal

class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = ['id', 'currency', 'balance', 'locked_balance', 
                  'available_balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'locked_balance', 'created_at', 
                           'updated_at']
    
    def get_available_balance(self, obj):
        return obj.balance - obj.locked_balance

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_type', 'currency', 'amount', 'fee', 
                  'status', 'reference_id', 'external_id', 'notes',
                  'created_at', 'completed_at']
        read_only_fields = ['id', 'status', 'reference_id', 'created_at', 
                           'completed_at']

class DepositSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    
    class Meta:
        model = Deposit
        fields = ['id', 'transaction', 'payment_method', 'payment_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='deposit',
            currency=validated_data.get('currency', 'USD'),
            amount=validated_data.get('amount'),
            status='pending',
            reference_id=f'DEP-{uuid.uuid4().hex[:12].upper()}'
        )
        
        # Create deposit record
        deposit = Deposit.objects.create(
            transaction=transaction,
            payment_method=validated_data['payment_method'],
            payment_details=validated_data['payment_details']
        )
        
        return deposit

class WithdrawalSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = ['id', 'transaction', 'destination_type', 'destination_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        amount = validated_data.get('amount')
        currency = validated_data.get('currency', 'USD')
        
        # Check balance
        wallet = Wallet.objects.get(user=user, currency=currency)
        if wallet.balance < amount:
            raise serializers.ValidationError("Insufficient balance")
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='withdrawal',
            currency=currency,
            amount=amount,
            status='pending',
            reference_id=f'WDR-{uuid.uuid4().hex[:12].upper()}'
        )
        
        # Lock funds
        wallet.balance -= amount
        wallet.locked_balance += amount
        wallet.save()
        
        # Create withdrawal record
        withdrawal = Withdrawal.objects.create(
            transaction=transaction,
            destination_type=validated_data['destination_type'],
            destination_details=validated_data['destination_details']
        )
        
        return withdrawal
```

### 7.4 Bot Serializers

```python
# bots/serializers.py
from rest_framework import serializers
from bots.models import TradingBot, BotTrade

class TradingBotSerializer(serializers.ModelSerializer):
    trading_pairs = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=TradingPair.objects.all()
    )
    win_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TradingBot
        fields = ['id', 'name', 'description', 'strategy', 'trading_pairs',
                  'is_active', 'is_paper_trading', 'max_position_size',
                  'stop_loss_percentage', 'take_profit_percentage',
                  'max_daily_loss', 'parameters', 'total_trades',
                  'winning_trades', 'total_profit', 'win_rate',
                  'created_at', 'updated_at', 'last_run_at']
        read_only_fields = ['id', 'total_trades', 'winning_trades', 
                           'total_profit', 'created_at', 'updated_at', 
                           'last_run_at']
    
    def get_win_rate(self, obj):
        if obj.total_trades == 0:
            return 0
        return (obj.winning_trades / obj.total_trades) * 100

class BotTradeSerializer(serializers.ModelSerializer):
    order_detail = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = BotTrade
        fields = ['id', 'bot', 'order', 'order_detail', 'signal_data', 
                  'created_at']
```

### 7.5 Copy Trading Serializers

```python
# copy_trading/serializers.py
from rest_framework import serializers
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade

class TraderSerializer(serializers.ModelSerializer):
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Trader
        fields = ['id', 'user', 'user_info', 'display_name', 'bio', 
                  'is_active', 'total_followers', 'total_profit',
                  'profit_percentage', 'win_rate', 'total_trades',
                  'risk_score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_followers', 'total_profit',
                           'profit_percentage', 'win_rate', 'total_trades',
                           'created_at', 'updated_at']

class CopyTradingSubscriptionSerializer(serializers.ModelSerializer):
    trader_detail = TraderSerializer(source='trader', read_only=True)
    
    class Meta:
        model = CopyTradingSubscription
        fields = ['id', 'trader', 'trader_detail', 'is_active', 
                  'copy_percentage', 'max_position_size',
                  'stop_loss_percentage', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        # Ensure user doesn't subscribe to themselves
        if attrs['trader'].user == self.context['request'].user:
            raise serializers.ValidationError("Cannot copy your own trades")
        
        return attrs

class CopiedTradeSerializer(serializers.ModelSerializer):
    subscription_detail = CopyTradingSubscriptionSerializer(
        source='subscription', 
        read_only=True
    )
    master_order_detail = OrderSerializer(source='master_order', read_only=True)
    follower_order_detail = OrderSerializer(source='follower_order', read_only=True)
    
    class Meta:
        model = CopiedTrade
        fields = ['id', 'subscription', 'subscription_detail', 'master_order',
                  'master_order_detail', 'follower_order', 'follower_order_detail',
                  'created_at']
```

### 7.6 Signals Serializers

```python
# signals/serializers.py
from rest_framework import serializers
from signals.models import (
    SignalProvider, SignalPlan, SignalSubscription, 
    TradingSignal, SignalNotification
)

class SignalProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignalProvider
        fields = ['id', 'name', 'description', 'provider_type', 'accuracy_rate',
                  'total_signals', 'is_active', 'created_at']

class SignalPlanSerializer(serializers.ModelSerializer):
    provider_detail = SignalProviderSerializer(source='provider', read_only=True)
    
    class Meta:
        model = SignalPlan
        fields = ['id', 'provider', 'provider_detail', 'name', 'description',
                  'price', 'duration_days', 'max_signals_per_day',
                  'trading_pairs', 'is_active', 'created_at']

class SignalSubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = SignalPlanSerializer(source='plan', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = SignalSubscription
        fields = ['id', 'plan', 'plan_detail', 'status', 'started_at',
                  'expires_at', 'auto_renew', 'days_remaining']
        read_only_fields = ['id', 'started_at', 'expires_at']
    
    def get_days_remaining(self, obj):
        from datetime import datetime
        if obj.expires_at:
            delta = obj.expires_at - datetime.now(obj.expires_at.tzinfo)
            return max(0, delta.days)
        return 0

class TradingSignalSerializer(serializers.ModelSerializer):
    provider_detail = SignalProviderSerializer(source='provider', read_only=True)
    trading_pair_detail = TradingPairSerializer(source='trading_pair', read_only=True)
    
    class Meta:
        model = TradingSignal
        fields = ['id', 'provider', 'provider_detail', 'trading_pair',
                  'trading_pair_detail', 'signal_type', 'entry_price',
                  'stop_loss', 'take_profit', 'timeframe', 'confidence',
                  'analysis', 'status', 'created_at', 'closed_at']

class SignalNotificationSerializer(serializers.ModelSerializer):
    signal_detail = TradingSignalSerializer(source='signal', read_only=True)
    
    class Meta:
        model = SignalNotification
        fields = ['id', 'signal', 'signal_detail', 'sent_at', 'read_at', 
                  'acted_on']
```

### 7.7 Loan Serializers

```python
# loans/serializers.py
from rest_framework import serializers
from loans.models import LoanProduct, Loan, LoanRepayment

class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = ['id', 'name', 'description', 'min_amount', 'max_amount',
                  'interest_rate', 'term_days', 'collateral_ratio',
                  'is_active', 'created_at']

class LoanSerializer(serializers.ModelSerializer):
    product_detail = LoanProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = Loan
        fields = ['id', 'product', 'product_detail', 'amount', 'interest_rate',
                  'term_days', 'collateral_amount', 'collateral_currency',
                  'outstanding_balance', 'status', 'applied_at', 'approved_at',
                  'disbursed_at', 'due_date', 'repaid_at']
        read_only_fields = ['id', 'interest_rate', 'outstanding_balance', 
                           'status', 'applied_at', 'approved_at', 'disbursed_at',
                           'due_date', 'repaid_at']
    
    def validate(self, attrs):
        product = attrs['product']
        amount = attrs['amount']
        
        if amount < product.min_amount or amount > product.max_amount:
            raise serializers.ValidationError(
                f"Amount must be between {product.min_amount} and {product.max_amount}"
            )
        
        # Calculate required collateral
        required_collateral = amount * product.collateral_ratio / 100
        if attrs['collateral_amount'] < required_collateral:
            raise serializers.ValidationError(
                f"Minimum collateral required: {required_collateral}"
            )
        
        return attrs

class LoanRepaymentSerializer(serializers.ModelSerializer):
    transaction_detail = TransactionSerializer(source='transaction', read_only=True)
    
    class Meta:
        model = LoanRepayment
        fields = ['id', 'loan', 'amount', 'principal_amount', 'interest_amount',
                  'transaction', 'transaction_detail', 'created_at']
        read_only_fields = ['id', 'principal_amount', 'interest_amount', 
                           'created_at']
```

## 8. Complete ViewSets

### 8.1 Authentication Views

```python
# users/views.py
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from users.serializers import (
    UserSerializer, UserRegistrationSerializer, KYCDocumentSerializer
)
from users.models import KYCDocument

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)

class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class KYCViewSet(viewsets.ModelViewSet):
    """KYC verification endpoints"""
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return KYCDocument.objects.all()
        return KYCDocument.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Submit KYC documents"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user already submitted KYC
        if KYCDocument.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'KYC already submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        kyc = serializer.save(user=request.user)
        request.user.kyc_status = 'pending'
        request.user.save()
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve KYC (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kyc = self.get_object()
        kyc.user.kyc_status = 'approved'
        kyc.user.is_verified = True
        kyc.user.save()
        
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.save()
        
        return Response({'message': 'KYC approved'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject KYC (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kyc = self.get_object()
        kyc.user.kyc_status = 'rejected'
        kyc.user.save()
        
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = request.data.get('reason', '')
        kyc.save()
        
        return Response({'message': 'KYC rejected'})
```

### 8.2 Funds Views

```python
# funds/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from funds.models import Wallet, Transaction, Deposit, Withdrawal
from funds.serializers import (
    WalletSerializer, TransactionSerializer, 
    DepositSerializer, WithdrawalSerializer
)

class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    """Wallet management endpoints"""
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Transaction history endpoints"""
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['transaction_type', 'currency', 'status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

class DepositViewSet(viewsets.ModelViewSet):
    """Deposit management endpoints"""
    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Deposit.objects.filter(transaction__user=self.request.user)

class WithdrawalViewSet(viewsets.ModelViewSet):
    """Withdrawal management endpoints"""
    serializer_class = WithdrawalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Withdrawal.objects.filter(transaction__user=self.request.user)
```

### 8.3 Bot Views

```python
# bots/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from bots.models import TradingBot, BotTrade
from bots.serializers import TradingBotSerializer, BotTradeSerializer
from bots.services.bot_engine import BotEngine

class TradingBotViewSet(viewsets.ModelViewSet):
    """Trading bot management endpoints"""
    serializer_class = TradingBotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return TradingBot.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a trading bot"""
        bot = self.get_object()
        
        if bot.is_active:
            return Response(
                {'error': 'Bot is already running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bot.is_active = True
        bot.save()
        
        return Response({'message': 'Bot started successfully'})
    
    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """Stop a trading bot"""
        bot = self.get_object()
        
        if not bot.is_active:
            return Response(
                {'error': 'Bot is not running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bot.is_active = False
        bot.save()
        
        return Response({'message': 'Bot stopped successfully'})
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get bot performance metrics"""
        bot = self.get_object()
        
        trades = BotTrade.objects.filter(bot=bot).select_related('order')
        
        # Calculate metrics
        total_profit = sum(
            trade.order.filled_quantity * 
            (trade.order.average_price - trade.signal_data.get('price', 0))
            for trade in trades
            if trade.order.status == 'filled'
        )
        
        return Response({
            'total_trades': bot.total_trades,
            'winning_trades': bot.winning_trades,
            'total_profit': bot.total_profit,
            'win_rate': (bot.winning_trades / bot.total_trades * 100) 
                       if bot.total_trades > 0 else 0,
            'recent_trades': BotTradeSerializer(trades[:10], many=True).data
        })

class BotTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Bot trade history endpoints"""
    serializer_class = BotTradeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BotTrade.objects.filter(bot__user=self.request.user)
```

### 8.4 Copy Trading Views

```python
# copy_trading/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from copy_trading.models import Trader, CopyTradingSubscription, CopiedTrade
from copy_trading.serializers import (
    TraderSerializer, CopyTradingSubscriptionSerializer, CopiedTradeSerializer
)

class TraderViewSet(viewsets.ReadOnlyModelViewSet):
    """Master trader listing endpoints"""
    serializer_class = TraderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Trader.objects.filter(is_active=True)
    filterset_fields = ['risk_score']
    ordering_fields = ['total_followers', 'profit_percentage', 'win_rate']
    ordering = ['-total_followers']

class CopyTradingSubscriptionViewSet(viewsets.ModelViewSet):
    """Copy trading subscription management"""
    serializer_class = CopyTradingSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CopyTradingSubscription.objects.filter(follower=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(follower=self.request.user)
        
        # Increment trader's follower count
        trader = serializer.validated_data['trader']
        trader.total_followers += 1
        trader.save()
    
    def perform_destroy(self, instance):
        # Decrement trader's follower count
        instance.trader.total_followers -= 1
        instance.trader.save()
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Get copy trading performance"""
        subscriptions = self.get_queryset().filter(is_active=True)
        
        total_profit = 0
        for sub in subscriptions:
            copied_trades = CopiedTrade.objects.filter(
                subscription=sub
            ).select_related('follower_order')
            
            for trade in copied_trades:
                if trade.follower_order.status == 'filled':
                    # Calculate profit
                    pass
        
        return Response({
            'active_subscriptions': subscriptions.count(),
            'total_profit': total_profit,
            'subscriptions': CopyTradingSubscriptionSerializer(
                subscriptions, many=True
            ).data
        })

class CopiedTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Copied trade history"""
    serializer_class = CopiedTradeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CopiedTrade.objects.filter(
            subscription__follower=self.request.user
        )
```

### 8.5 Signals Views

```python
# signals/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from signals.models import (
    SignalProvider, SignalPlan, SignalSubscription, 
    TradingSignal, SignalNotification
)
from signals.serializers import (
    SignalProviderSerializer, SignalPlanSerializer,
    SignalSubscriptionSerializer, TradingSignalSerializer,
    SignalNotificationSerializer
)
from trading.services.order_service import OrderExecutionService

class SignalProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """Signal provider listing"""
    serializer_class = SignalProviderSerializer
    permission_classes = [IsAuthenticated]
    queryset = SignalProvider.objects.filter(is_active=True)

class SignalPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Signal plan listing"""
    serializer_class = SignalPlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = SignalPlan.objects.filter(is_active=True)

class SignalSubscriptionViewSet(viewsets.ModelViewSet):
    """Signal subscription management"""
    serializer_class = SignalSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SignalSubscription.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Subscribe to a signal plan"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan = serializer.validated_data['plan']
        
        # Check if already subscribed
        if SignalSubscription.objects.filter(
            user=request.user,
            plan=plan,
            status='active'
        ).exists():
            return Response(
                {'error': 'Already subscribed to this plan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process payment (implementation depends on payment gateway)
        # For now, assume payment is successful
        
        # Create subscription
        expires_at = timezone.now() + timedelta(days=plan.duration_days)
        subscription = SignalSubscription.objects.create(
            user=request.user,
            plan=plan,
            expires_at=expires_at
        )
        
        return Response(
            SignalSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        subscription.status = 'cancelled'
        subscription.auto_renew = False
        subscription.save()
        
        return Response({'message': 'Subscription cancelled'})

class TradingSignalViewSet(viewsets.ReadOnlyModelViewSet):
    """Trading signals"""
    serializer_class = TradingSignalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Get user's active subscriptions
        subscriptions = SignalSubscription.objects.filter(
            user=self.request.user,
            status='active',
            expires_at__gt=timezone.now()
        ).values_list('plan__provider', flat=True)
        
        # Get signals from subscribed providers
        return TradingSignal.objects.filter(
            provider__in=subscriptions,
            status='active'
        ).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a signal as an order"""
        signal = self.get_object()
        
        # Check if user has active subscription
        if not SignalSubscription.objects.filter(
            user=request.user,
            plan__provider=signal.provider,
            status='active',
            expires_at__gt=timezone.now()
        ).exists():
            return Response(
                {'error': 'No active subscription for this signal'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create order based on signal
        order_service = OrderExecutionService()
        
        order_data = {
            'trading_pair': signal.trading_pair.id,
            'order_type': 'limit',
            'side': signal.signal_type,
            'quantity': request.data.get('quantity'),
            'price': signal.entry_price,
            'stop_price': signal.stop_loss,
            'source': 'signal',
            'source_id': signal.id
        }
        
        try:
            order = order_service.create_order(request.user, order_data)
            
            # Mark signal notification as acted on
            SignalNotification.objects.filter(
                user=request.user,
                signal=signal
            ).update(acted_on=True)
            
            return Response({
                'message': 'Signal executed',
                'order_id': order.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class SignalNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Signal notifications"""
    serializer_class = SignalNotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SignalNotification.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.read_at = timezone.now()
        notification.save()
        
        return Response({'message': 'Marked as read'})
```

### 8.6 Loans Views

```python
# loans/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from loans.models import LoanProduct, Loan, LoanRepayment
from loans.serializers import (
    LoanProductSerializer, LoanSerializer, LoanRepaymentSerializer
)
from funds.models import Wallet, Transaction

class LoanProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Loan product listing"""
    serializer_class = LoanProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = LoanProduct.objects.filter(is_active=True)

class LoanViewSet(viewsets.ModelViewSet):
    """Loan management"""
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Loan.objects.all()
        return Loan.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Apply for a loan"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user has KYC verified
        if not request.user.is_verified:
            return Response(
                {'error': 'KYC verification required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has active loans
        active_loans = Loan.objects.filter(
            user=request.user,
            status__in=['approved', 'active']
        ).count()
        
        if active_loans >= 3:
            return Response(
                {'error': 'Maximum active loans reached'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check collateral availability
        collateral_currency = serializer.validated_data['collateral_currency']
        collateral_amount = serializer.validated_data['collateral_amount']
        
        wallet = Wallet.objects.get(
            user=request.user,
            currency=collateral_currency
        )
        
        if wallet.balance < collateral_amount:
            return Response(
                {'error': 'Insufficient collateral'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Lock collateral
        wallet.balance -= collateral_amount
        wallet.locked_balance += collateral_amount
        wallet.save()
        
        # Create loan
        product = serializer.validated_data['product']
        loan = Loan.objects.create(
            user=request.user,
            product=product,
            amount=serializer.validated_data['amount'],
            interest_rate=product.interest_rate,
            term_days=product.term_days,
            collateral_amount=collateral_amount,
            collateral_currency=collateral_currency,
            outstanding_balance=serializer.validated_data['amount']
        )
        
        return Response(
            LoanSerializer(loan).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve loan (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        loan = self.get_object()
        
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update loan status
        loan.status = 'approved'
        loan.approved_by = request.user
        loan.approved_at = timezone.now()
        loan.disbursed_at = timezone.now()
        loan.due_date = timezone.now().date() + timedelta(days=loan.term_days)
        loan.save()
        
        # Credit user's wallet
        wallet, _ = Wallet.objects.get_or_create(
            user=loan.user,
            currency='USD'
        )
        wallet.balance += loan.amount
        wallet.save()
        
        # Create transaction
        Transaction.objects.create(
            user=loan.user,
            transaction_type='loan',
            currency='USD',
            amount=loan.amount,
            status='completed',
            reference_id=f'LOAN-{loan.id}',
            completed_at=timezone.now()
        )
        
        return Response({'message': 'Loan approved and disbursed'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject loan (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        loan = self.get_object()
        
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Unlock collateral
        wallet = Wallet.objects.get(
            user=loan.user,
            currency=loan.collateral_currency
        )
        wallet.balance += loan.collateral_amount
        wallet.locked_balance -= loan.collateral_amount
        wallet.save()
        
        # Update loan status
        loan.status = 'rejected'
        loan.approved_by = request.user
        loan.approved_at = timezone.now()
        loan.save()
        
        return Response({'message': 'Loan rejected'})
    
    @action(detail=True, methods=['post'])
    def repay(self, request, pk=None):
        """Make loan repayment"""
        loan = self.get_object()
        
        if loan.status not in ['approved', 'active']:
            return Response(
                {'error': 'Loan is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = Decimal(str(request.data.get('amount')))
        
        if amount <= 0:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check wallet balance
        wallet = Wallet.objects.get(
            user=request.user,
            currency='USD'
        )
        
        if wallet.balance < amount:
            return Response(
                {'error': 'Insufficient balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate principal and interest
        total_interest = (loan.amount * loan.interest_rate / 100 * 
                         loan.term_days / 365)
        total_due = loan.amount + total_interest
        paid_so_far = loan.amount - loan.outstanding_balance
        
        # Simple allocation: pay interest first
        remaining_interest = total_interest - (paid_so_far * 
                                              (total_interest / loan.amount))
        
        if amount <= remaining_interest:
            interest_amount = amount
            principal_amount = Decimal('0')
        else:
            interest_amount = remaining_interest
            principal_amount = amount - interest_amount
        
        # Deduct from wallet
        wallet.balance -= amount
        wallet.save()
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='loan_repayment',
            currency='USD',
            amount=amount,
            status='completed',
            reference_id=f'REPAY-{loan.id}-{timezone.now().timestamp()}',
            completed_at=timezone.now()
        )
        
        # Create repayment record
        LoanRepayment.objects.create(
            loan=loan,
            amount=amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            transaction=transaction
        )
        
        # Update loan
        loan.outstanding_balance -= principal_amount
        
        if loan.outstanding_balance <= Decimal('0.01'):
            loan.outstanding_balance = Decimal('0')
            loan.status = 'repaid'
            loan.repaid_at = timezone.now()
            
            # Release collateral
            collateral_wallet = Wallet.objects.get(
                user=request.user,
                currency=loan.collateral_currency
            )
            collateral_wallet.balance += loan.collateral_amount
            collateral_wallet.locked_balance -= loan.collateral_amount
            collateral_wallet.save()
        else:
            loan.status = 'active'
        
        loan.save()
        
        return Response({
            'message': 'Repayment successful',
            'outstanding_balance': loan.outstanding_balance
        })

class LoanRepaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Loan repayment history"""
    serializer_class = LoanRepaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LoanRepayment.objects.filter(loan__user=self.request.user)
```

### 8.7 Referrals Views

```python
# referrals/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from referrals.models import ReferralReward, ReferralTier
from users.serializers import UserSerializer

User = get_user_model()

class ReferralViewSet(viewsets.ViewSet):
    """Referral program endpoints"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def code(self, request):
        """Get user's referral code"""
        return Response({
            'referral_code': request.user.referral_code,
            'referral_link': f'{request.build_absolute_uri("/register")}?ref={request.user.referral_code}'
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get referral statistics"""
        referred_users = User.objects.filter(referred_by=request.user)
        rewards = ReferralReward.objects.filter(referrer=request.user)
        
        total_rewards = sum(reward.amount for reward in rewards)
        
        return Response({
            'total_referrals': referred_users.count(),
            'active_referrals': referred_users.filter(is_active=True).count(),
            'total_rewards': total_rewards,
            'pending_rewards': rewards.filter(
                transaction__isnull=True
            ).count()
        })
    
    @action(detail=False, methods=['get'])
    def rewards(self, request):
        """Get referral rewards"""
        rewards = ReferralReward.objects.filter(
            referrer=request.user
        ).order_by('-created_at')
        
        return Response([{
            'id': reward.id,
            'referred_user': reward.referred_user.username,
            'reward_type': reward.reward_type,
            'amount': reward.amount,
            'currency': reward.currency,
            'status': 'paid' if reward.transaction else 'pending',
            'created_at': reward.created_at
        } for reward in rewards])
    
    @action(detail=False, methods=['get'])
    def referred_users(self, request):
        """List referred users"""
        referred_users = User.objects.filter(referred_by=request.user)
        
        return Response([{
            'username': user.username,
            'email': user.email,
            'is_verified': user.is_verified,
            'created_at': user.created_at,
            'total_trades': user.order_set.filter(status='filled').count()
        } for user in referred_users])
```

## 9. URL Configuration

```python
# config/urls.py (main urls.py)
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Import viewsets
from users.views import UserRegistrationView, UserProfileView, KYCViewSet
from funds.views import (
    WalletViewSet, TransactionViewSet, DepositViewSet, WithdrawalViewSet
)
from trading.views import TradingPairViewSet, OrderViewSet, PositionViewSet
from bots.views import TradingBotViewSet, BotTradeViewSet
from copy_trading.views import (
    TraderViewSet, CopyTradingSubscriptionViewSet, CopiedTradeViewSet
)
from signals.views import (
    SignalProviderViewSet, SignalPlanViewSet, SignalSubscriptionViewSet,
    TradingSignalViewSet, SignalNotificationViewSet
)
from loans.views import LoanProductViewSet, LoanViewSet, LoanRepaymentViewSet
from referrals.views import ReferralViewSet

# Create router
router = DefaultRouter()

# Register viewsets
router.register(r'kyc', KYCViewSet, basename='kyc')
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'deposits', DepositViewSet, basename='deposit')
router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawal')
router.register(r'trading-pairs', TradingPairViewSet, basename='trading-pair')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'positions', PositionViewSet, basename='position')
router.register(r'bots', TradingBotViewSet, basename='bot')
router.register(r'bot-trades', BotTradeViewSet, basename='bot-trade')
router.register(r'traders', TraderViewSet, basename='trader')
router.register(r'copy-trading', CopyTradingSubscriptionViewSet, 
                basename='copy-trading')
router.register(r'copied-trades', CopiedTradeViewSet, basename='copied-trade')
router.register(r'signal-providers', SignalProviderViewSet, 
                basename='signal-provider')
router.register(r'signal-plans', SignalPlanViewSet, basename='signal-plan')
router.register(r'signal-subscriptions', SignalSubscriptionViewSet,
                basename='signal-subscription')
router.register(r'signals', TradingSignalViewSet, basename='signal')
router.register(r'signal-notifications', SignalNotificationViewSet,
                basename='signal-notification')
router.register(r'loan-products', LoanProductViewSet, basename='loan-product')
router.register(r'loans', LoanViewSet, basename='loan')
router.register(r'loan-repayments', LoanRepaymentViewSet, 
                basename='loan-repayment')
router.register(r'referrals', ReferralViewSet, basename='referral')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), 
         name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), 
         name='redoc'),
    
    # Authentication
    path('api/v1/auth/register/', UserRegistrationView.as_view(), 
         name='register'),
    path('api/v1/auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view(), 
         name='token_refresh'),
    path('api/v1/auth/me/', UserProfileView.as_view(), name='profile'),
    
    # API Routes
    path('api/v1/', include(router.urls)),
]
```

## 10. Settings Configuration

```python
# config/settings.py
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',
    'drf_spectacular',
    'channels',
    
    # Local apps
    'users',
    'funds',
    'trading',
    'bots',
    'copy_trading',
    'signals',
    'loans',
    'referrals',
]

python managepy startapp  users funds trading bots copy_trading signals loans referrals

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'trading_platform'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS Settings
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'update-market-prices': {
        'task': 'tasks.update_market_prices',
        'schedule': 5.0,  # Every 5 seconds
    },
    'execute-pending-orders': {
        'task': 'tasks.execute_pending_orders',
        'schedule': 10.0,  # Every 10 seconds
    },
    'run-trading-bots': {
        'task': 'tasks.run_trading_bots',
        'schedule': 60.0,  # Every minute
    },
    'process-copy-trades': {
        'task': 'tasks.process_copy_trades',
        'schedule': 30.0,  # Every 30 seconds
    },
    'calculate-loan-interest': {
        'task': 'tasks.calculate_loan_interest',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'process-referral-rewards': {
        'task': 'tasks.process_referral_rewards',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
    'check-kyc-expiry': {
        'task': 'tasks.check_kyc_expiry',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Channels Configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(
                os.environ.get('REDIS_HOST', '127.0.0.1'),
                int(os.environ.get('REDIS_PORT', 6379))
            )],
        },
    },
}

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')