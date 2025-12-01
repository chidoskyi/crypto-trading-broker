from django.utils import timezone
from django.contrib import admin
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib import messages
import logging
from .utils import send_deposit_notification, send_withdrawal_notification,send_withdrawal_notification_status
from .signals import send_email_referral_commission 
from django.db import transaction
from unfold.admin import ModelAdmin
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.models import User
# from user.forms import MessageForm
from django.conf import settings
from users.models import Referral
from decimal import Decimal
from .models import Wallet, InvestmentTransaction,InvestmentTransactions,Deposit,Withdrawal,WithdrawalCode, InvestmentPlan, Investment, TransactionHistory,Wallet, PaymentMethod
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.shortcuts import redirect, render
from django.http import JsonResponse
from .models import Deposit, Withdrawal, Wallet, PaymentMethod
from users.models import Account
import random
import string


logger = logging.getLogger(__name__)

@admin.register(TransactionHistory)
class TransactionHistoryAdmin(ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'status', 'created_at', 'get_payment_method', 'investment_plan')
    list_filter = ('transaction_type', 'user', 'status', 'investment_plan', 'payment_method')
    search_fields = ('user__username', 'transaction_type', 'amount', 'status')

    def get_payment_method(self, obj):
        return obj.payment_method.name if obj.payment_method else 'N/A'
    get_payment_method.short_description = 'Payment Method'

