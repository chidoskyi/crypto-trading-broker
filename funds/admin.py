from django.contrib import admin
from funds.models import Wallet, Transaction, Deposit, Withdrawal

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'balance', 'currency', 'locked_balance', 'created_at', 'updated_at']
    search_fields = ['user__username']
    list_filter = ['created_at', 'updated_at']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'reference_id', 'amount', 'transaction_type', 'fee', 'currency', 'status', 'external_id', 'notes', 'created_at', 'completed_at']
    search_fields = ['user__username']
    list_filter = ['created_at', 'transaction_type', 'completed_at', 'status']

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['id', 'transaction', 'payment_method', 'payment_details', 'created_at']
    search_fields = ['user__username']
    list_filter = ['created_at']

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['id', 'destination_type', 'transaction', 'destination_details', 'approved_by', 'created_at']
    search_fields = ['user__username']
    list_filter = ['created_at']
