# copy_trading/services/copy_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

from copy_trading.models import CopyTradingSubscription, CopiedTrade, CopyTradingPerformance
from trading.services.order_service import OrderExecutionService
from trading.models import Order, Position
from users.models import Account

logger = logging.getLogger(__name__)


class CopyTradingService:
    """
    Service for executing and managing copy trades
    """
    
    def __init__(self):
        self.order_service = OrderExecutionService()
    
    def replicate_trade(self, master_order):
        """Replicate a master trader's order to all active followers"""
        try:
            trader = master_order.user.trader
        except AttributeError:
            logger.error(f"Order {master_order.id} user is not a trader")
            return {
                'success': False,
                'error': 'User is not a registered trader'
            }
        
        subscriptions = CopyTradingSubscription.objects.filter(
            trader=trader,
            is_active=True
        ).select_related('follower', 'follower__account')
        
        results = {
            'total_followers': subscriptions.count(),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        for subscription in subscriptions:
            try:
                if subscription.execution_mode == CopyTradingSubscription.EXEC_AUTO:
                    self._copy_order_for_follower(master_order, subscription)
                    results['successful'] += 1
                else:
                    self._create_pending_trade(master_order, subscription)
                    results['successful'] += 1
                    
            except ValidationError as e:
                error_msg = str(e)
                if any(keyword in error_msg.lower() for keyword in [
                    'would lock', 'insufficient', 'maximum', 'exceeds'
                ]):
                    results['skipped'] += 1
                    logger.warning(
                        f"Skipped copying for {subscription.follower.username}: {error_msg}"
                    )
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'follower': subscription.follower.username,
                        'error': error_msg
                    })
                    logger.error(
                        f"Failed to copy trade for {subscription.follower.username}: {error_msg}"
                    )
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'follower': subscription.follower.username,
                    'error': str(e)
                })
                logger.error(
                    f"Error copying trade for {subscription.follower.username}: {e}",
                    exc_info=True
                )
        
        return results
    
    @transaction.atomic
    def _copy_order_for_follower(self, master_order, subscription):
        """Copy an order for a specific follower with auto execution"""
        follower = subscription.follower
        
        # Check minimum investment
        follower_account = Account.objects.get(user=follower)
        
        if follower_account.trading_balance < subscription.trader.minimum_investment:
            raise ValidationError(
                f"Your trading balance (${follower_account.trading_balance}) is below "
                f"the minimum required (${subscription.trader.minimum_investment}). "
                f"Please deposit more funds to continue copy trading."
            )
        
        # Validate follower can trade
        if not self._can_follower_trade(follower):
            raise ValidationError(f"Follower {follower.username} cannot trade")
        
        follower_account = Account.objects.select_for_update().get(user=follower)
        
        if follower_account.status != Account.STATUS_ACTIVE:
            raise ValidationError(
                f"Follower account is {follower_account.get_status_display()}"
            )
        
        # Calculate position size
        try:
            follower_quantity = self._calculate_follower_quantity(
                master_order,
                subscription,
                follower_account
            )
        except Exception as e:
            raise ValidationError(f"Failed to calculate position size: {e}")
        
        if follower_quantity <= 0:
            raise ValidationError("Calculated quantity is zero or negative")
        
        # Calculate order value
        order_price = master_order.price if master_order.price else self._get_market_price(
            master_order.trading_pair, 
            master_order.side
        )
        order_value = follower_quantity * order_price
        
        # Check projected locked balance
        if follower_account.trading_balance > 0:
            projected_locked = follower_account.locked_trading_balance + order_value
            projected_ratio = (projected_locked / follower_account.trading_balance * 100)
            
            MAX_LOCKED_PERCENTAGE = 80
            if projected_ratio > MAX_LOCKED_PERCENTAGE:
                raise ValidationError(
                    f"This trade would lock {projected_ratio:.2f}% of trading balance. "
                    f"Maximum allowed: {MAX_LOCKED_PERCENTAGE}%"
                )
        
        # Check available balance
        available_balance = follower_account.available_trading_balance
        if order_value > available_balance:
            raise ValidationError(
                f"Insufficient trading balance. Required: {order_value}, "
                f"Available: {available_balance}"
            )
        
        # Apply risk checks
        self._apply_risk_checks(
            master_order, 
            subscription, 
            follower_quantity, 
            follower_account,
            order_value
        )
        
        # Lock the trading balance
        follower_account.locked_trading_balance += order_value
        follower_account.save(update_fields=['locked_trading_balance'])
        
        # Create order data
        order_data = {
            'trading_pair': master_order.trading_pair,
            'order_type': master_order.order_type,
            'side': master_order.side,
            'quantity': follower_quantity,
            'price': master_order.price,
            'stop_price': master_order.stop_price,
            'leverage': master_order.leverage,
            'source': 'copy_trade',
            'source_id': master_order.id,
            'order_value': order_value
        }
        
        if subscription.stop_loss_percentage:
            order_data['stop_loss_percentage'] = subscription.stop_loss_percentage
        
        try:
            # Execute the order
            follower_order = self.order_service.create_order(
                follower,
                order_data
            )
            
            # Record the copied trade
            copied_trade = CopiedTrade.objects.create(
                subscription=subscription,
                master_order=master_order,
                follower_order=follower_order,
                status=CopiedTrade.STATUS_COMPLETED,
                calculated_quantity=follower_quantity,
                allocated_amount=order_value
            )
            
            # Update performance metrics
            self._update_performance_after_trade(subscription, copied_trade)
            
            logger.info(
                f"Successfully copied trade {master_order.id} to "
                f"follower {follower.username} as order {follower_order.id}"
            )
            
            return copied_trade
            
        except Exception as e:
            # Rollback locked balance on failure
            follower_account.locked_trading_balance -= order_value
            follower_account.save(update_fields=['locked_trading_balance'])
            logger.error(f"Failed to execute copied order: {e}")
            raise
    
    @transaction.atomic
    def _create_pending_trade(self, master_order, subscription):
        """Create a pending trade for manual approval"""
        follower_account = Account.objects.select_for_update().get(
            user=subscription.follower
        )
        
        # Calculate the quantity
        follower_quantity = self._calculate_follower_quantity(
            master_order,
            subscription,
            follower_account
        )
        
        if follower_quantity <= 0:
            raise ValidationError("Calculated quantity is zero or negative")
        
        # Calculate allocated amount
        order_price = master_order.price if master_order.price else self._get_market_price(
            master_order.trading_pair,
            master_order.side
        )
        allocated_amount = follower_quantity * order_price
        
        # Create pending copied trade
        copied_trade = CopiedTrade.objects.create(
            subscription=subscription,
            master_order=master_order,
            follower_order=None,
            status=CopiedTrade.STATUS_PENDING,
            calculated_quantity=follower_quantity,
            allocated_amount=allocated_amount
        )
        
        logger.info(
            f"Created pending trade {copied_trade.id} for follower "
            f"{subscription.follower.username}"
        )
        
        return copied_trade
    
    def execute_pending_trade(self, copied_trade):
        """Execute a pending trade after manual approval"""
        if copied_trade.status != CopiedTrade.STATUS_PENDING:
            raise ValidationError("Only pending trades can be executed")
        
        try:
            with transaction.atomic():
                result = self._copy_order_for_follower(
                    copied_trade.master_order,
                    copied_trade.subscription
                )
                
                # Update the original copied_trade
                copied_trade.follower_order = result.follower_order
                copied_trade.status = CopiedTrade.STATUS_COMPLETED
                copied_trade.save(update_fields=['follower_order', 'status'])
                
                # Update performance
                self._update_performance_after_trade(
                    copied_trade.subscription, 
                    copied_trade
                )
                
        except Exception as e:
            copied_trade.status = CopiedTrade.STATUS_FAILED
            copied_trade.error_message = str(e)
            copied_trade.save(update_fields=['status', 'error_message'])
            raise
    
    def _update_performance_after_trade(self, subscription, copied_trade):
        """Update performance metrics after a trade is executed"""
        performance, created = CopyTradingPerformance.objects.get_or_create(
            subscription=subscription
        )
        
        # Update immediately for new trade
        performance.total_trades += 1
        performance.last_trade_at = timezone.now()
        
        if copied_trade.allocated_amount:
            performance.total_invested += copied_trade.allocated_amount
        
        performance.save(update_fields=[
            'total_trades', 'last_trade_at', 'total_invested'
        ])
        
        logger.info(f"Updated performance for subscription {subscription.id}")
    
    def update_performance_from_closed_position(self, position):
        """
        Update performance metrics when a copied trade position is closed
        This should be called from signals or when closing positions
        """
        # Find the copied trade associated with this position
        try:
            copied_trade = CopiedTrade.objects.get(
                follower_order__id=position.order_id,
                status=CopiedTrade.STATUS_COMPLETED
            )
            
            performance, _ = CopyTradingPerformance.objects.get_or_create(
                subscription=copied_trade.subscription
            )
            
            # Update metrics based on position P&L
            if position.realized_pnl is not None:
                performance.total_profit_loss += position.realized_pnl
                
                if position.realized_pnl > 0:
                    performance.winning_trades += 1
                    
                    # Update best trade
                    if position.realized_pnl > performance.best_trade_profit:
                        performance.best_trade_profit = position.realized_pnl
                else:
                    performance.losing_trades += 1
                    
                    # Update worst trade
                    if position.realized_pnl < performance.worst_trade_loss:
                        performance.worst_trade_loss = position.realized_pnl
                
                # Recalculate win rate
                total_closed = performance.winning_trades + performance.losing_trades
                if total_closed > 0:
                    performance.win_rate = (
                        performance.winning_trades / total_closed * 100
                    )
                
                # Update averages
                if performance.winning_trades > 0:
                    total_profit = performance.best_trade_profit * performance.winning_trades
                    performance.average_profit_per_trade = (
                        total_profit / performance.winning_trades
                    )
                
                if performance.losing_trades > 0:
                    total_loss = performance.worst_trade_loss * performance.losing_trades
                    performance.average_loss_per_trade = (
                        total_loss / performance.losing_trades
                    )
                
                performance.save()
                
                logger.info(
                    f"Updated performance for subscription {copied_trade.subscription.id} "
                    f"from closed position {position.id}"
                )
            
        except CopiedTrade.DoesNotExist:
            logger.warning(f"No copied trade found for position {position.id}")
        except Exception as e:
            logger.error(f"Error updating performance from position: {e}")
    
    def _calculate_follower_quantity(self, master_order, subscription, follower_account):
        """Calculate appropriate quantity for follower based on sizing mode"""
        available_trading_balance = follower_account.available_trading_balance
        
        if available_trading_balance <= 0:
            raise ValidationError("No available trading balance")
        
        if subscription.sizing_mode == CopyTradingSubscription.MODE_FIXED:
            if not subscription.fixed_amount_per_trade:
                raise ValidationError("Fixed amount not configured")
            
            allocation = subscription.fixed_amount_per_trade
            
        else:
            allocation = (
                available_trading_balance * 
                subscription.copy_percentage / Decimal('100.00')
            )
        
        if subscription.max_position_size:
            allocation = min(allocation, subscription.max_position_size)
        
        if allocation > available_trading_balance:
            raise ValidationError(
                f"Allocation ({allocation}) exceeds available trading balance "
                f"({available_trading_balance})"
            )
        
        if master_order.price:
            quantity = allocation / master_order.price
        else:
            market_price = self._get_market_price(
                master_order.trading_pair, 
                master_order.side
            )
            quantity = allocation / market_price
        
        quantity = quantity.quantize(Decimal('0.00000001'))
        
        return quantity
    
    def _get_market_price(self, trading_pair, side):
        """Get current market price for a trading pair"""
        try:
            ticker = self.order_service.market_service.get_ticker(trading_pair)
            market_price = ticker.get('ask') if side == 'buy' else ticker.get('bid')
            
            if not market_price:
                raise ValidationError("Market price not available")
            
            return Decimal(str(market_price))
            
        except Exception as e:
            logger.error(f"Failed to get market price for {trading_pair.symbol}: {e}")
            raise ValidationError(f"Failed to get market price: {e}")
    
    def _apply_risk_checks(self, master_order, subscription, quantity, follower_account, order_value):
        """Apply risk management checks before executing"""
        follower = subscription.follower
        
        # Check open positions
        open_positions = Order.objects.filter(
            user=follower,
            status__in=['pending', 'open', 'partially_filled'],
            source='copy_trade'
        ).count()
        
        MAX_OPEN_COPY_POSITIONS = 20
        if open_positions >= MAX_OPEN_COPY_POSITIONS:
            raise ValidationError(
                f"Maximum open copy positions ({MAX_OPEN_COPY_POSITIONS}) reached"
            )
        
        # Check position size vs available balance
        available_balance = follower_account.available_trading_balance
        
        if available_balance > 0:
            position_percentage = (order_value / available_balance * 100)
            
            MAX_POSITION_PERCENTAGE = 30
            
            if position_percentage > MAX_POSITION_PERCENTAGE:
                raise ValidationError(
                    f"Position size ({position_percentage:.2f}%) exceeds "
                    f"maximum allowed ({MAX_POSITION_PERCENTAGE}%) of available balance"
                )
        else:
            raise ValidationError("No available trading balance")
        
        # Check subscription limits
        if subscription.max_position_size:
            if order_value > subscription.max_position_size:
                raise ValidationError(
                    f"Position value (${order_value:.2f}) exceeds "
                    f"subscription limit (${subscription.max_position_size:.2f})"
                )
        
        # Check daily limit
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = CopiedTrade.objects.filter(
            subscription__follower=follower,
            created_at__gte=today_start,
            status=CopiedTrade.STATUS_COMPLETED
        ).count()
        
        MAX_DAILY_COPY_TRADES = 50
        if today_trades >= MAX_DAILY_COPY_TRADES:
            raise ValidationError(
                f"Daily copy trade limit ({MAX_DAILY_COPY_TRADES}) reached"
            )
    
    def _can_follower_trade(self, follower):
        """Check if follower is allowed to trade"""
        try:
            account = follower.account
            
            if account.status != Account.STATUS_ACTIVE:
                logger.warning(
                    f"User {follower.username} cannot trade. "
                    f"Account status: {account.get_status_display()}"
                )
                return False
            
            if account.trading_balance <= 0:
                logger.warning(
                    f"User {follower.username} has zero trading balance"
                )
                return False
            
            # Check minimum investment
            try:
                subscription = CopyTradingSubscription.objects.filter(
                    follower=follower,
                    is_active=True
                ).select_related('trader').first()
                
                if subscription and account.trading_balance < subscription.trader.minimum_investment:
                    logger.warning(
                        f"User {follower.username} balance (${account.trading_balance}) "
                        f"below minimum (${subscription.trader.minimum_investment})"
                    )
                    return False
            except Exception as e:
                logger.error(f"Error checking minimum investment: {e}")
            
            if not follower.is_active:
                return False
            
            return True
            
        except Account.DoesNotExist:
            logger.error(f"Account not found for user {follower.username}")
            return False
    
    @transaction.atomic
    def stop_copying_trader(self, subscription, close_positions=False):
        """Stop copying a trader and optionally close all positions"""
        subscription.is_active = False
        subscription.save(update_fields=['is_active'])
        
        if close_positions:
            open_orders = Order.objects.filter(
                user=subscription.follower,
                source='copy_trade',
                source_id__in=CopiedTrade.objects.filter(
                    subscription=subscription
                ).values_list('master_order_id', flat=True),
                status__in=['pending', 'partial']
            )
            
            for order in open_orders:
                try:
                    self.order_service.cancel_order(order)
                    
                    if hasattr(order, 'locked_amount'):
                        account = order.user.account
                        account.locked_trading_balance -= order.locked_amount
                        account.save(update_fields=['locked_trading_balance'])
                        
                except Exception as e:
                    logger.error(f"Failed to cancel order {order.id}: {e}")


