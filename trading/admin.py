# trading/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin
from trading.models import TradingPair, Order, Trade, Position, AssetCategory, Transaction
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.db.models import Sum
from decimal import Decimal
from .models import Transaction


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'description', 'is_active', 'trading_hours_start', 'trading_hours_end', 'trading_days']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(TradingPair)
class TradingPairAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'market_type', 'is_active', 'price_change_24h','last_price', 'exchange','volume_24h','market_cap']
    list_filter = ['market_type', 'is_active', 'exchange']
    search_fields = ['symbol', 'base_currency', 'quote_currency', 'name', 'exchange']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'trading_pair', 'side', 'order_type',
                   'quantity', 'status', 'created_at']
    list_filter = ['status', 'order_type', 'side', 'source']
    search_fields = ['user__email', 'trading_pair__symbol']
    readonly_fields = ['created_at', 'updated_at', 'executed_at']

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'quantity', 'price', 'fee', 'executed_at']
    list_filter = ['executed_at']
    search_fields = ['order__user__email']

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['user', 'trading_pair', 'side', 'quantity', 
                   'unrealized_pnl', 'opened_at']
    list_filter = ['side', 'opened_at']
    search_fields = ['user__email', 'trading_pair__symbol']
    
    

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin configuration for Transaction model"""
    
    list_display = [
        'id',
        'user',
        'transaction_type_display',
        'amount_display',
        'balance_type_display',
        'status_display',
        'balance_before',
        'balance_after',
        'created_at',
        'related_objects'
    ]
    
    list_filter = [
        'transaction_type',
        'balance_type',
        'status',
        'created_at',
        'user'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'description',
        'reference_id',
        'order__id',
        'position__id'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'completed_at',
        'balance_before',
        'balance_after',
        'transaction_summary',
        'metadata_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user',
                'transaction_type',
                'balance_type',
                'amount',
                'status',
                'transaction_summary'
            )
        }),
        ('Balance Information', {
            'fields': (
                'balance_before',
                'balance_after',
                'position_side'
            )
        }),
        ('Related Objects', {
            'fields': (
                'order',
                'position'
            )
        }),
        ('Additional Information', {
            'fields': (
                'description',
                'reference_id',
                'metadata_display'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'completed_at'
            )
        }),
    )
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    def transaction_type_display(self, obj):
        """Color-coded transaction type"""
        colors = {
            Transaction.TYPE_DEPOSIT: 'green',
            Transaction.TYPE_WITHDRAWAL: 'red',
            Transaction.TYPE_PROFIT: 'green',
            Transaction.TYPE_LOSS: 'red',
            Transaction.TYPE_ORDER_FEE: 'orange',
            Transaction.TYPE_TRANSFER_TO_TRADING: 'blue',
            Transaction.TYPE_TRANSFER_FROM_TRADING: 'blue',
        }
        color = colors.get(obj.transaction_type, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_transaction_type_display()
        )
    transaction_type_display.short_description = 'Type'
    transaction_type_display.admin_order_field = 'transaction_type'
    
    def amount_display(self, obj):
        """Color-coded amount with proper sign"""
        color = 'green' if obj.amount >= 0 else 'red'
        sign = '+' if obj.amount >= 0 else ''
        
        # --- FIX IS HERE ---
        # 1. Format the number separately using an f-string or .format()
        # 2. Pass the final formatted number string to format_html
        formatted_amount = f"{abs(obj.amount):,.2f}"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>', # Removed {:,.2f}
            color,
            sign,
            formatted_amount # Passed as a formatted string
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def balance_type_display(self, obj):
        """Styled balance type"""
        color = 'blue' if obj.balance_type == Transaction.BALANCE_TRADING else 'purple'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_balance_type_display()
        )
    balance_type_display.short_description = 'Balance'
    balance_type_display.admin_order_field = 'balance_type'
    
    def status_display(self, obj):
        """Color-coded status"""
        colors = {
            Transaction.STATUS_COMPLETED: 'green',
            Transaction.STATUS_PENDING: 'orange',
            Transaction.STATUS_FAILED: 'red',
            Transaction.STATUS_CANCELLED: 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def related_objects(self, obj):
        """Show related order and position"""
        links = []
        if obj.order:
            links.append(f'Order: #{obj.order.id}')
        if obj.position:
            links.append(f'Position: #{obj.position.id}')
        return ', '.join(links) if links else '-'
    related_objects.short_description = 'Related Objects'
    
    def transaction_summary(self, obj):
        """Display transaction summary"""
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<strong>Transaction Summary:</strong><br>'
            '{} - {} balance<br>'
            'User: {}<br>'
            'Date: {}'
            '</div>',
            obj.get_transaction_type_display(),
            obj.get_balance_type_display(),
            obj.user.username,
            obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
        )
    transaction_summary.short_description = 'Summary'
    
    def metadata_display(self, obj):
        """Display metadata in readable format"""
        if not obj.metadata:
            return '-'
        
        html = '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">'
        for key, value in obj.metadata.items():
            html += f'<strong>{key}:</strong> {value}<br>'
        html += '</div>'
        return format_html(html)
    metadata_display.short_description = 'Metadata'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'user', 'order', 'position'
    )
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        response = super().changelist_view(request, extra_context)
        
        try:
            # Calculate summary statistics
            qs = self.get_queryset(request)
            
            # Total deposits
            total_deposits = qs.filter(
                transaction_type=Transaction.TYPE_DEPOSIT,
                status=Transaction.STATUS_COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Total withdrawals
            total_withdrawals = qs.filter(
                transaction_type=Transaction.TYPE_WITHDRAWAL,
                status=Transaction.STATUS_COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Total profits
            total_profits = qs.filter(
                transaction_type=Transaction.TYPE_PROFIT,
                status=Transaction.STATUS_COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Total losses
            total_losses = qs.filter(
                transaction_type=Transaction.TYPE_LOSS,
                status=Transaction.STATUS_COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Net flow
            net_flow = total_deposits + total_withdrawals + total_profits + total_losses
            
            extra_context = extra_context or {}
            extra_context.update({
                'summary_stats': {
                    'total_deposits': total_deposits,
                    'total_withdrawals': total_withdrawals,
                    'total_profits': total_profits,
                    'total_losses': total_losses,
                    'net_flow': net_flow,
                    'total_transactions': qs.count(),
                }
            })
            
            if hasattr(response, 'context_data'):
                response.context_data.update(extra_context)
                
        except Exception as e:
            # Silently fail if there are any issues with statistics
            pass
            
        return response

class TransactionInline(admin.TabularInline):
    """Inline for showing transactions in User admin"""
    model = Transaction
    extra = 0
    max_num = 10
    readonly_fields = ['transaction_type', 'amount', 'balance_type', 'created_at']
    fields = ['transaction_type', 'amount', 'balance_type', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# If you want to add transaction summary to User admin
def add_transaction_summary_to_user_admin():
    """Add transaction summary to User admin"""
    from django.contrib.auth.models import User
    
    class CustomUserAdmin(UserAdmin):
        inlines = [TransactionInline]
        
        def changelist_view(self, request, extra_context=None):
            response = super().changelist_view(request, extra_context)
            
            try:
                # Add transaction statistics to user admin
                qs = Transaction.objects.all()
                user_stats = {}
                
                for user in User.objects.all():
                    user_transactions = qs.filter(user=user)
                    user_stats[user.id] = {
                        'total_transactions': user_transactions.count(),
                        'total_deposits': user_transactions.filter(
                            transaction_type=Transaction.TYPE_DEPOSIT
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                        'total_profits': user_transactions.filter(
                            transaction_type=Transaction.TYPE_PROFIT
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                    }
                
                extra_context = extra_context or {}
                extra_context['user_transaction_stats'] = user_stats
                
                if hasattr(response, 'context_data'):
                    response.context_data.update(extra_context)
                    
            except Exception:
                pass
                
            return response
    
    # Unregister and re-register User admin
    admin.site.unregister(User)
    admin.site.register(User, CustomUserAdmin)

# Uncomment to enable transaction inline in User admin
# add_transaction_summary_to_user_admin()

# Custom admin actions
def mark_as_completed(modeladmin, request, queryset):
    """Mark selected transactions as completed"""
    updated = queryset.update(status=Transaction.STATUS_COMPLETED)
    modeladmin.message_user(request, f'{updated} transactions marked as completed.')
mark_as_completed.short_description = "Mark selected transactions as completed"

def mark_as_failed(modeladmin, request, queryset):
    """Mark selected transactions as failed"""
    updated = queryset.update(status=Transaction.STATUS_FAILED)
    modeladmin.message_user(request, f'{updated} transactions marked as failed.')
mark_as_failed.short_description = "Mark selected transactions as failed"

def recalculate_balances(modeladmin, request, queryset):
    """Recalculate balance_before and balance_after for selected transactions"""
    for transaction in queryset:
        try:
            # This would need to be implemented based on your balance calculation logic
            # For now, just a placeholder
            pass
        except Exception as e:
            modeladmin.message_user(
                request, 
                f'Error recalculating transaction {transaction.id}: {str(e)}', 
                level='error'
            )
    modeladmin.message_user(request, 'Balance recalculation completed.')
recalculate_balances.short_description = "Recalculate balances for selected transactions"

# Add custom actions to TransactionAdmin
TransactionAdmin.actions = [mark_as_completed, mark_as_failed, recalculate_balances]    
    