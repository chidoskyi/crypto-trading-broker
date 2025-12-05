from django.core.management.base import BaseCommand
from copy_trading.models import Trader

class Command(BaseCommand):
    help = 'Update performance metrics for all traders'

    def handle(self, *args, **options):
        traders = Trader.objects.filter(is_active=True)
        
        for trader in traders:
            try:
                trader.update_performance_metrics()
                self.stdout.write(
                    self.style.SUCCESS(f'Updated metrics for {trader.display_name}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to update {trader.display_name}: {e}')
                )