# # copy_trading/services/copy_service.py
# from decimal import Decimal
# from django.db import transaction
# from django.core.exceptions import ValidationError
# from django.utils import timezone
# import logging

# from copy_trading.models import CopyTradingSubscription, CopiedTrade
# from trading.services.order_service import OrderExecutionService
# from trading.models import Order
# from users.models import Account

# logger = logging.getLogger(__name__)


# class CopyTradingService:
#     """
#     Service for executing and managing copy trades
    
#     Handles:
#     - Trade replication from master to followers
#     - Position sizing calculations using Account.trading_balance
#     - Risk management
#     - Trade execution
#     """
    
#     def __init__(self):
#         self.order_service = OrderExecutionService()
    
#     def replicate_trade(self, master_order):
#         """Replicate a master trader's order to all active followers"""
#         try:
#             trader = master_order.user.trader
#         except AttributeError:
#             logger.error(f"Order {master_order.id} user is not a trader")
#             return {
#                 'success': False,
#                 'error': 'User is not a registered trader'
#             }
        
#         subscriptions = CopyTradingSubscription.objects.filter(
#             trader=trader,
#             is_active=True
#         ).select_related('follower', 'follower__account')
        
#         results = {
#             'total_followers': subscriptions.count(),
#             'successful': 0,
#             'failed': 0,
#             'skipped': 0,  # ✅ Add skipped count
#             'errors': []
#         }
        