@admin.register(InvestmentTransaction)    
class InvestmentTransactionAdmin(ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'status', 'confirmed', 'payment_method', 'wallet_used', 'timestamp', 'transactionid')
    list_filter = ('status', 'transaction_type', 'payment_method', 'timestamp')
    search_fields = ('user__username', 'transactionid', 'wallet_used')
    actions = ['approve_transactions', 'reject_transactions']

    def get_queryset(self, request):
        # ✅ FIX 1: Completely exclude reinvestments from admin queue
        return super().get_queryset(request).filter(
            status='pending'
        ).exclude(
            transaction_type=InvestmentTransaction.REINVESTMENT
        )

    def approve_transactions(self, request, queryset):
        for transaction_obj in queryset.filter(status='pending'):
            try:
                # ✅ FIX 2: Double-check status before processing
                transaction_obj.refresh_from_db()
                if transaction_obj.status != 'pending':
                    self.message_user(
                        request,
                        f"Transaction {transaction_obj.transactionid} already processed",
                        messages.WARNING
                    )
                    continue

                # ✅ FIX 3: Explicitly block reinvestments with clear error
                if transaction_obj.transaction_type ==  InvestmentTransaction.REINVESTMENT:
                    self.message_user(
                        request,
                        f"ERROR: Reinvestment {transaction_obj.transactionid} should not be in admin queue",
                        messages.ERROR
                    )
                    continue

                with transaction.atomic():
                    account = Account.objects.select_for_update().get(user=transaction_obj.user)

                    if transaction_obj.transaction_type == InvestmentTransaction.DEPOSIT:
                        # Process the deposit first
                        account.process_deposit(transaction_obj.amount)

                        if transaction_obj.investment_plan:
                            investment = Investment.objects.filter(
                                user=transaction_obj.user,
                                plan=transaction_obj.investment_plan,
                                amount=transaction_obj.amount,
                                status='pending'
                            ).first()

                            if investment:
                                # ✅ FIX 4: Check if investment already processed
                                if investment.status == 'approved' or investment.is_running:
                                    raise ValueError("Investment already processed")

                                # Process investment
                                account.process_investment(transaction_obj.amount, transaction_obj.investment_plan)
                                
                                investment.status = 'approved'
                                investment.is_running = True  
                                now = timezone.now()
                                investment.start_date = now
                                if investment.plan.duration_unit == InvestmentPlan.DURATION_UNIT_HOURS:
                                    investment.end_date = now + timezone.timedelta(hours=investment.plan.duration)
                                else:
                                    investment.end_date = now + timezone.timedelta(days=investment.plan.duration)
                                
                                investment.save()
                                account.update_active_investments()

                                if not investment.is_reinvestment:
                                    self.award_referrer_on_investment(investment)

                                Notification.create_notification(
                                    user=transaction_obj.user,
                                    title="Investment Started",
                                    message=f"Your investment of ${transaction_obj.amount} in {transaction_obj.investment_plan.name} plan has started.",
                                    notification_type='investment',
                                    link='/user/investments/'
                                )

                        Notification.create_notification(
                            user=transaction_obj.user,
                            title="Deposit Approved",
                            message=f"Your deposit of ${transaction_obj.amount} has been approved and credited to your account.",
                            notification_type='transaction',
                            link='/user/transactions/'
                        )

                    elif transaction_obj.transaction_type == Transaction.WITHDRAWAL:
                        if account.available_balance >= transaction_obj.amount:
                            account.available_balance -= transaction_obj.amount
                            account.total_withdrawals += transaction_obj.amount
                            account.pending_withdrawals -= transaction_obj.amount
                            account.last_withdrawal = timezone.now()
                            account.save(update_fields=['available_balance', 'total_withdrawals', 'pending_withdrawals', 'last_withdrawal'])

                            send_withdrawal_notification_status(
                                user=transaction_obj.user,
                                amount=transaction_obj.amount,
                                username=transaction_obj.user.username,
                                status='confirmed'
                            )

                            Notification.create_notification(
                                user=transaction_obj.user,
                                title="Withdrawal Approved",
                                message=f"Your withdrawal request of ${transaction_obj.amount} has been approved.",
                                notification_type='transaction',
                                link='/user/transactions/'
                            )
                        else:
                            raise ValueError("Insufficient balance")

                    transaction_obj.status = 'confirmed'
                    transaction_obj.confirmed = True
                    transaction_obj.save()

                    if not self._create_transaction_records(transaction_obj, 'confirmed', True):
                        raise ValueError("Failed to create transaction records")

                    self.message_user(request, f"Successfully approved {transaction_obj.get_transaction_type_display().lower()} of ${transaction_obj.amount} for {transaction_obj.user.username}", messages.SUCCESS)

            except Account.DoesNotExist:
                self.message_user(request, f"Account for user {transaction_obj.user.username} does not exist.", messages.ERROR)
            except ValueError as e:
                self.message_user(request, str(e), messages.ERROR)
            except Exception as e:
                self.message_user(request, f"Error processing transaction: {str(e)}", messages.ERROR)

    approve_transactions.short_description = "Approve selected transactions"

    def reject_transactions(self, request, queryset):
        for transaction_obj in queryset.filter(status='pending'):
            try:
                with transaction.atomic():
                    if transaction_obj.transaction_type == Transaction.WITHDRAWAL:
                        account = Account.objects.select_for_update().get(user=transaction_obj.user)
                        account.pending_withdrawals -= transaction_obj.amount
                        account.save(update_fields=['pending_withdrawals'])

                    transaction_obj.status = 'rejected'
                    transaction_obj.confirmed = False
                    transaction_obj.save()

                    send_withdrawal_notification_status(
                        user=transaction_obj.user,
                        amount=transaction_obj.amount,
                        username=transaction_obj.user.username,
                        status='rejected'
                    )

                    Notification.create_notification(
                        user=transaction_obj.user,
                        title=f"{transaction_obj.get_transaction_type_display()} Rejected",
                        message=f"Your {transaction_obj.get_transaction_type_display().lower()} of ${transaction_obj.amount} has been rejected.",
                        notification_type='transaction',
                        link='/user/transactions/'
                    )

                    if not self._create_transaction_records(transaction_obj, 'rejected', False):
                        raise ValueError("Failed to create transaction records")

                    self.message_user(request, f"Successfully rejected {transaction_obj.get_transaction_type_display().lower()} of ${transaction_obj.amount} for {transaction_obj.user.username}", messages.SUCCESS)

            except Account.DoesNotExist:
                self.message_user(request, f"Account for user {transaction_obj.user.username} does not exist.", messages.ERROR)
            except Exception as e:
                self.message_user(request, f"Error rejecting transaction: {str(e)}", messages.ERROR)

    reject_transactions.short_description = "Reject selected transactions"

    def award_referrer_on_investment(self, investment):
        if investment.amount and investment.amount > 0:
            investor = investment.user

            try:
                investor_profile = investor.profile
                if investor_profile.referred_by:
                    referrer_profile = investor_profile.referred_by
                    referrer_user = referrer_profile.user

                    commission = investment.amount * Decimal('0.10')

                    referral, _ = Referral.objects.get_or_create(
                        referrer=referrer_profile,
                        referee=investor_profile,
                        defaults={'total_commission': Decimal('0.00')}
                    )

                    referral.total_commission += commission
                    referral.save()

                    try:
                        referrer_account = Account.objects.get(user=referrer_user)
                        referrer_account.available_balance += commission
                        referrer_account.total_earned += commission
                        referrer_account.save()

                        Notification.create_notification(
                            user=referrer_user,
                            title="Referral Commission Earned",
                            message=f"You've earned ${commission} commission from {investor.username}'s {'reinvestment' if investment.is_reinvestment else 'investment'} of ${investment.amount}!",
                            notification_type='referral',
                            link='/user/referrals/'
                        )

                        send_email_referral_commission(referrer_user, investor, commission, 'reinvestment' if investment.is_reinvestment else 'investment')

                    except Account.DoesNotExist:
                        logger.error(f"No account found for referrer: {referrer_user.username}")

            except Exception as e:
                logger.error(f"Error processing referral commission: {str(e)}")


@admin.register(Investment)
class InvestmentAdmin(ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'roi', 'start_date', 'end_date', 'status', 'completed', 'is_running', 'is_reinvestment')
    list_editable = ('is_running', 'completed', 'is_reinvestment')
    list_filter = ('status', 'completed', 'is_reinvestment', 'plan')
    search_fields = ('user__username', 'plan__name')
    readonly_fields = ('roi', 'start_date', 'end_date', 'status')
    date_hierarchy = 'start_date'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'plan')
    
    
