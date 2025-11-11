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