#         for subscription in subscriptions:
#             try:
#                 if subscription.execution_mode == CopyTradingSubscription.EXEC_AUTO:
#                     self._copy_order_for_follower(master_order, subscription)
#                     results['successful'] += 1
#                 else:
#                     self._create_pending_trade(master_order, subscription)
#                     results['successful'] += 1
                    
#             except ValidationError as e:  # ✅ Catch ValidationError specifically
#                 # ✅ Check if it's a risk management block (skip gracefully)
#                 error_msg = str(e)
#                 if any(keyword in error_msg.lower() for keyword in [
#                     'would lock', 'insufficient', 'maximum', 'exceeds'
#                 ]):
#                     results['skipped'] += 1
#                     logger.warning(
#                         f"Skipped copying for {subscription.follower.username}: {error_msg}"
#                     )
#                 else:
#                     # Other validation errors are failures
#                     results['failed'] += 1
#                     results['errors'].append({
#                         'follower': subscription.follower.username,
#                         'error': error_msg
#                     })
#                     logger.error(
#                         f"Failed to copy trade for {subscription.follower.username}: {error_msg}"
#                     )
#             except Exception as e:  # ✅ Other exceptions are real failures
#                 results['failed'] += 1
#                 results['errors'].append({
#                     'follower': subscription.follower.username,
#                     'error': str(e)
#                 })
#                 logger.error(
#                     f"Error copying trade for {subscription.follower.username}: {e}",
#                     exc_info=True
#                 )
        