@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(ModelAdmin):
    list_display = ('name', 'plan_types', 'interest_rate', 'duration', 'duration_unit', 'min_investment', 'max_investment')
    list_filter = ('plan_types', 'duration_unit')
    search_fields = ('name',)
    ordering = ('duration', 'interest_rate')

    fieldsets = (
        ('Plan Details', {
            'fields': ('name', 'plan_types', 'interest_rate', 'min_investment', 'max_investment')
        }),
        ('Duration', {
            'fields': ('duration', 'duration_unit')
        }),
    )

admin.site.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'min_amount', 'max_amount', 'icon', 'processing_time')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'icon', 'is_active')
        }),
        ('Limits', {
            'fields': ('min_amount', 'max_amount')
        }),
        ('Processing', {
            'fields': ('processing_time',)
        })
    )

@admin.register(InvestmentTransactions)
class TransactionAdmin(ModelAdmin):
    list_display = ('transactionid', 'user', 'transaction_type', 'amount', 'payment_method', 'status', 'timestamp')
    list_filter = ('transaction_type', 'status', 'payment_method', 'timestamp')
    search_fields = ('user__username', 'transactionid', 'wallet_used')
    ordering = ('-timestamp',)
    
    fieldsets = (
        (None, {
            'fields': ('user', 'transaction_type', 'amount', 'payment_method')
        }),
        ('Status', {
            'fields': ('status', 'confirmed')
        }),
        ('Details', {
            'fields': ('wallet_used', 'description', 'investment_plan')
        })
    )

