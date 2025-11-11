# config/urls.py (COMPLETE VERSION)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Import all viewsets
from users.views import (
    UserRegistrationView, UserProfileView, KYCViewSet
)
from funds.views import (
    WalletViewSet, TransactionViewSet, DepositViewSet, 
    WithdrawalViewSet, 
    # CryptoDepositViewSet
)
from trading.views import (
    TradingPairViewSet, OrderViewSet, PositionViewSet,
    # TradeViewSet
)
from bots.views import TradingBotViewSet, BotTradeViewSet
from copy_trading.views import (
    TraderViewSet, CopyTradingSubscriptionViewSet, CopiedTradeViewSet
)
from signals.views import (
    SignalProviderViewSet, SignalPlanViewSet, SignalSubscriptionViewSet,
    TradingSignalViewSet, SignalNotificationViewSet
)
from loans.views import (
    LoanProductViewSet, LoanViewSet, LoanRepaymentViewSet
)
from referrals.views import ReferralViewSet
from notifications.views import NotificationViewSet

# Create router
router = DefaultRouter()

# User & Auth
router.register(r'kyc', KYCViewSet, basename='kyc')

# Funds
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'deposits', DepositViewSet, basename='deposit')
router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawal')
# router.register(r'crypto-deposits', CryptoDepositViewSet, basename='crypto-deposit')

# Trading
router.register(r'trading-pairs', TradingPairViewSet, basename='trading-pair')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'positions', PositionViewSet, basename='position')
# router.register(r'trades', TradeViewSet, basename='trade')

# Bots
router.register(r'bots', TradingBotViewSet, basename='bot')
router.register(r'bot-trades', BotTradeViewSet, basename='bot-trade')

# Copy Trading
router.register(r'traders', TraderViewSet, basename='trader')
router.register(r'copy-trading', CopyTradingSubscriptionViewSet, 
                basename='copy-trading')
router.register(r'copied-trades', CopiedTradeViewSet, basename='copied-trade')

# Signals
router.register(r'signal-providers', SignalProviderViewSet, 
                basename='signal-provider')
router.register(r'signal-plans', SignalPlanViewSet, basename='signal-plan')
router.register(r'signal-subscriptions', SignalSubscriptionViewSet,
                basename='signal-subscription')
router.register(r'signals', TradingSignalViewSet, basename='signal')
router.register(r'signal-notifications', SignalNotificationViewSet,
                basename='signal-notification')

# Loans
router.register(r'loan-products', LoanProductViewSet, basename='loan-product')
router.register(r'loans', LoanViewSet, basename='loan')
router.register(r'loan-repayments', LoanRepaymentViewSet, 
                basename='loan-repayment')

# Referrals
router.register(r'referrals', ReferralViewSet, basename='referral')

# Notifications
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    path('', include('client.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), 
         name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), 
         name='redoc'),
    
    # Authentication
    path('api/v1/auth/register/', UserRegistrationView.as_view(), 
         name='register'),
    path('api/v1/auth/login/', TokenObtainPairView.as_view(), 
         name='token_obtain_pair'),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view(), 
         name='token_refresh'),
    path('api/v1/auth/me/', UserProfileView.as_view(), name='user-profile'),
    
    # API Routes
    path('api/v1/', include(router.urls)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)




# # config/urls.py (main urls.py)
# from django.contrib import admin
# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from rest_framework_simplejwt.views import (
#     TokenObtainPairView,
#     TokenRefreshView,
# )
# from drf_spectacular.views import (
#     SpectacularAPIView,
#     SpectacularSwaggerView,
#     SpectacularRedocView,
# )

# # Import viewsets
# from users.views import UserRegistrationView, UserProfileView, KYCViewSet
# from funds.views import (
#     WalletViewSet, TransactionViewSet, DepositViewSet, WithdrawalViewSet
# )
# from trading.views import TradingPairViewSet, OrderViewSet, PositionViewSet
# from bots.views import TradingBotViewSet, BotTradeViewSet
# from copy_trading.views import (
#     TraderViewSet, CopyTradingSubscriptionViewSet, CopiedTradeViewSet
# )
# from signals.views import (
#     SignalProviderViewSet, SignalPlanViewSet, SignalSubscriptionViewSet,
#     TradingSignalViewSet, SignalNotificationViewSet
# )
# from loans.views import LoanProductViewSet, LoanViewSet, LoanRepaymentViewSet
# from referrals.views import ReferralViewSet

# # Create router
# router = DefaultRouter()

# # Register viewsets
# router.register(r'kyc', KYCViewSet, basename='kyc')
# router.register(r'wallets', WalletViewSet, basename='wallet')
# router.register(r'transactions', TransactionViewSet, basename='transaction')
# router.register(r'deposits', DepositViewSet, basename='deposit')
# router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawal')
# router.register(r'trading-pairs', TradingPairViewSet, basename='trading-pair')
# router.register(r'orders', OrderViewSet, basename='order')
# router.register(r'positions', PositionViewSet, basename='position')
# router.register(r'bots', TradingBotViewSet, basename='bot')
# router.register(r'bot-trades', BotTradeViewSet, basename='bot-trade')
# router.register(r'traders', TraderViewSet, basename='trader')
# router.register(r'copy-trading', CopyTradingSubscriptionViewSet, 
#                 basename='copy-trading')
# router.register(r'copied-trades', CopiedTradeViewSet, basename='copied-trade')
# router.register(r'signal-providers', SignalProviderViewSet, 
#                 basename='signal-provider')
# router.register(r'signal-plans', SignalPlanViewSet, basename='signal-plan')
# router.register(r'signal-subscriptions', SignalSubscriptionViewSet,
#                 basename='signal-subscription')
# router.register(r'signals', TradingSignalViewSet, basename='signal')
# router.register(r'signal-notifications', SignalNotificationViewSet,
#                 basename='signal-notification')
# router.register(r'loan-products', LoanProductViewSet, basename='loan-product')
# router.register(r'loans', LoanViewSet, basename='loan')
# router.register(r'loan-repayments', LoanRepaymentViewSet, 
#                 basename='loan-repayment')
# router.register(r'referrals', ReferralViewSet, basename='referral')

# urlpatterns = [
#     # Admin
#     path('admin/', admin.site.urls),
    
#     # API Documentation
#     path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
#     path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), 
#          name='swagger-ui'),
#     path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), 
#          name='redoc'),    
    
#     # Authentication
#     path('api/v1/auth/register/', UserRegistrationView.as_view(), 
#          name='register'),
#     path('api/v1/auth/login/', TokenObtainPairView.as_view(), name='login'),
#     path('api/v1/auth/refresh/', TokenRefreshView.as_view(), 
#          name='token_refresh'),
#     path('api/v1/auth/me/', UserProfileView.as_view(), name='profile'),
    
#     # API Routes
#     path('api/v1/', include(router.urls)),
# ]