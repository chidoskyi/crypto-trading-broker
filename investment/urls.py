from . import views
from django.urls import path, re_path
from .cron_job_views import cron_health_check, cron_process_investments, cron_update_market_prices, cron_execute_pending_orders, cron_run_trading_bots, cron_process_copy_trades, cron_calculate_loan_interest, cron_process_referral_rewards, cron_check_kyc_expiry, cron_check_crypto_deposits, cron_generate_qr_codes, cron_run_all_tasks, cron_expire_orders, cron_update_positions

urlpatterns = [
    # path('make-investment', views.make_investment, name="make_investment"),
    # path('withdrawal/', views.withdrawal_view, name='withdrawal'),
    # path('withdrawal/confirmation/', views.withdrawal_confirmation, name='withdrawal_confirmation'),
    # path('deposit-history/', views.deposit_history, name='deposit_history'),
    # path('withdraw-history/', views.withdraw_history, name='withdraw_history'),
    # path('earning-history/', views.earning_history, name='earning-history'),
    # # path('security/', views.security_and_2fa_view, name='security'),
    # path('transactions/', views.transactions, name='transactions'),
    # path('dashboard', views.account_details, name='dashboard'),
    # path('active-investment/', views.active_investment, name='active_investment'),
    # path('notifications/', views.get_notifications, name='get_notifications'),
    # path('notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    # path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    # path('calculate-investment/', views.calculate_investment, name='calculate_investment'),
    
    # cron jobs
    # Health check (no auth required)
    path('cron/health/', cron_health_check, name='cron_health'),
    
    # Individual task endpoints
    path('cron/process-investments/', cron_process_investments, name='cron_investments'),
    path('cron/update-market-prices/', cron_update_market_prices, name='cron_market_prices'),
    path('cron/execute-orders/', cron_execute_pending_orders, name='cron_execute_orders'),
    path('cron/run-trading-bots/', cron_run_trading_bots, name='cron_trading_bots'),
    path('cron/process-copy-trades/', cron_process_copy_trades, name='cron_copy_trades'),
    path('cron/calculate-loan-interest/', cron_calculate_loan_interest, name='cron_loan_interest'),
    path('cron/process-referrals/', cron_process_referral_rewards, name='cron_referrals'),
    path('cron/check-kyc-expiry/', cron_check_kyc_expiry, name='cron_kyc'),
    path('cron/check-crypto-deposits/', cron_check_crypto_deposits, name='cron_deposits'),
    path('cron/generate-qr-codes/', cron_generate_qr_codes, name='cron_qr_codes'),
    path('cron/expire-orders/', cron_expire_orders, name='cron_expire_orders'),
    path('cron/update-positions/', cron_update_positions, name='cron_update_positions'),
    
    # Master endpoint (runs all tasks)
    path('cron/run-all/', cron_run_all_tasks, name='cron_run_all'),
    
]