#         return results
    
#     @transaction.atomic
#     def _copy_order_for_follower(self, master_order, subscription):
#         """
#         Copy an order for a specific follower with auto execution
#         """
#         follower = subscription.follower
        
#         # ✅ ADD THIS - Check minimum investment before copying
#         follower_account = Account.objects.get(user=follower)
        
#         if follower_account.trading_balance < subscription.trader.minimum_investment:
#             raise ValidationError(
#                 f"Your trading balance (${follower_account.trading_balance}) is below "
#                 f"the minimum required (${subscription.trader.minimum_investment}). "
#                 f"Please deposit more funds to continue copy trading."
#             )
        
#         # Validate follower can trade
#         if not self._can_follower_trade(follower):
#             raise ValidationError(f"Follower {follower.username} cannot trade")
        
#         # Lock the follower's account for this transaction
#         follower_account = Account.objects.select_for_update().get(user=follower)
        
#         # Verify account is active
#         if follower_account.status != Account.STATUS_ACTIVE:
#             raise ValidationError(
#                 f"Follower account is {follower_account.get_status_display()}"
#             )
        
#         # Calculate position size based on available trading balance
#         try:
#             follower_quantity = self._calculate_follower_quantity(
#                 master_order,
#                 subscription,
#                 follower_account
#             )
#         except Exception as e:
#             raise ValidationError(f"Failed to calculate position size: {e}")
        
