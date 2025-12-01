"""
Webhook endpoints for all background tasks
Replace Celery tasks with HTTP endpoints for shared hosting

Add to views.py
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.db.models import Q
from investment.models import Investment
from trading.models import TradingPair, Order
from trading.services.order_service import OrderExecutionService
from trading.services.market_service import MarketDataService
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


def verify_cron_token(request):
    """Verify the cron secret token"""
    secret_token = request.GET.get('token') or request.headers.get('X-Cron-Token')
    
    if not secret_token or secret_token != settings.CRON_SECRET_TOKEN:
        logger.warning(f"Unauthorized cron attempt from IP: {request.META.get('REMOTE_ADDR')}")
        return False
    return True


# ============================================
# 1. PROCESS MATURED INVESTMENTS
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])  # Allow both for testing
def cron_process_investments(request):
    """
    Webhook endpoint to process matured investments
    Can be called by external cron services
    
    Security: Use a secret token in URL or header
    """
    
    # ✅ SECURITY CHECK - Verify secret token
    secret_token = request.GET.get('token') or request.headers.get('X-Cron-Token')
    
    if not secret_token or secret_token != settings.CRON_SECRET_TOKEN:
        logger.warning(f"Unauthorized cron attempt from IP: {get_client_ip(request)}")
        return JsonResponse({
            'error': 'Unauthorized',
            'status': 'failed'
        }, status=403)
    
    # Process matured investments
    try:
        now = timezone.now()
        logger.info(f'[{now}] Webhook triggered - Processing matured investments...')
        
        # Find all matured investments
        matured_investments = Investment.objects.filter(
            Q(status=Investment.STATUS_APPROVED) &
            Q(is_running=True) &
            Q(completed=False) &
            Q(end_date__lte=now)
        ).select_related('user', 'plan')
        
        total_count = matured_investments.count()
        
        if total_count == 0:
            return JsonResponse({
                'status': 'success',
                'message': 'No matured investments found',
                'total': 0,
                'processed': 0,
                'errors': 0,
                'timestamp': str(now)
            })
        
        success_count = 0
        error_count = 0
        errors_list = []
        
        # Process each investment
        for investment in matured_investments:
            try:
                result = investment.update_status()
                
                if result:
                    success_count += 1
                    logger.info(f'✓ Processed Investment #{investment.id}')
                else:
                    error_count += 1
                    errors_list.append(f'Investment #{investment.id} returned False')
                    logger.error(f'✗ Failed Investment #{investment.id}')
                    
            except Exception as e:
                error_count += 1
                errors_list.append(f'Investment #{investment.id}: {str(e)}')
                logger.error(f'Error processing investment #{investment.id}: {str(e)}')
        
        response_data = {
            'status': 'completed',
            'message': f'Processed {success_count} of {total_count} investments',
            'total': total_count,
            'processed': success_count,
            'errors': error_count,
            'timestamp': str(now)
        }
        
        if errors_list:
            response_data['error_details'] = errors_list[:10]  # First 10 errors
        
        logger.info(f'Webhook processing complete: {response_data}')
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f'Critical error in webhook: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'timestamp': str(timezone.now())
        }, status=500)


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================
# 2. UPDATE MARKET PRICES
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_update_market_prices(request):
    """Update market prices for all active trading pairs - Run every 2-5 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        market_service = MarketDataService()
        active_pairs = TradingPair.objects.filter(is_active=True)
        updated = 0
        errors = 0
        
        for pair in active_pairs:
            try:
                ticker = market_service.get_ticker(pair)
                if ticker and 'last_price' in ticker:
                    pair.last_price = ticker['last_price']
                    pair.price_change_24h = ticker.get('change_24h', 0)
                    pair.percentage_change_24h = ticker.get('change_24h', 0)
                    pair.volume_24h = ticker.get('volume', 0)
                    pair.market_cap = ticker.get('market_cap')
                    
                    # Update high and low from ticker data
                    if 'high_24h' in ticker:
                        pair.high = ticker['high_24h']
                    if 'low_24h' in ticker:
                        pair.low = ticker['low_24h']
                    
                    # Update open and close from ticker data
                    if 'open' in ticker:
                        pair.open = ticker['open']
                    if 'close' in ticker:
                        pair.close = ticker['close']
                    
                    pair.last_updated = timezone.now()
                    pair.save()
                    updated += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error updating {pair.symbol}: {e}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'update_market_prices',
            'total_pairs': active_pairs.count(),
            'updated': updated,
            'errors': errors,
            'timestamp': str(timezone.now())
        })
    except Exception as e:
        logger.error(f"Critical error in cron_update_market_prices: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    
# ============================================
# 3. EXECUTE PENDING ORDERS - UPDATED
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_execute_pending_orders(request):
    """Check and execute pending limit orders - Run every 1-2 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:        
        order_service = OrderExecutionService()
        pending_orders = Order.objects.filter(
            status='open',
            order_type__in=['limit', 'stop_loss', 'take_profit']
        ).select_related('trading_pair', 'user')  # ✅ Added select_related for performance
        
        total = pending_orders.count()
        executed = 0
        errors = 0
        details = []
        
        for order in pending_orders:
            try:
                result = order_service.check_and_execute_order(order)
                if result:
                    executed += 1
                    details.append(f"Order {order.id} executed successfully")
                else:
                    details.append(f"Order {order.id} conditions not met")
                    
            except Exception as e:
                errors += 1
                logger.error(f"Error executing order {order.id}: {e}")
                details.append(f"Order {order.id} error: {str(e)}")
        
        logger.info(f"Cron executed: {executed}/{total} orders, {errors} errors")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'execute_pending_orders',
            'total_orders': total,
            'executed': executed,
            'errors': errors,
            'details': details,  # ✅ Added details for debugging
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_execute_pending_orders: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ============================================
# 3. EXECUTE EXPIRED ORDERS - UPDATED
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_expire_orders(request):
    """
    Expire orders that have reached their expiration time
    Run this every 1 minute
    """
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        now = timezone.now()
        
        # Find all orders that should be expired
        expired_orders = Order.objects.filter(
            status__in=['open', 'pending'],
            expiration_time__isnull=False,
            expiration_time__lte=now
        ).select_related('user', 'trading_pair')  # ✅ Added select_related
        
        order_service = OrderExecutionService()
        
        # ✅ Use the service method instead of manual handling
        expired_count = order_service.handle_expired_orders()
        
        return JsonResponse({
            'status': 'completed',
            'task': 'expire_orders',
            'total_checked': expired_orders.count(),
            'expired': expired_count,
            'timestamp': str(now)
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_expire_orders: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ============================================
# 4. UPDATE POSITIONS - UPDATED
# ============================================
@csrf_exempt
def cron_update_positions(request):
    """
    Update unrealized P&L for all open positions
    Run this every 5 minutes
    """
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from trading.models import Position
        
        market_service = MarketDataService()
        # ✅ Fixed: filter only open positions
        active_positions = Position.objects.filter(status='open')
        
        updated = 0
        errors = 0
        details = []
        
        for position in active_positions:
            try:
                # Get current price
                ticker = market_service.get_ticker(position.trading_pair)
                current_price = Decimal(str(ticker['last_price']))
                
                # Update position
                position.current_price = current_price
                
                # Calculate unrealized P&L
                if position.side == 'long':
                    price_diff = current_price - position.entry_price
                else:  # short
                    price_diff = position.entry_price - current_price
                
                # Apply leverage to P&L
                position.unrealized_pnl = price_diff * position.quantity * position.leverage
                position.save()
                
                updated += 1
                details.append(f"Position {position.id} updated - P&L: {position.unrealized_pnl}")
                
            except Exception as e:
                errors += 1
                logger.error(f"Error updating position {position.id}: {str(e)}")
                details.append(f"Position {position.id} error: {str(e)}")
        
        logger.info(f"Positions updated: {updated}/{active_positions.count()}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'update_positions',
            'total_positions': active_positions.count(),
            'updated': updated,
            'errors': errors,
            'details': details,  # ✅ Added details for debugging
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_update_positions: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
# ============================================
# 4. RUN TRADING BOTS
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_run_trading_bots(request):
    """Execute all active trading bots - Run every 5-10 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from bots.models import TradingBot
        from bots.services.bot_engine import BotEngine
        
        active_bots = TradingBot.objects.filter(
            is_active=True,
            is_paper_trading=False
        )
        
        total = active_bots.count()
        executed = 0
        errors = 0
        
        for bot in active_bots:
            try:
                engine = BotEngine(bot)
                engine.run()
                executed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error running bot {bot.id}: {e}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'run_trading_bots',
            'total_bots': total,
            'executed': executed,
            'errors': errors,
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_run_trading_bots: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 5. PROCESS COPY TRADES
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_process_copy_trades(request):
    """Process copy trading orders - Run every 5 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from trading.models import Order
        from copy_trading.services.copy_service import CopyTradingService
        
        copy_service = CopyTradingService()
        
        # Get recently filled orders from master traders
        recent_orders = Order.objects.filter(
            status='filled',
            user__trader__isnull=False,
            executed_at__gte=timezone.now() - timedelta(minutes=5)
        ).exclude(source='copy_trade')
        
        total = recent_orders.count()
        processed = 0
        errors = 0
        
        for order in recent_orders:
            try:
                copy_service.replicate_trade(order)
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error copying trade {order.id}: {e}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'process_copy_trades',
            'total_orders': total,
            'processed': processed,
            'errors': errors,
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_process_copy_trades: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 6. CALCULATE LOAN INTEREST
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_calculate_loan_interest(request):
    """Calculate and apply interest to active loans - Run daily"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from loans.models import Loan
        
        active_loans = Loan.objects.filter(status='active')
        
        total = active_loans.count()
        processed = 0
        errors = 0
        
        for loan in active_loans:
            try:
                # Calculate daily interest
                daily_rate = loan.interest_rate / 365 / 100
                interest = loan.outstanding_balance * Decimal(str(daily_rate))
                
                loan.outstanding_balance += interest
                loan.save()
                processed += 1
                
            except Exception as e:
                errors += 1
                logger.error(f"Error calculating interest for loan {loan.id}: {e}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'calculate_loan_interest',
            'total_loans': total,
            'processed': processed,
            'errors': errors,
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_calculate_loan_interest: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 7. PROCESS REFERRAL REWARDS
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_process_referral_rewards(request):
    """Process referral rewards - Run every 10-30 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from referrals.models import ReferralReward
        from funds.models import Transaction, Wallet
        
        pending_rewards = ReferralReward.objects.filter(transaction__isnull=True)
        
        total = pending_rewards.count()
        processed = 0
        errors = 0
        
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
                processed += 1
                
            except Exception as e:
                errors += 1
                logger.error(f"Error processing reward {reward.id}: {e}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'process_referral_rewards',
            'total_rewards': total,
            'processed': processed,
            'errors': errors,
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_process_referral_rewards: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 8. CHECK KYC EXPIRY
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_check_kyc_expiry(request):
    """Check for expired KYC documents - Run daily"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from users.models import User, KYCDocument
        
        # KYC documents older than 2 years need reverification
        expiry_date = timezone.now() - timedelta(days=730)
        
        expired_kyc = KYCDocument.objects.filter(
            submitted_at__lt=expiry_date,
            user__kyc_status='approved'
        )
        
        total = expired_kyc.count()
        processed = 0
        
        for kyc in expired_kyc:
            kyc.user.kyc_status = 'not_submitted'
            kyc.user.save()
            processed += 1
            # TODO: Send notification to user
        
        return JsonResponse({
            'status': 'completed',
            'task': 'check_kyc_expiry',
            'expired_documents': total,
            'users_notified': processed,
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_check_kyc_expiry: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 9. CHECK CRYPTO DEPOSITS
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_check_crypto_deposits(request):
    """Check for new crypto deposits - Run every 2 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from funds.services.deposit_detector import deposit_detector
        
        result = deposit_detector.check_all_deposits()
        
        return JsonResponse({
            'status': 'completed',
            'task': 'check_crypto_deposits',
            'result': str(result),
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_check_crypto_deposits: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 10. GENERATE MISSING QR CODES
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_generate_qr_codes(request):
    """Generate QR codes for addresses - Run every 30 minutes"""
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from funds.models import CryptoWalletAddress
        
        addresses = CryptoWalletAddress.objects.filter(
            qr_code='',
            is_active=True
        )
        
        total = addresses.count()
        generated = 0
        errors = 0
        
        for addr in addresses:
            try:
                addr.generate_qr_code()
                addr.save()
                generated += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error generating QR for {addr.id}: {e}")
        
        return JsonResponse({
            'status': 'completed',
            'task': 'generate_qr_codes',
            'total_addresses': total,
            'generated': generated,
            'errors': errors,
            'timestamp': str(timezone.now())
        })
        
    except Exception as e:
        logger.error(f"Critical error in cron_generate_qr_codes: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================
# 11. MASTER CRON - RUN ALL TASKS
# ============================================
@csrf_exempt
@require_http_methods(["POST", "GET"])
def cron_run_all_tasks(request):
    """
    Run all cron tasks in sequence
    Use this if you want one endpoint that does everything
    Run every 5 minutes
    """
    if not verify_cron_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    results = {}
    start_time = timezone.now()
    
    # List of all cron functions
    tasks = [
        ('process_investments', cron_process_investments),
        ('update_market_prices', cron_update_market_prices),
        ('execute_pending_orders', cron_execute_pending_orders),
        ('check_crypto_deposits', cron_check_crypto_deposits),
        ('process_referral_rewards', cron_process_referral_rewards),
        ('generate_qr_codes', cron_generate_qr_codes),
        ('expire_orders', cron_expire_orders),
        ('update_positions', cron_update_positions),
    ]
    
    for task_name, task_func in tasks:
        try:
            # Call each task function
            response = task_func(request)
            results[task_name] = {
                'status': 'completed',
                'response': response.content.decode() if hasattr(response, 'content') else str(response)
            }
        except Exception as e:
            results[task_name] = {
                'status': 'error',
                'error': str(e)
            }
            logger.error(f"Error in {task_name}: {e}")
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    return JsonResponse({
        'status': 'completed',
        'task': 'run_all_tasks',
        'results': results,
        'duration_seconds': duration,
        'timestamp': str(end_time)
    })


# ============================================
# 12. HEALTH CHECK ENDPOINT
# ============================================
@csrf_exempt
@require_http_methods(["GET"])
def cron_health_check(request):
    """
    Simple health check endpoint (no auth required)
    Use this to verify your cron service can reach your server
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'cron_webhooks',
        'timestamp': str(timezone.now()),
        'server_time': str(timezone.now())
    })