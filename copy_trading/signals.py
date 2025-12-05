from django.db.models.signals import post_save
from django.dispatch import receiver
from trading.models import Order
from copy_trading.services.copy_service import CopyTradingService
import logging

logger = logging.getLogger(__name__)


from django.db.models import Sum, Count, Avg, Q
from decimal import Decimal
from .models import CopiedTrade, Trader, CopyTradingPerformance
from trading.models import Position


@receiver(post_save, sender=Position)
def update_performance_on_position_close(sender, instance, created, **kwargs):
    """
    Update copy trading performance metrics when a position is closed
    """
    # Only process closed positions with realized P&L
    if instance.status == 'closed' and instance.realized_pnl is not None:
        try:
            # Check if this position is from a copied trade
            copied_trade = CopiedTrade.objects.filter(
                follower_order=instance.order,
                status=CopiedTrade.STATUS_COMPLETED
            ).select_related('subscription').first()
            
            if copied_trade:
                # Update the subscription's performance metrics
                performance, _ = CopyTradingPerformance.objects.get_or_create(
                    subscription=copied_trade.subscription
                )
                performance.update_metrics()
                
                logger.info(
                    f"Updated performance for subscription {copied_trade.subscription.id} "
                    f"after closing position {instance.id}"
                )
                
        except Exception as e:
            logger.error(
                f"Error updating performance from position {instance.id}: {e}",
                exc_info=True
            )


@receiver(post_save, sender=Position)
def update_trader_performance_on_position_close(sender, instance, created, **kwargs):
    """
    Update trader's overall performance metrics when any of their positions close
    """
    # Only process closed positions
    if instance.status == 'closed' and instance.realized_pnl is not None:
        try:
            # Check if the user is a trader
            trader = Trader.objects.filter(user=instance.user).first()
            
            if trader:
                # Update trader's performance metrics
                trader.update_performance_metrics()
                
                logger.info(
                    f"Updated trader performance for {trader.display_name} "
                    f"after closing position {instance.id}"
                )
                
        except Exception as e:
            logger.error(
                f"Error updating trader performance from position {instance.id}: {e}",
                exc_info=True
            )


@receiver(post_save, sender=Order)
def replicate_master_trader_order(sender, instance, created, **kwargs):
    """
    Automatically replicate master trader orders to followers
    Only triggers for newly created orders from traders
    """
    if created and instance.status in ['open', 'filled']:
        try:
            # Check if the user is a trader
            trader = Trader.objects.filter(
                user=instance.user,
                is_active=True
            ).first()
            
            if trader:
                # Import here to avoid circular imports
                from copy_trading.services.copy_service import CopyTradingService
                
                # Replicate to all active followers
                service = CopyTradingService()
                results = service.replicate_trade(instance)
                
                logger.info(
                    f"Replicated order {instance.id} from trader {trader.display_name}: "
                    f"{results['successful']} successful, "
                    f"{results['failed']} failed, "
                    f"{results['skipped']} skipped"
                )
                
        except Exception as e:
            logger.error(
                f"Error replicating order {instance.id}: {e}",
                exc_info=True
            )

@receiver(post_save, sender=CopiedTrade)
def update_trader_stats(sender, instance, created, **kwargs):
    """Update trader statistics when a copied trade is completed"""
    
    if instance.status != CopiedTrade.STATUS_COMPLETED:
        return
    
    trader = instance.subscription.trader
    
    # Get all completed copied trades for this trader
    completed_trades = CopiedTrade.objects.filter(
        subscription__trader=trader,
        status=CopiedTrade.STATUS_COMPLETED,
        follower_order__isnull=False
    ).select_related('follower_order')
    
    # Calculate statistics
    total_trades = completed_trades.count()
    
    # Calculate win rate and profits
    winning_trades = 0
    total_profit = Decimal('0.00')
    
    for trade in completed_trades:
        order = trade.follower_order
        if order.status == 'filled' and hasattr(order, 'realized_pnl'):
            profit = order.realized_pnl or Decimal('0.00')
            total_profit += profit
            if profit > 0:
                winning_trades += 1
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else Decimal('0.00')
    
    # Update trader model
    trader.total_trades = total_trades
    trader.win_rate = win_rate
    trader.total_profit = total_profit
    
    # Calculate profit percentage (needs initial investment tracking)
    # This is a simplified version - adjust based on your needs
    if total_trades > 0:
        avg_profit_per_trade = total_profit / total_trades
        trader.profit_percentage = avg_profit_per_trade  # Adjust calculation as needed
    
    trader.save(update_fields=[
        'total_trades', 'win_rate', 'total_profit', 'profit_percentage'
    ])


@receiver(post_save, sender=Order)
def replicate_trader_order(sender, instance, created, **kwargs):
    """
    Automatically replicate orders from master traders to followers
    
    Triggers when:
    - A new order is created
    - The order is from a registered trader
    - The order should be copied (based on source)
    """
    # Only process new orders
    if not created:
        return
    
    # Don't copy orders that are already copy trades
    if instance.source == 'copy_trade':
        return
    
    # Check if the user is a trader
    try:
        trader = instance.user.trader
        if not trader.is_active:
            return
    except AttributeError:
        # User is not a trader
        return
    
    # Replicate the trade asynchronously (recommended)
    try:
        # If using Celery:
        # from copy_trading.tasks import replicate_trade_task
        # replicate_trade_task.delay(instance.id)
        
        # Synchronous execution (for development/testing):
        service = CopyTradingService()
        results = service.replicate_trade(instance)
        logger.info(f"Replicated order {instance.id}: {results}")
        
    except Exception as e:
        logger.error(f"Failed to replicate order {instance.id}: {e}", exc_info=True)
        
        
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from trading.models import Order
# from copy_trading.services.copy_service import CopyTradingService
# from copy_trading.models import Trader
# import logging

# logger = logging.getLogger(__name__)


# @receiver(post_save, sender=Order)
# def replicate_trade_on_order_creation(sender, instance, created, **kwargs):
#     """
#     Automatically replicate trades when a master trader creates an order
    
#     This signal fires whenever an Order is created or updated.
#     We only want to replicate on creation and only for master traders.
#     """
#     # Only process newly created orders
#     if not created:
#         return
    
#     # Check if the user is a registered trader
#     try:
#         trader = Trader.objects.get(user=instance.user, is_active=True)
#     except Trader.DoesNotExist:
#         # User is not a master trader, nothing to copy
#         return
    
#     # Only replicate certain order types (customize as needed)
#     # You might want to skip certain internal orders
#     if instance.source == 'copy_trade':
#         # Don't copy trades that are already copies
#         return
    
#     # Only replicate filled or pending orders (not cancelled/rejected)
#     if instance.status not in ['pending', 'filled', 'partial']:
#         return
    
#     logger.info(
#         f"Replicating trade from master trader {trader.display_name} "
#         f"(Order #{instance.id})"
#     )
    
#     # Execute replication asynchronously (recommended for production)
#     try:
#         service = CopyTradingService()
#         results = service.replicate_trade(instance)
        
#         logger.info(
#             f"Trade replication completed. "
#             f"Successful: {results['successful']}, Failed: {results['failed']}"
#         )
        
#         if results['errors']:
#             for error in results['errors']:
#                 logger.error(
#                     f"Failed to copy for {error['follower']}: {error['error']}"
#                 )
    
#     except Exception as e:
#         logger.error(
#             f"Error replicating trade from order {instance.id}: {e}",
#             exc_info=True
#         )