#         if follower_quantity <= 0:
#             raise ValidationError("Calculated quantity is zero or negative")
        
#         # ✅ Calculate order value HERE (before risk checks)
#         order_price = master_order.price if master_order.price else self._get_market_price(
#             master_order.trading_pair, 
#             master_order.side
#         )
#         order_value = follower_quantity * order_price
        
#         # ✅ Check projected locked balance BEFORE locking funds
#         if follower_account.trading_balance > 0:
#             projected_locked = follower_account.locked_trading_balance + order_value
#             projected_ratio = (projected_locked / follower_account.trading_balance * 100)
            
#             MAX_LOCKED_PERCENTAGE = 80
#             if projected_ratio > MAX_LOCKED_PERCENTAGE:
#                 raise ValidationError(
#                     f"This trade would lock {projected_ratio:.2f}% of trading balance. "
#                     f"Maximum allowed: {MAX_LOCKED_PERCENTAGE}%"
#                 )
        
#         # Check if sufficient available trading balance
#         available_balance = follower_account.available_trading_balance
#         if order_value > available_balance:
#             raise ValidationError(
#                 f"Insufficient trading balance. Required: {order_value}, "
#                 f"Available: {available_balance}"
#             )
        
#         # Apply OTHER risk management checks (but NOT the locked balance check anymore)
#         self._apply_risk_checks(
#             master_order, 
#             subscription, 
#             follower_quantity, 
#             follower_account,
#             order_value  # ✅ Pass order_value as parameter
#         )
        
