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