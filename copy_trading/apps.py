from django.apps import AppConfig


class CopyTradingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'copy_trading'
    
    def ready(self):
        import copy_trading.signals