#         # Lock the trading balance for this order
#         follower_account.locked_trading_balance += order_value
#         follower_account.save(update_fields=['locked_trading_balance'])
        
#         # Create order data
#         order_data = {
#             'trading_pair': master_order.trading_pair,
#             'order_type': master_order.order_type,
#             'side': master_order.side,
#             'quantity': follower_quantity,
#             'price': master_order.price,
#             'stop_price': master_order.stop_price,
#             'source': 'copy_trade',
#             'source_id': master_order.id,
#             'order_value': order_value
#         }
        
#         # Apply stop loss if configured
#         if subscription.stop_loss_percentage:
#             order_data['stop_loss_percentage'] = subscription.stop_loss_percentage
        
#         try:
#             # Execute the order
#             follower_order = self.order_service.create_order(
#                 follower,
#                 order_data
#             )
            
#             # Record the copied trade
#             copied_trade = CopiedTrade.objects.create(
#                 subscription=subscription,
#                 master_order=master_order,
#                 follower_order=follower_order,
#                 status=CopiedTrade.STATUS_COMPLETED
#             )
            
#             logger.info(
#                 f"Successfully copied trade {master_order.id} to "
#                 f"follower {follower.username} as order {follower_order.id}"
#             )
            
#             return copied_trade
            
#         except Exception as e:
#             # Rollback locked balance on failure
#             follower_account.locked_trading_balance -= order_value
#             follower_account.save(update_fields=['locked_trading_balance'])
#             logger.error(f"Failed to execute copied order: {e}")
#             raise
    
#     @transaction.atomic
#     def _create_pending_trade(self, master_order, subscription):
#         """
#         Create a pending trade for manual approval
        
#         Args:
#             master_order: The master order
#             subscription: The subscription in manual mode
#         """
#         # Get follower account
#         follower_account = Account.objects.select_for_update().get(
#             user=subscription.follower
#         )
        
#         # Calculate the quantity that would be used
#         follower_quantity = self._calculate_follower_quantity(
#             master_order,
#             subscription,
#             follower_account
#         )
        
#         if follower_quantity <= 0:
#             raise ValidationError("Calculated quantity is zero or negative")
        
#         # Create pending copied trade (no follower order yet)
#         copied_trade = CopiedTrade.objects.create(
#             subscription=subscription,
#             master_order=master_order,
#             follower_order=None,  # Will be created upon approval
#             status=CopiedTrade.STATUS_PENDING
#         )
        
#         # Optionally send notification to follower
#         # self._notify_follower_pending_trade(subscription.follower, copied_trade)
        
#         logger.info(
#             f"Created pending trade {copied_trade.id} for follower "
#             f"{subscription.follower.username}"
#         )
        
#         return copied_trade
    
#     def execute_pending_trade(self, copied_trade):
#         """
#         Execute a pending trade after manual approval
        
#         Args:
#             copied_trade: The CopiedTrade instance to execute
#         """
#         if copied_trade.status != CopiedTrade.STATUS_PENDING:
#             raise ValidationError("Only pending trades can be executed")
        
#         try:
#             with transaction.atomic():
#                 # Execute as if it were auto
#                 result = self._copy_order_for_follower(
#                     copied_trade.master_order,
#                     copied_trade.subscription
#                 )
                
#                 # Update the original copied_trade with the new follower_order
#                 copied_trade.follower_order = result.follower_order
#                 copied_trade.status = CopiedTrade.STATUS_COMPLETED
#                 copied_trade.save(update_fields=['follower_order', 'status'])
                
#         except Exception as e:
#             copied_trade.status = CopiedTrade.STATUS_FAILED
#             copied_trade.save(update_fields=['status'])
#             raise
    
#     def _calculate_follower_quantity(self, master_order, subscription, follower_account):
#         """
#         Calculate appropriate quantity for follower based on sizing mode
#         Uses Account.trading_balance for calculations
        
#         Args:
#             master_order: The master order
#             subscription: The subscription with sizing settings
#             follower_account: The follower's Account instance
            
