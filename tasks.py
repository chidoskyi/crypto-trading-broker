# tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

# @shared_task
# def update_market_prices():
#     """Update market prices for all active trading pairs"""
#     from trading.models import TradingPair
#     from trading.services.market_service import MarketDataService
    
#     market_service = MarketDataService()
#     active_pairs = TradingPair.objects.filter(is_active=True)
    
#     for pair in active_pairs:
#         try:
#             ticker = market_service.get_ticker(pair.symbol)
#             # Update cached prices or database as needed
#         except Exception as e:
#             print(f"Error updating {pair.symbol}: {e}")

@shared_task
def update_market_prices():
    """Update market prices for all active trading pairs"""
    from trading.models import TradingPair
    from trading.services.market_service import MarketDataService
    from django.utils import timezone
    
    market_service = MarketDataService()
    active_pairs = TradingPair.objects.filter(is_active=True)
    
    for pair in active_pairs:
        try:
            # FIXED: Pass the TradingPair object, not the symbol string
            ticker = market_service.get_ticker(pair)  # NO .symbol here!
            
            # Update the TradingPair model with new data
            if ticker and 'last_price' in ticker:
                pair.last_price = ticker['last_price']
                pair.price_change_24h = ticker.get('change_24h', 0)
                pair.volume_24h = ticker.get('volume', 0)   
                pair.market_cap = ticker.get('market_cap')
                pair.last_updated = timezone.now()
                pair.save()
                
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



@shared_task
def check_crypto_deposits():
    """Check for new crypto deposits - runs every 2 minutes"""
    from funds.services.deposit_detector import deposit_detector
    
    try:
        deposit_detector.check_all_deposits()
        return "Deposit check completed"
    except Exception as e:
        print(f"Error in check_crypto_deposits: {e}")
        return f"Error: {e}"

@shared_task
def generate_missing_qr_codes():
    """Generate QR codes for addresses that don't have them"""
    from funds.models import CryptoWalletAddress
    
    addresses = CryptoWalletAddress.objects.filter(
        qr_code='',
        is_active=True
    )
    
    for addr in addresses:
        try:
            addr.generate_qr_code()
            addr.save()
        except Exception as e:
            print(f"Error generating QR for {addr.id}: {e}")
    
    return f"Generated QR codes for {addresses.count()} addresses"