class StatusFilter(admin.SimpleListFilter):
    """Custom filter for status"""
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('rejected', 'Rejected'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset

@admin.register(Deposit)
class DepositAdmin(ModelAdmin):
    list_display = [
        'deposit_id_short',
        'user_email',
        'amount_display',
        'selected_crypto',
        'status_badge',
        'has_deposited',
        'payment_proof_preview',
        'created_at',
    ]
    list_filter = [
        StatusFilter,
        'selected_crypto',
        'has_deposited',
    ]
    search_fields = [
        'deposit_id',
        'user__email',
        'user__username',
        'amount',
    ]
    readonly_fields = [
        'deposit_id',
        'payment_proof_preview_large',
        'wallet_address_display',
        'wallet_qr_code_display',
        'user_details',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Deposit Information', {
            'fields': (
                'deposit_id',
                'user',
                'wallet',
                'amount',
                'selected_crypto',
                'wallet_address_display',
                'wallet_qr_code_display',
            )
        }),
        ('Payment Details', {
            'fields': (
                'payment_method',
                'payment_proof',
                'payment_proof_preview_large',
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'has_deposited',
            )
        }),
        ('User Information', {
            'fields': ('user_details',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    actions = [
        'approve_deposits',
        'reject_deposits',
    ]
    list_per_page = 25
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'payment_method', 'wallet')

    def deposit_id_short(self, obj):
        """Display shortened deposit ID"""
        return f"{str(obj.deposit_id)[:8]}..."
    deposit_id_short.short_description = "Deposit ID"

    def user_email(self, obj):
        """Display user email with link to user admin"""
        if obj.user:
            try:
                url = reverse('admin:users_user_change', args=[obj.user.id])
            except:
                try:
                    url = reverse('admin:accounts_user_change', args=[obj.user.id])
                except:
                    try:
                        url = reverse('admin:user_user_change', args=[obj.user.id])
                    except:
                        try:
                            url = reverse('admin:auth_user_change', args=[obj.user.id])
                        except:
                            return obj.user.email
            
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return "No user"
    user_email.short_description = "User"
    user_email.admin_order_field = 'user__email'

    def amount_display(self, obj):
        """Display formatted amount"""
        try:
            amount = float(obj.amount)
            return format_html(
                '<strong>${:,.2f}</strong>',
                amount
            )
        except (ValueError, TypeError):
            return format_html(
                '<strong>${}</strong>',
                obj.amount
            )
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        """Display colored status badge"""
        colors = {
            'pending': '#FFA500',
            'confirmed': '#28A745',
            'rejected': '#DC3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6C757D'),
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'status'

    def payment_proof_preview(self, obj):
        """Display small payment proof preview"""
        if obj.payment_proof:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" /></a>',
                obj.payment_proof.url,
                obj.payment_proof.url
            )
        return "-"
    payment_proof_preview.short_description = "Proof"

    def payment_proof_preview_large(self, obj):
        """Display large payment proof preview in detail view"""
        if obj.payment_proof:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 400px; border-radius: 5px;" /></a>',
                obj.payment_proof.url,
                obj.payment_proof.url
            )
        return "No payment proof uploaded"
    payment_proof_preview_large.short_description = "Payment Proof"

    def wallet_address_display(self, obj):
        """Display the wallet address for selected crypto from Wallet model"""
        if obj.wallet and obj.selected_crypto:
            # Get the wallet address based on selected crypto
            crypto_field_map = {
                'BTC': 'btc_wallet',
                'ETH': 'eth_wallet',
                'USDT': 'usdt_wallet',
                'LTC': 'ltc_wallet',
                'BNB': 'bnb_wallet',
            }
            
            field_name = crypto_field_map.get(obj.selected_crypto)
            if field_name:
                address = getattr(obj.wallet, field_name, None)
                if address:
                    return format_html(
                        '<code style="background: #f4f4f4; padding: 5px; border-radius: 3px;">{}</code>',
                        address
                    )
        
        return format_html('<span style="color: red;">No wallet address configured for {}</span>', obj.selected_crypto)
    wallet_address_display.short_description = "Wallet Address"

    def wallet_qr_code_display(self, obj):
        """Display the QR code for selected crypto from Wallet model"""
        if obj.wallet and obj.selected_crypto:
            # Get the QR code based on selected crypto
            crypto_qr_map = {
                'BTC': 'btc_qr',
                'ETH': 'eth_qr',
                'USDT': 'usdt_qr',
                'LTC': 'ltc_qr',
                'BNB': 'bnb_qr',
            }
            
            qr_field_name = crypto_qr_map.get(obj.selected_crypto)
            if qr_field_name:
                qr_code = getattr(obj.wallet, qr_field_name, None)
                if qr_code:
                    return format_html(
                        '<div style="text-align: center;">'
                        '<a href="{}" target="_blank">'
                        '<img src="{}" style="max-width: 300px; border: 2px solid #ddd; border-radius: 5px; padding: 5px;" />'
                        '</a>'
                        '<p style="margin-top: 10px; color: green;">Scan to deposit {}</p>'
                        '</div>',
                        qr_code.url,
                        qr_code.url,
                        obj.selected_crypto
                    )
        
        return format_html(
            '<span style="color: red;">No QR code available for {}. Please configure wallet address in Wallet admin.</span>',
            obj.selected_crypto
        )
    wallet_qr_code_display.short_description = "Payment QR Code"

    def user_details(self, obj):
        """Display detailed user information"""
        user = obj.user
        return format_html(
            '<strong>Username:</strong> {}<br>'
            '<strong>Email:</strong> {}<br>'
            '<strong>Full Name:</strong> {} {}<br>'
            '<strong>Active:</strong> {}<br>'
            '<strong>Date Joined:</strong> {}',
            user.username,
            user.email,
            user.first_name,
            user.last_name,
            "Yes" if user.is_active else "No",
            user.date_joined.strftime('%Y-%m-%d %H:%M')
        )
    user_details.short_description = "User Details"

    def approve_deposits(self, request, queryset):
        """Bulk approve deposits and credit deposit_balance to existing accounts"""
        approved_count = 0
        
        for deposit in queryset.filter(status='pending'):
            try:
                with transaction.atomic():
                    deposit.status = 'confirmed'
                    deposit.has_deposited = True
                    deposit.save()
                    
                    try:
                        account = Account.objects.get(user=deposit.user)
                        
                        # Credit the deposit_balance
                        account.deposit_balance += deposit.amount
                        account.total_deposits += deposit.amount
                        account.save(update_fields=['deposit_balance', 'total_deposits'])
                        
                        # Create transaction record
                        InvestmentTransaction.objects.create(
                            user=deposit.user,
                            transaction_type=InvestmentTransaction.DEPOSIT,
                            amount=deposit.amount,
                            status='confirmed',
                            confirmed=True,
                            payment_method=deposit.payment_method,
                            description=f"Deposit approved - {deposit.selected_crypto}",
                            wallet_used=deposit.selected_crypto
                        )   
                        
                        approved_count += 1
                        logger.info(f"Deposit approved and credited: {deposit.deposit_id} - ${deposit.amount} to {deposit.user.username}")
                        
                    except Account.DoesNotExist:
                        logger.error(f"Account not found for user: {deposit.user.username}")
                        self.message_user(
                            request,
                            f"Error: No account found for user {deposit.user.username}. Please create an account first.",
                            messages.ERROR
                        )
                        continue
                    
            except Exception as e:
                logger.error(f"Error approving deposit {deposit.deposit_id}: {str(e)}")
                self.message_user(
                    request,
                    f"Error approving deposit {deposit.deposit_id}: {str(e)}",
                    messages.ERROR
                )
        
        if approved_count > 0:
            self.message_user(
                request,
                f"Successfully approved {approved_count} deposit(s) and credited deposit balances.",
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "No deposits were approved.",
                messages.WARNING
            )
    approve_deposits.short_description = "Approve selected deposits and credit balances"

    def reject_deposits(self, request, queryset):
        """Bulk reject deposits"""
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(
            request,
            f"{updated} deposit(s) rejected.",
            messages.WARNING
        )
    reject_deposits.short_description = "Reject selected deposits"