#         Returns:
#             Decimal: The quantity for follower's order
#         """
#         # Get available trading balance (excluding locked balance)
#         available_trading_balance = follower_account.available_trading_balance
        
#         if available_trading_balance <= 0:
#             raise ValidationError("No available trading balance")
        
#         if subscription.sizing_mode == CopyTradingSubscription.MODE_FIXED:
#             # Fixed amount per trade
#             if not subscription.fixed_amount_per_trade:
#                 raise ValidationError("Fixed amount not configured")
            
#             allocation = subscription.fixed_amount_per_trade
            
#         else:
#             # Proportional sizing based on copy percentage
#             # Use available trading balance, not total
#             allocation = (
#                 available_trading_balance * 
#                 subscription.copy_percentage / Decimal('100.00')
#             )
        
#         # Apply max position size limit if set
#         if subscription.max_position_size:
#             allocation = min(allocation, subscription.max_position_size)
        
#         # Ensure allocation doesn't exceed available balance
#         if allocation > available_trading_balance:
#             raise ValidationError(
#                 f"Allocation ({allocation}) exceeds available trading balance "
#                 f"({available_trading_balance})"
#             )
        
#         # Calculate quantity based on price
#         if master_order.price:
#             # Limit order with specified price
#             quantity = allocation / master_order.price
#         else:
#             # Market order - use current market price
#             market_price = self._get_market_price(
#                 master_order.trading_pair, 
#                 master_order.side
#             )
#             quantity = allocation / market_price
        
#         # Round to appropriate precision (8 decimal places for crypto)
#         quantity = quantity.quantize(Decimal('0.00000001'))
        
#         return quantity
    
#     def _get_market_price(self, trading_pair, side):
#         """
#         Get current market price for a trading pair
        
#         Args:
#             trading_pair: The TradingPair instance
#             side: 'buy' or 'sell'
            
#         Returns:
#             Decimal: Current market price
#         """
#         try:
#             # ✅ FIX: Pass the entire trading_pair object, not just .symbol
#             ticker = self.order_service.market_service.get_ticker(trading_pair)
            
#             # Use ask price for buy orders, bid price for sell orders
#             market_price = ticker.get('ask') if side == 'buy' else ticker.get('bid')
            
#             if not market_price:
#                 raise ValidationError("Market price not available")
            
#             return Decimal(str(market_price))
            
#         except Exception as e:
#             logger.error(f"Failed to get market price for {trading_pair.symbol}: {e}")
#             raise ValidationError(f"Failed to get market price: {e}")
    
#     def _apply_risk_checks(self, master_order, subscription, quantity, follower_account, order_value):
#         """
#         Apply risk management checks before executing
        
#         Args:
#             master_order: The master order
#             subscription: The subscription
#             quantity: The calculated quantity
#             follower_account: The follower's Account instance
#             order_value: The calculated order value (quantity * price)  # ✅ Added parameter
#         """
#         follower = subscription.follower
        
#         # Check if follower has too many open copy trade positions
#         open_positions = Order.objects.filter(
#             user=follower,
#             status__in=['pending', 'open', 'partially_filled'],
#             source='copy_trade'
#         ).count()
        
#         MAX_OPEN_COPY_POSITIONS = 20
#         if open_positions >= MAX_OPEN_COPY_POSITIONS:
#             raise ValidationError(
#                 f"Maximum open copy positions ({MAX_OPEN_COPY_POSITIONS}) reached"
#             )
        
#         # ✅ REMOVED: The locked balance check (now done before locking)
#         # The locked balance ratio check has been moved to _copy_order_for_follower
        
#         # ✅ Check position size vs AVAILABLE trading balance
#         available_balance = follower_account.available_trading_balance
        
#         if available_balance > 0:
#             position_percentage = (order_value / available_balance * 100)
            
#             MAX_POSITION_PERCENTAGE = 30
            
#             if position_percentage > MAX_POSITION_PERCENTAGE:
#                 raise ValidationError(
#                     f"Position size ({position_percentage:.2f}%) exceeds "
#                     f"maximum allowed ({MAX_POSITION_PERCENTAGE}%) of available balance"
#                 )
#         else:
#             raise ValidationError("No available trading balance")
        
