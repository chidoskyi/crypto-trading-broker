# copy_trading/services/copy_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

from copy_trading.models import CopyTradingSubscription, CopiedTrade
from trading.services.order_service import OrderExecutionService
from trading.models import Order

logger = logging.getLogger(__name__)


class CopyTradingService:
    """
    Service for executing and managing copy trades
    
    Handles:
    - Trade replication from master to followers
    - Position sizing calculations
    - Risk management
    - Trade execution
    """
    
    def __init__(self):
        self.order_service = OrderExecutionService()
    
    def replicate_trade(self, master_order):
        """
        Replicate a master trader's order to all active followers
        
        Args:
            master_order: The master trader's order to replicate
            
        Returns:
            dict: Summary of replication results
        """
        try:
            trader = master_order.user.trader
        except AttributeError:
            logger.error(f"Order {master_order.id} user is not a trader")
            return {
                'success': False,
                'error': 'User is not a registered trader'
            }
        
        # Get active subscribers
        subscriptions = CopyTradingSubscription.objects.filter(
            trader=trader,
            is_active=True
        ).select_related('follower', 'follower__profile')
        
        results = {
            'total_followers': subscriptions.count(),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for subscription in subscriptions:
            try:
                # Check execution mode
                if subscription.execution_mode == CopyTradingSubscription.EXEC_AUTO:
                    self._copy_order_for_follower(master_order, subscription)
                    results['successful'] += 1
                else:
                    # Create pending trade for manual approval
                    self._create_pending_trade(master_order, subscription)
                    results['successful'] += 1
                    
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
        """
        Copy an order for a specific follower with auto execution
        
        Args:
            master_order: The master order to copy
            subscription: The subscription defining copy settings
        """
        follower = subscription.follower
        
        # Validate follower can trade
        if not self._can_follower_trade(follower):
            raise ValidationError(f"Follower {follower.username} cannot trade")
        
        # Calculate position size
        try:
            follower_quantity = self._calculate_follower_quantity(
                master_order,
                subscription
            )
        except Exception as e:
            raise ValidationError(f"Failed to calculate position size: {e}")
        
        if follower_quantity <= 0:
            raise ValidationError("Calculated quantity is zero or negative")
        
        # Apply risk management checks
        self._apply_risk_checks(master_order, subscription, follower_quantity)
        
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
        
        # Apply stop loss if configured
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
                status=CopiedTrade.STATUS_COMPLETED
            )
            
            logger.info(
                f"Successfully copied trade {master_order.id} to "
                f"follower {follower.username} as order {follower_order.id}"
            )
            
            return copied_trade
            
        except Exception as e:
            logger.error(f"Failed to execute copied order: {e}")
            raise
    
    @transaction.atomic
    def _create_pending_trade(self, master_order, subscription):
        """
        Create a pending trade for manual approval
        
        Args:
            master_order: The master order
            subscription: The subscription in manual mode
        """
        # Calculate the quantity that would be used
        follower_quantity = self._calculate_follower_quantity(
            master_order,
            subscription
        )
        
        if follower_quantity <= 0:
            raise ValidationError("Calculated quantity is zero or negative")
        
        # Create a placeholder follower order (not yet executed)
        # This depends on your Order model implementation
        # You might create it with a 'pending_approval' status
        
        copied_trade = CopiedTrade.objects.create(
            subscription=subscription,
            master_order=master_order,
            follower_order=None,  # Will be created upon approval
            status=CopiedTrade.STATUS_PENDING
        )
        
        # Optionally send notification to follower
        # self._notify_follower_pending_trade(subscription.follower, copied_trade)
        
        return copied_trade
    
    def execute_pending_trade(self, copied_trade):
        """
        Execute a pending trade after manual approval
        
        Args:
            copied_trade: The CopiedTrade instance to execute
        """
        if copied_trade.status != CopiedTrade.STATUS_PENDING:
            raise ValidationError("Only pending trades can be executed")
        
        try:
            with transaction.atomic():
                # Execute as if it were auto
                self._copy_order_for_follower(
                    copied_trade.master_order,
                    copied_trade.subscription
                )
                
                copied_trade.status = CopiedTrade.STATUS_COMPLETED
                copied_trade.save(update_fields=['status'])
                
        except Exception as e:
            copied_trade.status = CopiedTrade.STATUS_FAILED
            copied_trade.save(update_fields=['status'])
            raise
    
    def _calculate_follower_quantity(self, master_order, subscription):
        """
        Calculate appropriate quantity for follower based on sizing mode
        
        Args:
            master_order: The master order
            subscription: The subscription with sizing settings
            
        Returns:
            Decimal: The quantity for follower's order
        """
        follower = subscription.follower
        
        # Get follower's available balance
        try:
            follower_wallet = follower.wallet_set.get(
                currency=master_order.trading_pair.quote_currency
            )
        except Exception:
            raise ValidationError(
                f"Follower wallet not found for {master_order.trading_pair.quote_currency}"
            )
        
        if subscription.sizing_mode == CopyTradingSubscription.MODE_FIXED:
            # Fixed amount per trade
            if not subscription.fixed_amount_per_trade:
                raise ValidationError("Fixed amount not configured")
            
            allocation = subscription.fixed_amount_per_trade
            
        else:
            # Proportional sizing based on copy percentage
            allocation = (
                follower_wallet.balance * 
                subscription.copy_percentage / Decimal('100.00')
            )
        
        # Apply max position size limit if set
        if subscription.max_position_size:
            allocation = min(allocation, subscription.max_position_size)
        
        # Ensure sufficient balance
        if allocation > follower_wallet.balance:
            raise ValidationError(
                f"Insufficient balance. Required: {allocation}, "
                f"Available: {follower_wallet.balance}"
            )
        
        # Calculate quantity based on price
        if master_order.price:
            # Limit order with specified price
            quantity = allocation / master_order.price
        else:
            # Market order - use current market price
            try:
                ticker = self.order_service.market_service.get_ticker(
                    master_order.trading_pair.symbol
                )
                market_price = ticker.get('ask') if master_order.side == 'buy' else ticker.get('bid')
                
                if not market_price:
                    raise ValidationError("Market price not available")
                
                quantity = allocation / Decimal(str(market_price))
            except Exception as e:
                raise ValidationError(f"Failed to get market price: {e}")
        
        # Round to appropriate precision
        # This depends on your trading pair configuration
        quantity = quantity.quantize(Decimal('0.00000001'))
        
        return quantity
    
    def _apply_risk_checks(self, master_order, subscription, quantity):
        """
        Apply risk management checks before executing
        
        Args:
            master_order: The master order
            subscription: The subscription
            quantity: The calculated quantity
            
        Raises:
            ValidationError: If risk checks fail
        """
        follower = subscription.follower
        
        # Check if follower has too many open positions
        open_positions = Order.objects.filter(
            user=follower,
            status__in=['pending', 'partial'],
            source='copy_trade'
        ).count()
        
        MAX_OPEN_COPY_POSITIONS = 10  # Configure this
        if open_positions >= MAX_OPEN_COPY_POSITIONS:
            raise ValidationError(
                f"Maximum open copy positions ({MAX_OPEN_COPY_POSITIONS}) reached"
            )
        
        # Check position size vs total portfolio
        try:
            total_balance = follower.wallet_set.aggregate(
                total=Sum('balance')
            )['total'] or Decimal('0')
            
            position_value = quantity * (master_order.price or Decimal('1'))
            position_percentage = (position_value / total_balance * 100) if total_balance > 0 else 100
            
            MAX_POSITION_PERCENTAGE = 20  # Configure this
            if position_percentage > MAX_POSITION_PERCENTAGE:
                raise ValidationError(
                    f"Position size ({position_percentage:.2f}%) exceeds "
                    f"maximum allowed ({MAX_POSITION_PERCENTAGE}%)"
                )
        except Exception as e:
            logger.warning(f"Could not perform position size check: {e}")
        
        # Additional risk checks can be added here
        # - Daily loss limits
        # - Trade frequency limits
        # - Correlation checks
        # etc.
    
    def _can_follower_trade(self, follower):
        """
        Check if follower is allowed to trade
        
        Args:
            follower: The User instance
            
        Returns:
            bool: True if follower can trade
        """
        # Check if user account is active
        if not follower.is_active:
            return False
        
        # Check if user has completed KYC (if required)
        # if hasattr(follower, 'profile') and not follower.profile.kyc_verified:
        #     return False
        
        # Check if user has any restrictions
        # if hasattr(follower, 'restrictions') and follower.restrictions.trading_disabled:
        #     return False
        
        return True
    
    def calculate_subscription_performance(self, subscription):
        """
        Calculate performance metrics for a subscription
        
        Args:
            subscription: The CopyTradingSubscription instance
            
        Returns:
            dict: Performance metrics
        """
        trades = CopiedTrade.objects.filter(
            subscription=subscription,
            status=CopiedTrade.STATUS_COMPLETED,
            follower_order__status='filled'
        ).select_related('follower_order')
        
        total_profit = Decimal('0.00')
        total_trades = trades.count()
        winning_trades = 0
        
        for trade in trades:
            # Calculate profit for each trade
            # This is a placeholder - implement based on your Order model
            # profit = self._calculate_trade_profit(trade.follower_order)
            # total_profit += profit
            # if profit > 0:
            #     winning_trades += 1
            pass
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_profit': total_profit,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': win_rate,
        }
    
    def stop_copying_trader(self, subscription, close_positions=False):
        """
        Stop copying a trader and optionally close all positions
        
        Args:
            subscription: The subscription to stop
            close_positions: Whether to close existing positions
        """
        with transaction.atomic():
            subscription.is_active = False
            subscription.save(update_fields=['is_active'])
            
            if close_positions:
                # Close all open positions from this subscription
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
                    except Exception as e:
                        logger.error(f"Failed to cancel order {order.id}: {e}")