@admin.register(WithdrawalCode)
class WithdrawalCodeAdmin(admin.ModelAdmin):
    """Admin for managing withdrawal code requests"""
    list_display = [
        'code_id_short',
        'user_email',
        'code_display',
        'approval_status',
        'usage_status',
        'expiry_status',
        'action_buttons',
        'created_at',
    ]
    list_filter = [
        'is_approved',
        'is_used',
        'created_at',
    ]
    search_fields = [
        'code_id',
        'user__email',
        'user__username',
        'code',
    ]
    readonly_fields = [
        'code_id',
        'user',
        'code',
        'is_used',
        'used_at',
        'created_at',
        'code_details_display',
    ]
    fieldsets = (
        ('Code Information', {
            'fields': (
                'code_id',
                'user',
                'code_details_display',
            )
        }),
        ('Approval & Status', {
            'fields': (
                'is_approved',
                'is_used',
                'used_at',
                'expiry_date',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    actions = [
        'approve_codes',
        'reject_codes',
        'extend_expiry',
    ]
    list_per_page = 25
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')

    def code_id_short(self, obj):
        """Display shortened code ID"""
        return f"{str(obj.code_id)[:8]}..."
    code_id_short.short_description = "Request ID"

    def user_email(self, obj):
        """Display user email with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_email.short_description = "User"
    user_email.admin_order_field = 'user__email'

    def code_display(self, obj):
        """Display the 6-digit code prominently"""
        if obj.is_approved:
            return format_html(
                '<code style="background: #28a745; color: white; padding: 5px 10px; '
                'border-radius: 3px; font-size: 14px; font-weight: bold; letter-spacing: 2px;">{}</code>',
                obj.code
            )
        return format_html(
            '<code style="background: #6c757d; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-size: 14px; font-weight: bold; letter-spacing: 2px;">{}</code>',
            obj.code
        )
    code_display.short_description = "Code"

    def approval_status(self, obj):
        """Display approval status"""
        if obj.is_approved:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Approved</span>'
            )
        return format_html(
            '<span style="color: #ffc107; font-weight: bold;">⏳ Pending Approval</span>'
        )
    approval_status.short_description = "Approval"
    approval_status.admin_order_field = 'is_approved'

    def usage_status(self, obj):
        """Display usage status"""
        if obj.is_used:
            return format_html(
                '<span style="color: #6c757d;">✓ Used</span>'
            )
        return format_html(
            '<span style="color: #007bff;">○ Unused</span>'
        )
    usage_status.short_description = "Usage"
    usage_status.admin_order_field = 'is_used'

    def expiry_status(self, obj):
        """Display expiry status"""
        now = timezone.now()
        if now > obj.expiry_date:
            return format_html(
                '<span style="color: #dc3545;">⏱ Expired</span>'
            )
        
        time_left = obj.expiry_date - now
        hours_left = int(time_left.total_seconds() / 3600)
        
        if hours_left < 24:
            return format_html(
                '<span style="color: #ffc107;">⏱ {}h left</span>',
                hours_left
            )
        
        days_left = int(time_left.total_seconds() / 86400)
        return format_html(
            '<span style="color: #28a745;">⏱ {}d left</span>',
            days_left
        )
    expiry_status.short_description = "Expiry"

    def action_buttons(self, obj):
        """Display action buttons"""
        buttons = []
        
        if not obj.is_approved and not obj.is_used:
            # Show approve button
            approve_url = reverse('admin:approve_withdrawal_code', args=[obj.code_id])
            buttons.append(
                f'<a href="{approve_url}" style="background: #28a745; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none; font-size: 11px; margin-right: 5px;">✓ Approve</a>'
            )
            
            # Show reject button
            reject_url = reverse('admin:reject_withdrawal_code', args=[obj.code_id])
            buttons.append(
                f'<a href="{reject_url}" style="background: #dc3545; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none; font-size: 11px;">✗ Reject</a>'
            )
        
        return format_html(' '.join(buttons))
    action_buttons.short_description = "Actions"

    def code_details_display(self, obj):
        """Display detailed code information"""
        status_color = '#28a745' if obj.is_approved else '#ffc107'
        status_text = 'APPROVED' if obj.is_approved else 'PENDING APPROVAL'
        
        if obj.is_used:
            status_color = '#6c757d'
            status_text = 'USED'
        elif obj.expiry_date and timezone.now() > obj.expiry_date:
            status_color = '#dc3545'
            status_text = 'EXPIRED'
        
        return format_html(
            '<div style="background: #f8f9fa; padding: 20px; border-radius: 5px; text-align: center; border: 2px solid {};">'
            '<div style="color: {}; font-weight: bold; margin-bottom: 10px;">{}</div>'
            '<div style="background: white; padding: 20px; border-radius: 5px; margin: 10px 0;">'
            '<div style="font-size: 36px; font-weight: bold; letter-spacing: 10px; font-family: monospace; color: #333;">{}</div>'
            '</div>'
            '<p style="color: #6c757d; margin-top: 10px;"><strong>Expires:</strong> {}</p>'
            '<p style="color: #6c757d;"><strong>Created:</strong> {}</p>'
            '{}'
            '</div>',
            status_color,
            status_color,
            status_text,
            obj.code,
            obj.expiry_date.strftime('%Y-%m-%d %H:%M'),
            obj.created_at.strftime('%Y-%m-%d %H:%M'),
            f'<p style="color: #6c757d;"><strong>Used:</strong> {obj.used_at.strftime("%Y-%m-%d %H:%M")}</p>' if obj.used_at else ''
        )
    code_details_display.short_description = "Code Details"

    def get_urls(self):
        """Add custom URLs for approval actions"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/approve/',
                self.admin_site.admin_view(self.approve_code_view),
                name='approve_withdrawal_code',
            ),
            path(
                '<path:object_id>/reject/',
                self.admin_site.admin_view(self.reject_code_view),
                name='reject_withdrawal_code',
            ),
        ]
        return custom_urls + urls

    def approve_code_view(self, request, object_id):
        """Approve withdrawal code"""
        code = self.get_object(request, object_id)
        
        if code is None:
            self.message_user(request, "Withdrawal code not found.", messages.ERROR)
            return redirect('admin:yourapp_withdrawalcode_changelist')
        
        code.is_approved = True
        code.save(update_fields=['is_approved'])
        
        self.message_user(
            request,
            format_html(
                '✓ Withdrawal code <strong>{}</strong> approved for user <strong>{}</strong>',
                code.code,
                code.user.email
            ),
            messages.SUCCESS
        )
        
        return redirect('admin:yourapp_withdrawalcode_change', object_id)

    def reject_code_view(self, request, object_id):
        """Reject/delete withdrawal code"""
        code = self.get_object(request, object_id)
        
        if code is None:
            self.message_user(request, "Withdrawal code not found.", messages.ERROR)
            return redirect('admin:yourapp_withdrawalcode_changelist')
        
        user_email = code.user.email
        code.delete()
        
        self.message_user(
            request,
            format_html(
                '✗ Withdrawal code request rejected for user <strong>{}</strong>',
                user_email
            ),
            messages.WARNING
        )
        
        return redirect('admin:yourapp_withdrawalcode_changelist')

    def approve_codes(self, request, queryset):
        """Bulk approve codes"""
        updated = queryset.filter(is_approved=False, is_used=False).update(is_approved=True)
        self.message_user(
            request,
            f"✓ {updated} withdrawal code(s) approved.",
            messages.SUCCESS
        )
    approve_codes.short_description = "✓ Approve selected codes"

    def reject_codes(self, request, queryset):
        """Bulk reject/delete codes"""
        count = queryset.filter(is_approved=False, is_used=False).count()
        queryset.filter(is_approved=False, is_used=False).delete()
        self.message_user(
            request,
            f"✗ {count} withdrawal code(s) rejected.",
            messages.WARNING
        )
    reject_codes.short_description = "✗ Reject selected codes"

    def extend_expiry(self, request, queryset):
        """Extend expiry by 7 days"""
        for code in queryset.filter(is_used=False):
            code.expiry_date = code.expiry_date + timedelta(days=7)
            code.save(update_fields=['expiry_date'])
        
        self.message_user(
            request,
            f"⏱ Extended expiry for {queryset.count()} code(s) by 7 days.",
            messages.SUCCESS
        )
    extend_expiry.short_description = "⏱ Extend expiry by 7 days"


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    """Admin for managing withdrawals"""
    list_display = [
        'withdrawal_id_short',
        'user_email',
        'amount_display',
        'wallet_address_short',
        'code_status',
        'status_badge',
        'created_at',
    ]
    list_filter = [
        StatusFilter,
        'pending_withdrawals',
        'payment_method',
    ]
    search_fields = [
        'withdrawal_id',
        'wallet__user__email',
        'wallet__user__username',
        'wallet_address',
        'amount',
    ]
    readonly_fields = [
        'withdrawal_id',
        'withdrawal_code',
        'user_details',
        'wallet_info',
        'code_info_display',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Withdrawal Information', {
            'fields': (
                'withdrawal_id',
                'wallet',
                'amount',
                'wallet_address',
                'payment_method',
            )
        }),
        ('Verification', {
            'fields': (
                'withdrawal_code',
                'code_info_display',
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'pending_withdrawals',
            )
        }),
        ('User Information', {
            'fields': ('user_details', 'wallet_info'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    actions = [
        'approve_withdrawals',
        'reject_withdrawals',
    ]
    list_per_page = 25
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('wallet__user', 'payment_method', 'withdrawal_code')

    def withdrawal_id_short(self, obj):
        """Display shortened withdrawal ID"""
        return f"{str(obj.withdrawal_id)[:8]}..."
    withdrawal_id_short.short_description = "Withdrawal ID"

    def user_email(self, obj):
        """Display user email with link"""
        user = obj.wallet.user
        url = reverse('admin:auth_user_change', args=[user.id])
        return format_html('<a href="{}">{}</a>', url, user.email)
    user_email.short_description = "User"
    user_email.admin_order_field = 'wallet__user__email'

    def amount_display(self, obj):
        """Display formatted amount"""
        return format_html(
            '<strong>${:,.2f}</strong>',
            obj.amount
        )
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = 'amount'

    def wallet_address_short(self, obj):
        """Display shortened wallet address"""
        if obj.wallet_address:
            address = obj.wallet_address
            if len(address) > 20:
                return format_html(
                    '<code style="background: #f4f4f4; padding: 3px; border-radius: 3px;">{}...{}</code>',
                    address[:10],
                    address[-10:]
                )
            return format_html(
                '<code style="background: #f4f4f4; padding: 3px; border-radius: 3px;">{}</code>',
                address
            )
        return "-"
    wallet_address_short.short_description = "Wallet Address"

    def code_status(self, obj):
        """Display withdrawal code status"""
        if obj.withdrawal_code:
            return format_html(
                '<code style="background: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-weight: bold;">{}</code>',
                obj.withdrawal_code.code
            )
        return format_html(
            '<span style="color: #dc3545;">✗ No Code</span>'
        )
    code_status.short_description = "Code"

    def status_badge(self, obj):
        """Display colored status badge"""
        colors = {
            'pending': '#FFA500',
            'confirmed': '#28A745',
            'rejected': '#DC3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6C757D'),
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'status'

    def code_info_display(self, obj):
        """Display withdrawal code information"""
        if not obj.withdrawal_code:
            return format_html(
                '<div style="background: #f8d7da; padding: 15px; border-radius: 5px; color: #721c24;">'
                '<strong>⚠ No withdrawal code associated</strong>'
                '</div>'
            )
        
        code = obj.withdrawal_code
        return format_html(
            '<div style="background: #d4edda; padding: 15px; border-radius: 5px; border: 1px solid #c3e6cb;">'
            '<p><strong>Code:</strong> <code style="font-size: 18px; background: white; padding: 5px 10px; '
            'border-radius: 3px; letter-spacing: 3px;">{}</code></p>'
            '<p><strong>User:</strong> {}</p>'
            '<p><strong>Approved:</strong> {}</p>'
            '<p><strong>Used:</strong> {}</p>'
            '<p><strong>Expires:</strong> {}</p>'
            '</div>',
            code.code,
            code.user.email,
            '✓ Yes' if code.is_approved else '✗ No',
            '✓ Yes' if code.is_used else '○ No',
            code.expiry_date.strftime('%Y-%m-%d %H:%M')
        )
    code_info_display.short_description = "Withdrawal Code Info"

    def user_details(self, obj):
        """Display detailed user information"""
        user = obj.wallet.user
        return format_html(
            '<strong>Username:</strong> {}<br>'
            '<strong>Email:</strong> {}<br>'
            '<strong>Full Name:</strong> {} {}<br>'
            '<strong>Active:</strong> {}<br>'
            '<strong>Date Joined:</strong> {}',
            user.username,
            user.email,
            user.first_name,
            user.last_name,
            "Yes" if user.is_active else "No",
            user.date_joined.strftime('%Y-%m-%d %H:%M')
        )
    user_details.short_description = "User Details"

    def wallet_info(self, obj):
        """Display wallet information"""
        wallet = obj.wallet
        return format_html(
            '<strong>BTC:</strong> <code>{}</code><br>'
            '<strong>ETH:</strong> <code>{}</code><br>'
            '<strong>USDT:</strong> <code>{}</code><br>'
            '<strong>LTC:</strong> <code>{}</code><br>'
            '<strong>BNB:</strong> <code>{}</code>',
            wallet.btc_wallet or 'Not set',
            wallet.eth_wallet or 'Not set',
            wallet.usdt_wallet or 'Not set',
            wallet.ltc_wallet or 'Not set',
            wallet.bnb_wallet or 'Not set',
        )
    wallet_info.short_description = "Wallet Addresses"

    def approve_withdrawals(self, request, queryset):
        """Bulk approve withdrawals"""
        valid_withdrawals = queryset.filter(
            status='pending',
            withdrawal_code__is_approved=True,
            withdrawal_code__is_used=False
        )
        
        updated = 0
        for withdrawal in valid_withdrawals:
            withdrawal.status = 'confirmed'
            withdrawal.pending_withdrawals = False
            withdrawal.withdrawal_code.mark_as_used()
            withdrawal.save(update_fields=['status', 'pending_withdrawals'])
            updated += 1
        
        invalid_count = queryset.count() - updated
        
        if updated > 0:
            self.message_user(
                request,
                f"✓ {updated} withdrawal(s) approved successfully!",
                messages.SUCCESS
            )
        
        if invalid_count > 0:
            self.message_user(
                request,
                f"⚠ {invalid_count} withdrawal(s) skipped (invalid or already used codes).",
                messages.WARNING
            )
    approve_withdrawals.short_description = "✓ Approve withdrawals"

    def reject_withdrawals(self, request, queryset):
        """Bulk reject withdrawals"""
        updated = queryset.filter(status='pending').update(
            status='rejected',
            pending_withdrawals=False
        )
        self.message_user(
            request,
            f"✗ {updated} withdrawal(s) rejected.",
            messages.WARNING
        )
    reject_withdrawals.short_description = "✗ Reject withdrawals"

@admin.register(Wallet)
class WalletAdmin(ModelAdmin):
    list_display = [
        'admin_wallet_label',
        'btc_wallet_short',
        'eth_wallet_short',
        'usdt_wallet_short',
        'ltc_wallet_short',
        'bnb_wallet_short',
        'updated_at',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'btc_qr_preview',
        'eth_qr_preview',
        'usdt_qr_preview',
        'ltc_qr_preview',
        'bnb_qr_preview',
    ]
    fieldsets = (
        ('Bitcoin (BTC)', {
            'fields': ('btc_wallet', 'btc_qr_preview')
        }),
        ('Ethereum (ETH)', {
            'fields': ('eth_wallet', 'eth_qr_preview')
        }),
        ('USDT (Tether)', {
            'fields': ('usdt_wallet', 'usdt_qr_preview')
        }),
        ('Litecoin (LTC)', {
            'fields': ('ltc_wallet', 'ltc_qr_preview')
        }),
        ('Binance Coin (BNB)', {
            'fields': ('bnb_wallet', 'bnb_qr_preview')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    list_per_page = 25

    def has_add_permission(self, request):
        """Only allow one wallet instance"""
        return not Wallet.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the wallet"""
        return False

    def admin_wallet_label(self, obj):
        return "Admin Wallet Addresses"
    admin_wallet_label.short_description = "Wallet"

    # Wallet address display methods
    def btc_wallet_short(self, obj):
        return self._format_wallet(obj.btc_wallet, obj.btc_qr)
    btc_wallet_short.short_description = "BTC Wallet"

    def eth_wallet_short(self, obj):
        return self._format_wallet(obj.eth_wallet, obj.eth_qr)
    eth_wallet_short.short_description = "ETH Wallet"

    def usdt_wallet_short(self, obj):
        return self._format_wallet(obj.usdt_wallet, obj.usdt_qr)
    usdt_wallet_short.short_description = "USDT Wallet"

    def ltc_wallet_short(self, obj):
        return self._format_wallet(obj.ltc_wallet, obj.ltc_qr)
    ltc_wallet_short.short_description = "LTC Wallet"

    def bnb_wallet_short(self, obj):
        return self._format_wallet(obj.bnb_wallet, obj.bnb_qr)
    bnb_wallet_short.short_description = "BNB Wallet"

    def _format_wallet(self, address, qr_code):
        """Format wallet address with QR indicator"""
        if address:
            qr_icon = '✓' if qr_code else '✗'
            qr_color = 'green' if qr_code else 'red'
            if len(address) > 20:
                return format_html(
                    '<code>{}...{}</code> <span style="color: {};">[QR: {}]</span>',
                    address[:8],
                    address[-8:],
                    qr_color,
                    qr_icon
                )
            return format_html(
                '<code>{}</code> <span style="color: {};">[QR: {}]</span>',
                address,
                qr_color,
                qr_icon
            )
        return '-'

    # QR Code preview methods
    def btc_qr_preview(self, obj):
        return self._qr_preview(obj.btc_qr, 'Bitcoin')
    btc_qr_preview.short_description = "BTC QR Code"

    def eth_qr_preview(self, obj):
        return self._qr_preview(obj.eth_qr, 'Ethereum')
    eth_qr_preview.short_description = "ETH QR Code"

    def usdt_qr_preview(self, obj):
        return self._qr_preview(obj.usdt_qr, 'USDT')
    usdt_qr_preview.short_description = "USDT QR Code"

    def ltc_qr_preview(self, obj):
        return self._qr_preview(obj.ltc_qr, 'Litecoin')
    ltc_qr_preview.short_description = "LTC QR Code"

    def bnb_qr_preview(self, obj):
        return self._qr_preview(obj.bnb_qr, 'Binance Coin')
    bnb_qr_preview.short_description = "BNB QR Code"

    def _qr_preview(self, qr_field, crypto_name):
        """Display QR code preview"""
        if qr_field:
            return format_html(
                '<div style="text-align: center;">'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 200px; border: 2px solid #ddd; border-radius: 5px; padding: 5px;" />'
                '</a>'
                '<p style="margin-top: 5px; color: green;">✓ QR Code Available</p>'
                '</div>',
                qr_field.url,
                qr_field.url
            )
        return format_html(
            '<p style="color: #999;">No QR code - Add {} wallet address to auto-generate</p>',
            crypto_name
        )
