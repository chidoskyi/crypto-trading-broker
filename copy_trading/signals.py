from django.db.models.signals import post_save
from django.dispatch import receiver
from trading.models import Order
from copy_trading.services.copy_service import CopyTradingService
import logging

logger = logging.getLogger(__name__)


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