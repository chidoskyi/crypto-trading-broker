from django.contrib import admin
from funds.models import CryptoWalletAddress, DepositMethod, PendingDeposit, Wallet, Transaction, Deposit, Withdrawal

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


@admin.register(DepositMethod)
class DepositMethodAdmin(admin.ModelAdmin):
    list_display = ['currency', 'network', 'name', 'min_deposit', 
                   'required_confirmations', 'is_active']
    list_filter = ['currency', 'network', 'is_active']
    search_fields = ['name', 'currency']

@admin.register(CryptoWalletAddress)
class CryptoWalletAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'currency', 'network', 'address', 
                   'total_deposits', 'total_received', 'is_active']
    list_filter = ['currency', 'network', 'is_active']
    search_fields = ['user__email', 'address']
    readonly_fields = ['address', 'qr_code', 'total_received', 
                      'total_deposits', 'created_at']
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'currency', 'network')
        }),
        ('Address Details', {
            'fields': ('address', 'qr_code', 'derivation_path', 'address_index')
        }),
        ('Statistics', {
            'fields': ('total_received', 'total_deposits', 'last_checked')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        })
    )

@admin.register(PendingDeposit)
class PendingDepositAdmin(admin.ModelAdmin):
    list_display = ['user', 'currency', 'amount', 'confirmations',
                   'required_confirmations', 'status', 'detected_at']
    list_filter = ['currency', 'network', 'status', 'detected_at']
    search_fields = ['user__email', 'tx_hash', 'from_address']
    readonly_fields = ['detected_at', 'completed_at']
    
    fieldsets = (
        ('User & Amount', {
            'fields': ('user', 'wallet_address', 'currency', 'network', 'amount')
        }),
        ('Transaction Details', {
            'fields': ('tx_hash', 'from_address', 'block_number')
        }),
        ('Confirmation Status', {
            'fields': ('confirmations', 'required_confirmations', 'status')
        }),
        ('Timestamps', {
            'fields': ('detected_at', 'completed_at')
        }),
        ('Link', {
            'fields': ('transaction',)
        })
    )
    
    def has_add_permission(self, request):
        return False  # Can only be created by system