#         # ✅ Check subscription limits
#         if subscription.max_position_size:
#             if order_value > subscription.max_position_size:
#                 raise ValidationError(
#                     f"Position value (${order_value:.2f}) exceeds "
#                     f"subscription limit (${subscription.max_position_size:.2f})"
#                 )
        
#         # Check daily copy trade limit
#         from django.utils import timezone
        
#         today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         today_trades = CopiedTrade.objects.filter(
#             subscription__follower=follower,
#             created_at__gte=today_start,
#             status=CopiedTrade.STATUS_COMPLETED
#         ).count()
        
#         MAX_DAILY_COPY_TRADES = 50
#         if today_trades >= MAX_DAILY_COPY_TRADES:
#             raise ValidationError(
#                 f"Daily copy trade limit ({MAX_DAILY_COPY_TRADES}) reached"
#             )
    
#     def _can_follower_trade(self, follower):
#         """
#         Check if follower is allowed to trade
#         Uses Account status for validation
#         """
#         try:
#             account = follower.account
            
#             # Check account status
#             if account.status != Account.STATUS_ACTIVE:
#                 logger.warning(
#                     f"User {follower.username} cannot trade. "
#                     f"Account status: {account.get_status_display()}"
#                 )
#                 return False
            
#             # Check if user has any trading balance
#             if account.trading_balance <= 0:
#                 logger.warning(
#                     f"User {follower.username} has zero trading balance"
#                 )
#                 return False
            
#             # ✅ ADD THIS - Check against trader's minimum investment
#             try:
#                 subscription = CopyTradingSubscription.objects.filter(
#                     follower=follower,
#                     is_active=True
#                 ).select_related('trader').first()
                
#                 if subscription and account.trading_balance < subscription.trader.minimum_investment:
#                     logger.warning(
#                         f"User {follower.username} balance (${account.trading_balance}) "
#                         f"below minimum (${subscription.trader.minimum_investment})"
#                     )
#                     return False
#             except Exception as e:
#                 logger.error(f"Error checking minimum investment: {e}")
            
#             # Check if user account is active
#             if not follower.is_active:
#                 return False
            
#             return True
            
#         except Account.DoesNotExist:
#             logger.error(f"Account not found for user {follower.username}")
#             return False
    
#     def calculate_subscription_performance(self, subscription):
#         """
#         Calculate performance metrics for a subscription
        
#         Args:
#             subscription: The CopyTradingSubscription instance
            
#         Returns:
#             dict: Performance metrics
#         """
#         trades = CopiedTrade.objects.filter(
#             subscription=subscription,
#             status=CopiedTrade.STATUS_COMPLETED,
#             follower_order__status='filled'
#         ).select_related('follower_order')
        
#         total_profit = Decimal('0.00')
#         total_trades = trades.count()
#         winning_trades = 0
        
#         for trade in trades:
#             # Calculate profit for each trade
#             # This depends on your Order model implementation
#             # profit = self._calculate_trade_profit(trade.follower_order)
#             # total_profit += profit
#             # if profit > 0:
#             #     winning_trades += 1
#             pass
        
#         win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
#         return {
#             'total_profit': total_profit,
#             'total_trades': total_trades,
#             'winning_trades': winning_trades,
#             'losing_trades': total_trades - winning_trades,
#             'win_rate': win_rate,
#         }
    
#     @transaction.atomic
#     def stop_copying_trader(self, subscription, close_positions=False):
#         """
#         Stop copying a trader and optionally close all positions
        
#         Args:
#             subscription: The subscription to stop
#             close_positions: Whether to close existing positions
#         """
#         subscription.is_active = False
#         subscription.save(update_fields=['is_active'])
        
#         if close_positions:
#             # Close all open positions from this subscription
#             open_orders = Order.objects.filter(
#                 user=subscription.follower,
#                 source='copy_trade',
#                 source_id__in=CopiedTrade.objects.filter(
#                     subscription=subscription
#                 ).values_list('master_order_id', flat=True),
#                 status__in=['pending', 'partial']
#             )
            
#             for order in open_orders:
#                 try:
#                     self.order_service.cancel_order(order)
                    
#                     # Unlock the trading balance for cancelled orders
#                     if hasattr(order, 'locked_amount'):
#                         account = order.user.account
#                         account.locked_trading_balance -= order.locked_amount
#                         account.save(update_fields=['locked_trading_balance'])
                        
#                 except Exception as e:
#                     logger.error(f"Failed to cancel order {order.id}: {e}")