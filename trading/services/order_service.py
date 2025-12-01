# trading/services/order_service.py - UPDATED to use Account model

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import F
from trading.models import Order, Trade, Position, Transaction, create_transaction
from users.models import Account  # ✅ Changed from funds.models import Wallet
from trading.services.market_service import MarketDataService
import logging

logger = logging.getLogger(__name__)

class OrderExecutionService:
    """Order execution using Account model instead of Wallet"""
    
    def __init__(self):
        self.market_service = MarketDataService()
    
    def handle_expired_orders(self):
        """Handle expired orders - cancel them and unlock funds"""
        now = timezone.now()
        
        # Find all orders that should be expired
        expired_orders = Order.objects.filter(
            status__in=['open', 'pending'],
            expiration_time__isnull=False,
            expiration_time__lte=now
        ).select_related('user', 'trading_pair')
        
        expired_count = 0
        
        for order in expired_orders:
            try:
                with transaction.atomic():
                    # Cancel the expired order
                    self.cancel_expired_order(order)
                    expired_count += 1
                    logger.info(f"Order {order.id} expired and cancelled")
                    
            except Exception as e:
                logger.error(f"Error handling expired order {order.id}: {str(e)}")
                continue
        
        return expired_count

    @transaction.atomic
    def cancel_expired_order(self, order):
        """Cancel an expired order and unlock funds"""
        if order.status not in ['open', 'pending']:
            return
        
        # Calculate remaining quantity that wasn't filled
        remaining_quantity = order.quantity - order.filled_quantity
        
        if remaining_quantity > 0 and order.side == 'buy':
            # Calculate locked amount to unlock
            price = order.price or Decimal('0')
            leverage = Decimal(order.leverage)
            
            position_value = remaining_quantity * price
            required_margin = position_value / leverage if leverage > 1 else position_value
            fee = position_value * order.trading_pair.trading_fee_percentage / 100
            locked_amount = required_margin + fee
            
            # Unlock funds
            self._unlock_trading_funds(order.user, locked_amount)
        
        # Update order status
        order.status = 'expired'
        order.save()
        
        # Create transaction for expiration
        create_transaction(
            user=order.user,
            transaction_type=Transaction.TYPE_ORDER_EXPIRED,
            amount=Decimal('0'),
            balance_type='trading',
            order=order,
            description=f'Order #{order.id} expired for {order.trading_pair.symbol}',
            metadata={
                'symbol': order.trading_pair.symbol,
                'quantity': str(remaining_quantity),
                'order_type': order.order_type
            }
        )
    
    @transaction.atomic
    def create_order(self, user, order_data):
        """Create and validate a new order"""
        trading_pair = order_data['trading_pair']
        
        # Check if trading pair is active
        if not trading_pair.is_active:
            raise ValueError(f"Trading pair {trading_pair.symbol} is not active")
        
        # Check market hours for non-24/7 markets
        if not self._check_market_hours(trading_pair):
            raise ValueError(f"Market for {trading_pair.symbol} is currently closed")
        
        # Validate order data
        self._validate_order_data(order_data, trading_pair)
        
        side = order_data['side']
        quantity = Decimal(str(order_data['quantity']))
        order_type = order_data['order_type']
        leverage = order_data.get('leverage', '1')
        expiration_type = order_data.get('expiration_type', 'gtc')
        leverage_multiplier = Decimal(leverage)
        
        # ✅ Validate account has sufficient trading balance
        self._validate_trading_balance(user, trading_pair, side, quantity, leverage_multiplier, order_data)
        
        # ✅ Lock funds from Account.trading_balance
        locked_amount = self._lock_trading_funds(user, trading_pair, side, quantity, order_data, leverage_multiplier)
        
        try:
            # Create the order
            order = Order.objects.create(
                user=user,
                trading_pair=trading_pair,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=order_data.get('price'),
                stop_price=order_data.get('stop_price'),
                leverage=leverage,
                expiration_type=expiration_type,
                source=order_data.get('source', 'manual'),
                source_id=order_data.get('source_id'),
                status='open'
            )
            
            logger.info(
                f"Order created: {order.id} - {side} {quantity} {trading_pair.symbol} "
                f"with {leverage}x leverage, expires: {expiration_type}"
            )
            
            # Step 5: Execute based on order type
            if order_data['order_type'] == 'market':
                # Market orders execute immediately
                result = self._execute_market_order(order)
                # ✅ Return the Order object, not the full result dict
                return result['order']  # Extract the order from the result
            
            elif order_data['order_type'] in ['limit', 'stop_loss', 'take_profit']:
                # Pending orders - reserve balance
                account.pending_balance += total_required
                account.available_trading_balance -= total_required
                account.save()
                
                # ❌ NO POSITION CREATED YET!
                # ❌ NO TRANSACTION CREATED YET!
                # Order stays as 'pending' until price is reached
            
            return {
                'order': order,
                'position': None,  # No position until filled
                'account_balance': {
                    'trading_balance': str(account.trading_balance),
                    'available_trading_balance': str(account.available_trading_balance),
                    'pending_balance': str(account.pending_balance),
                }
            }
            
        except Exception as e:
            # Rollback fund lock on error
            self._unlock_trading_funds(user, locked_amount)
            logger.error(f"Order creation failed: {str(e)}")
            raise
    
    
    def _validate_order_data(self, order_data, trading_pair):
        """Validate order parameters"""
        quantity = Decimal(str(order_data['quantity']))
        order_type = order_data['order_type']
        
        # Validate quantity
        if quantity < trading_pair.min_order_size:
            raise ValueError(f"Quantity must be at least {trading_pair.min_order_size}")
        
        if quantity > trading_pair.max_order_size:
            raise ValueError(f"Quantity cannot exceed {trading_pair.max_order_size}")
        
        # Validate price for limit orders
        if order_type == 'limit' and not order_data.get('price'):
            raise ValueError("Price is required for limit orders")
        
        # Validate stop price for stop orders
        if order_type in ['stop_loss', 'take_profit'] and not order_data.get('stop_price'):
            raise ValueError("Stop price is required for stop orders")
    
    def _check_market_hours(self, trading_pair):
        """Check if market is open for trading"""
        category = trading_pair.asset_category
        
        # 24/7 markets (crypto)
        if not category.trading_hours_start or not category.trading_hours_end:
            return True
        
        now = timezone.now()
        current_time = now.time()
        current_day = now.isoweekday()
        
        # Check if current day is a trading day
        if current_day not in category.trading_days:
            return False
        
        # Check if within trading hours
        return category.trading_hours_start <= current_time <= category.trading_hours_end
    
    def _validate_trading_balance(self, user, trading_pair, side, quantity, leverage, order_data):
        """✅ NEW: Validate user has sufficient trading balance"""
        # Get user's account
        try:
            account = Account.objects.get(user=user)
        except Account.DoesNotExist:
            raise ValueError("User account not found")
        
        # Check account status
        if account.status != Account.STATUS_ACTIVE:
            raise ValueError(f"Account is {account.status}. Trading not allowed.")
        
        # Only validate for BUY orders (selling uses existing positions)
        if side != 'buy':
            return
        
        # Get price
        price = order_data.get('price')
        if not price:
            ticker = self.market_service.get_ticker(trading_pair)
            price = Decimal(str(ticker['ask']))
        else:
            price = Decimal(str(price))
        
        # Calculate required balance with leverage
        position_value = quantity * price
        
        if leverage > Decimal('1'):
            # With leverage, only need margin (position_value / leverage)
            required_margin = position_value / leverage
        else:
            # No leverage, need full amount
            required_margin = position_value
        
        # Add trading fee
        fee = position_value * trading_pair.trading_fee_percentage / 100
        total_required = required_margin + fee
        
        # Check if user has sufficient trading balance
        if account.trading_balance < total_required:
            raise ValueError(
                f"Insufficient trading balance. "
                f"Required: ${total_required:.2f}, "
                f"Available: ${account.trading_balance:.2f}"
            )
    
    @transaction.atomic
    def _lock_trading_funds(self, user, trading_pair, side, quantity, order_data, leverage=Decimal('1')):
        """✅ NEW: Lock funds from Account.trading_balance"""
        account = Account.objects.select_for_update().get(user=user)
        
        # Only lock funds for BUY orders
        if side == 'buy':
            # Get price
            price = order_data.get('price')
            if not price:
                ticker = self.market_service.get_ticker(trading_pair)
                price = Decimal(str(ticker['ask']))
            else:
                price = Decimal(str(price))
            
            # Calculate required balance with leverage
            position_value = quantity * price
            
            if leverage > Decimal('1'):
                required_margin = position_value / leverage
            else:
                required_margin = position_value
            
            fee = position_value * trading_pair.trading_fee_percentage / 100
            required_balance = required_margin + fee
            
            # Lock from trading_balance
            if account.trading_balance < required_balance:
                raise ValueError(
                    f"Insufficient trading balance. "
                    f"Required: ${required_balance:.2f}, "
                    f"Available: ${account.trading_balance:.2f}"
                )
            
            # Deduct from trading_balance and add to pending_balance
            account.trading_balance = F('trading_balance') - required_balance
            account.pending_balance = F('pending_balance') + required_balance
            account.save()
            account.refresh_from_db()
            
            logger.info(f"Locked ${required_balance:.2f} from user {user.id} trading balance")
            return required_balance
        
        else:  # SELL
            # For selling, we need to check if user has a position
            # The position itself acts as collateral
            # We don't lock funds for selling (we're receiving funds)
            return Decimal('0')
    
    @transaction.atomic
    def _unlock_trading_funds(self, user, amount):
        """✅ NEW: Unlock funds back to Account.trading_balance"""
        if amount <= 0:
            return
        
        try:
            account = Account.objects.select_for_update().get(user=user)
            account.trading_balance = F('trading_balance') + amount
            account.pending_balance = F('pending_balance') - amount
            account.save()
            logger.info(f"Unlocked ${amount:.2f} back to user {user.id} trading balance")
        except Exception as e:
            logger.error(f"Failed to unlock trading funds: {str(e)}")
    
    def check_and_execute_order(self, order):
        """Check if pending order conditions are met and execute if they are"""
        try:
            # Get current market data
            ticker = self.market_service.get_ticker(order.trading_pair)
            current_price = Decimal(str(ticker['last_price']))
            
            # Check if order conditions are met
            if self._should_execute_order(order, current_price):
                return self._execute_pending_order(order, current_price)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking order {order.id}: {str(e)}")
            return False
    
    def _should_execute_order(self, order, current_price):
        """Check if order should be executed based on current price"""
        if order.order_type == 'limit':
            if order.side == 'buy':
                return current_price <= order.price
            else:  # sell
                return current_price >= order.price
        
        elif order.order_type == 'stop_loss':
            if order.side == 'buy':
                return current_price >= order.stop_price
            else:  # sell
                return current_price <= order.stop_price
        
        elif order.order_type == 'take_profit':
            if order.side == 'buy':
                return current_price >= order.stop_price
            else:  # sell
                return current_price <= order.stop_price
        
        return False
    
    @transaction.atomic
    def _execute_market_order(self, order):
        """Execute a market order immediately"""
        try:
            # Get current market price
            ticker = self.market_service.get_ticker(order.trading_pair)
            execution_price = Decimal(str(
                ticker['ask'] if order.side == 'buy' else ticker['bid']
            ))
            
            # Calculate fee
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
            
            # ✅ Settle the trade using Account
            self._settle_trade_account(order, trade)
            
            # ✅ Create transactions for audit trail
            transactions = self._create_order_transactions(order, fee, execution_price)
            
            # Update or create position
            self._update_position(order, trade)
            
            logger.info(
                f"Order executed: {order.id} - {order.side} {order.quantity} "
                f"{order.trading_pair.symbol} @ {execution_price}"
            )
            
            return {
                'order': order,
                'trade': trade,
                'transactions': transactions,
            }
            
        except Exception as e:
            order.status = 'rejected'
            order.save()
            logger.error(f"Order execution failed: {str(e)}")
            raise
    
    @transaction.atomic
    def _settle_trade_account(self, order, trade):
        """✅ NEW: Settle trade using Account model"""
        account = Account.objects.select_for_update().get(user=order.user)
        
        total_cost = trade.quantity * trade.price
        
        if order.side == 'buy':
            # BUY: Remove from pending_balance (already locked)
            # The actual asset is now in the Position (created by _update_position)
            cost_with_fee = total_cost + trade.fee
            account.pending_balance = F('pending_balance') - cost_with_fee
            account.save()
            
            logger.info(
                f"BUY settled: User {order.user.id} bought {trade.quantity} "
                f"{order.trading_pair.symbol} for ${total_cost:.2f}"
            )
            
        else:  # SELL
            # SELL: Add proceeds to trading_balance (minus fee)
            proceeds = total_cost - trade.fee
            account.trading_balance = F('trading_balance') + proceeds
            account.save()
            
            logger.info(
                f"SELL settled: User {order.user.id} sold {trade.quantity} "
                f"{order.trading_pair.symbol} for ${proceeds:.2f}"
            )
        
        account.refresh_from_db()
    
    def _calculate_fee(self, order, price):
        """Calculate trading fee"""
        return (order.quantity * price * 
                order.trading_pair.trading_fee_percentage / 100)
    
    @transaction.atomic
    def _update_position(self, order, trade):
        """Update or create position after trade execution"""
        user = order.user
        trading_pair = order.trading_pair
        position_side = 'long' if order.side == 'buy' else 'short'
        leverage = Decimal(order.leverage)
        
        if order.side == 'buy':
            # BUY: Create or add to position
            try:
                position = Position.objects.select_for_update().get(
                    user=user,
                    trading_pair=trading_pair,
                    side=position_side
                )
                
                # Update existing position (weighted average entry price)
                total_cost = (position.quantity * position.entry_price + 
                             trade.quantity * trade.price)
                total_quantity = position.quantity + trade.quantity
                
                position.quantity = total_quantity
                position.entry_price = total_cost / total_quantity
                position.current_price = trade.price
                position.leverage = ((position.leverage * position.quantity + 
                                    leverage * trade.quantity) / total_quantity)
                position.save()
                
            except Position.DoesNotExist:
                # Create new position
                Position.objects.create(
                    user=user,
                    trading_pair=trading_pair,
                    side=position_side,
                    quantity=trade.quantity,
                    entry_price=trade.price,
                    current_price=trade.price,
                    unrealized_pnl=Decimal('0'),
                    leverage=leverage
                )
        
        else:  # SELL
            # SELL: Reduce or close position
            try:
                position = Position.objects.select_for_update().get(
                    user=user,
                    trading_pair=trading_pair,
                    side='long'  # Can only sell from long positions
                )
                
                if position.quantity < trade.quantity:
                    raise ValueError("Cannot sell more than current position")
                
                # Calculate realized P&L
                realized_pnl = (trade.price - position.entry_price) * trade.quantity
                
                # Update or close position
                if position.quantity == trade.quantity:
                    # Close entire position
                    position.delete()
                    logger.info(f"Position closed for {user.id} - {trading_pair.symbol}")
                else:
                    # Reduce position
                    position.quantity = F('quantity') - trade.quantity
                    position.save()
                    position.refresh_from_db()
                
                # Add realized P&L to trading balance
                if realized_pnl != 0:
                    account = Account.objects.get(user=user)
                    account.trading_balance = F('trading_balance') + realized_pnl
                    account.total_earned = F('total_earned') + realized_pnl if realized_pnl > 0 else F('total_earned')
                    account.save()
                
            except Position.DoesNotExist:
                raise ValueError("No long position to sell from")
    
    @transaction.atomic
    def cancel_order(self, order):
        """Cancel an open order and unlock funds"""
        if order.status not in ['open', 'partially_filled']:
            raise ValueError("Only open or partially filled orders can be cancelled")
        
        remaining_quantity = order.quantity - order.filled_quantity
        
        if order.side == 'buy':
            # Calculate locked amount
            price = order.price or Decimal('0')
            leverage = Decimal(order.leverage)
            
            position_value = remaining_quantity * price
            required_margin = position_value / leverage if leverage > 1 else position_value
            fee = position_value * order.trading_pair.trading_fee_percentage / 100
            locked_amount = required_margin + fee
            
            # Unlock funds
            self._unlock_trading_funds(order.user, locked_amount)
        
        order.status = 'cancelled'
        order.save()
        
        logger.info(f"Order cancelled: {order.id}")
        return order
    
    # @transaction.atomic
    # def close_position(self, position):
    #     """Close an entire position by creating opposite order"""
    #     opposite_side = 'sell' if position.side == 'long' else 'buy'
        
    #     order_data = {
    #         'trading_pair': position.trading_pair,
    #         'order_type': 'market',
    #         'side': opposite_side,
    #         'quantity': position.quantity,
    #         'leverage': str(position.leverage),
    #         'source': 'manual'
    #     }
        
    #     order = self.create_order(position.user, order_data)
        
    #     return order
    
    @transaction.atomic
    def close_position(self, position):
        """Close an entire position by creating opposite order - FIXED"""
        opposite_side = 'sell' if position.side == 'long' else 'buy'
        
        order_data = {
            'trading_pair': position.trading_pair,
            'order_type': 'market', 
            'side': opposite_side,
            'quantity': position.quantity,
            'leverage': str(position.leverage),
            'source': 'manual',
            'is_closing_order': True,
            'original_position_id': position.id
        }
        
        # Create and execute the closing order
        # create_order returns just the Order object for market orders
        closing_order = self.create_order(position.user, order_data)
        
        # Refresh to get the latest status
        closing_order.refresh_from_db()
        
        # Verify order was filled (market orders should execute immediately)
        if closing_order.status == 'filled':
            # Update the original position
            position.status = 'closed'
            position.closed_at = timezone.now()
            position.closing_order = closing_order
            
            # Calculate final P&L using actual execution price
            if position.side == 'long':
                realized_pnl = (closing_order.average_price - position.entry_price) * position.quantity
            else:  # short
                realized_pnl = (position.entry_price - closing_order.average_price) * position.quantity
            
            position.realized_pnl = realized_pnl
            position.exit_price = closing_order.average_price
            position.save()
            
            # Create closing transactions
            transactions = self._create_closing_transactions(position, closing_order)
            
            logger.info(
                f"Position closed: {position.id} - {position.side} {position.quantity} "
                f"{position.trading_pair.symbol} @ {closing_order.average_price} "
                f"P&L: {realized_pnl}"
            )
            
            # Return consistent dict format
            return {
                'order': closing_order,
                'position': position,
                'realized_pnl': realized_pnl,
                'transactions': transactions
            }
        else:
            raise ValueError(f"Closing order failed to execute. Status: {closing_order.status}")
            
    def _create_order_transactions(self, order, fee, execution_price):
        """Create transaction records for order execution"""
        
        investment_amount = order.quantity * execution_price
        
        # Investment transaction
        investment_tx = create_transaction(
            user=order.user,
            transaction_type=Transaction.TYPE_POSITION_OPEN,
            amount=-investment_amount,
            balance_type='trading',
            order=order,
            description=f'Opened {order.side} position on {order.trading_pair.symbol}',
            metadata={
                'symbol': order.trading_pair.symbol,
                'quantity': str(order.quantity),
                'leverage': order.leverage,
                'entry_price': str(execution_price)
            }
        )
        
        # Fee transaction
        fee_tx = create_transaction(
            user=order.user,
            transaction_type=Transaction.TYPE_ORDER_FEE,
            amount=-fee,
            balance_type='trading',
            order=order,
            description=f'Trading fee for order #{order.id}'
        )
        
        return {
            'investment': investment_tx,
            'fee': fee_tx
        }
        
        
    def _create_closing_transactions(self, position, closing_order):
        """Create transaction records for position closing"""
        
        # Calculate net amount returned (original investment + P&L - fees)
        original_investment = (position.quantity * position.entry_price) / position.leverage
        net_amount = original_investment + position.realized_pnl - closing_order.fee
        
        transactions = {}
        
        # Position close transaction
        transactions['close'] = create_transaction(
            user=position.user,
            transaction_type=Transaction.TYPE_POSITION_CLOSE,
            amount=net_amount,
            balance_type='trading',
            order=closing_order,
            position=position,
            description=f'Closed {position.side} position on {position.trading_pair.symbol}',
            metadata={
                'symbol': position.trading_pair.symbol,
                'quantity': str(position.quantity),
                'entry_price': str(position.entry_price),
                'exit_price': str(position.exit_price),
                'realized_pnl': str(position.realized_pnl),
                'leverage': str(position.leverage)
            }
        )
        
        # Fee transaction
        if closing_order.fee > 0:
            transactions['fee'] = create_transaction(
                user=position.user,
                transaction_type=Transaction.TYPE_ORDER_FEE,
                amount=-closing_order.fee,
                balance_type='trading',
                order=closing_order,
                description=f'Closing fee for position #{position.id}'
            )
        
        # P&L transaction
        if position.realized_pnl != 0:
            tx_type = Transaction.TYPE_PROFIT if position.realized_pnl > 0 else Transaction.TYPE_LOSS
            transactions['pnl'] = create_transaction(
                user=position.user,
                transaction_type=tx_type,
                amount=position.realized_pnl,
                balance_type='trading',
                position=position,
                description=f'Trading {"profit" if position.realized_pnl > 0 else "loss"} from {position.trading_pair.symbol}',
                metadata={'position_id': position.id}
            )
        
        return transactions    