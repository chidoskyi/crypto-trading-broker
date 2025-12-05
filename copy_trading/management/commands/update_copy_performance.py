# copy_trading/management/commands/update_copy_performance.py
from django.core.management.base import BaseCommand
from django.db import transaction
from copy_trading.models import CopyTradingPerformance, CopyTradingSubscription, Trader
from decimal import Decimal


class Command(BaseCommand):
    help = 'Update copy trading performance metrics for all subscriptions and traders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subscription-id',
            type=int,
            help='Update only a specific subscription by ID'
        )
        parser.add_argument(
            '--trader-id',
            type=int,
            help='Update only subscriptions for a specific trader by ID'
        )
        parser.add_argument(
            '--update-traders',
            action='store_true',
            help='Also update trader performance metrics'
        )

    def handle(self, *args, **options):
        subscription_id = options.get('subscription_id')
        trader_id = options.get('trader_id')
        update_traders = options.get('update_traders')
        
        # Update subscription performances
        if subscription_id:
            # Update specific subscription
            try:
                performance, created = CopyTradingPerformance.objects.get_or_create(
                    subscription_id=subscription_id
                )
                performance.update_metrics()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated performance for subscription {subscription_id}'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error updating subscription {subscription_id}: {e}')
                )
        
        elif trader_id:
            # Update all subscriptions for a specific trader
            subscriptions = CopyTradingSubscription.objects.filter(trader_id=trader_id)
            self.stdout.write(f'Updating {subscriptions.count()} subscriptions for trader {trader_id}...')
            
            updated = 0
            failed = 0
            
            for subscription in subscriptions:
                try:
                    performance, created = CopyTradingPerformance.objects.get_or_create(
                        subscription=subscription
                    )
                    performance.update_metrics()
                    updated += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Error updating subscription {subscription.id}: {e}'
                        )
                    )
                    failed += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Updated {updated} subscriptions, {failed} failed'
                )
            )
        
        else:
            # Update all subscriptions
            subscriptions = CopyTradingSubscription.objects.all()
            total = subscriptions.count()
            self.stdout.write(f'Updating performance for {total} subscriptions...')
            
            updated = 0
            failed = 0
            
            for subscription in subscriptions:
                try:
                    performance, created = CopyTradingPerformance.objects.get_or_create(
                        subscription=subscription
                    )
                    performance.update_metrics()
                    updated += 1
                    
                    if updated % 10 == 0:
                        self.stdout.write(f'Progress: {updated}/{total}')
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Error updating subscription {subscription.id}: {e}'
                        )
                    )
                    failed += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Completed: {updated} updated, {failed} failed'
                )
            )
        
        # Update trader performance if requested
        if update_traders:
            self.stdout.write('\nUpdating trader performance metrics...')
            traders = Trader.objects.filter(is_active=True)
            
            updated_traders = 0
            failed_traders = 0
            
            for trader in traders:
                try:
                    trader.update_performance_metrics()
                    updated_traders += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Error updating trader {trader.display_name}: {e}'
                        )
                    )
                    failed_traders += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Updated {updated_traders} traders, {failed_traders} failed'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('\n✓ Performance update complete!'))