import requests
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Investment
from django.contrib import messages
from users.models import Profile, Referral, Account
from django.contrib.auth.models import User
from .models import (
    Investment, InvestmentPlan, 
    InvestmentTransaction, TransactionHistory, Wallet, InvestmentTransactions, PaymentMethod
)
from rest_framework import serializers
from decimal import Decimal, InvalidOperation
from django.utils.translation import gettext_lazy as _
from django.db import transaction as db_transaction  # Import with an alias to avoid conflict
from django.db.models import Sum
from datetime import datetime
from .utils import send_deposit_notification, send_withdrawal_notification, send_reinvest_notification, send_withdrawal_notification_status
import json
from django.views.decorators.http import require_http_methods
import logging
from .services import ROIService  
from django.db.models import Sum, F
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from .utils import handle_investment 
from .models import Deposit, Wallet
from .models import Withdrawal, WithdrawalCode
from .serializers import (
    DepositSerializer,
    DepositCreateSerializer,
    DepositListSerializer,
    DepositStatusUpdateSerializer,
    WalletSerializer,
    WithdrawalSerializer,
    WithdrawalCreateSerializer,
    WithdrawalCodeRequestSerializer,
    WithdrawalCodeSerializer,
    PaymentMethodSerializer,
    InvestmentSerializer,
    InvestmentPlanSerializer,
    CreateInvestmentSerializer,
    AccountSerializer,
    InvestmentTransactionSerializer
)

import logging

# Set up logging
logger = logging.getLogger(__name__)    


class DepositViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing deposits
    
    list: Get all deposits for the authenticated user
    create: Create a new deposit
    retrieve: Get a specific deposit detail
    update/partial_update: Not allowed for users (admin only for status updates)
    destroy: Delete a deposit (only if pending)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['status', 'selected_crypto', 'has_deposited']
    ordering_fields = ['amount']
    search_fields = ['deposit_id', 'amount']
    
    def get_queryset(self):
        """Return deposits for the current user, or all if admin"""
        user = self.request.user
        if user.is_staff:
            return Deposit.objects.all().select_related('wallet__user', 'payment_method')
        return Deposit.objects.filter(user=user).select_related('wallet', 'payment_method')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return DepositCreateSerializer
        elif self.action == 'list':
            return DepositListSerializer
        elif self.action == 'update_status':
            return DepositStatusUpdateSerializer
        return DepositSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new deposit"""
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deposit = serializer.save()
        
        # Return full deposit details
        response_serializer = DepositSerializer(deposit, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        """Allow deletion only for pending deposits"""
        deposit = self.get_object()
        
        if deposit.status != 'pending':
            return Response(
                {"error": "Only pending deposits can be deleted"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deposit.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """
        Admin endpoint to update deposit status
        PATCH /api/deposits/{id}/update_status/
        """
        deposit = self.get_object()
        serializer = DepositStatusUpdateSerializer(deposit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return full deposit details
        response_serializer = DepositSerializer(deposit, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def regenerate_qr(self, request, pk=None):
        """
        Regenerate QR code for a deposit
        POST /api/deposits/{id}/regenerate_qr/
        """
        deposit = self.get_object()
        
        if deposit.generate_qr_code():
            deposit.save(update_fields=['qr_code'])
            serializer = DepositSerializer(deposit, context={'request': request})
            return Response(serializer.data)
        
        return Response(
            {"error": "Could not generate QR code. Wallet address not configured."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def my_deposits(self, request):
        """
        Get current user's deposits with filtering
        GET /api/deposits/my_deposits/
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = DepositListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DepositListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get deposit statistics for current user
        GET /api/deposits/statistics/
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_deposits': queryset.count(),
            'pending': queryset.filter(status='pending').count(),
            'confirmed': queryset.filter(status='confirmed').count(),
            'rejected': queryset.filter(status='rejected').count(),
            'total_amount': sum(d.amount for d in queryset.filter(status='confirmed')),
            'by_crypto': {}
        }
        
        # Statistics by cryptocurrency
        for crypto, _ in Deposit.CRYPTO_CHOICES:
            crypto_deposits = queryset.filter(selected_crypto=crypto, status='confirmed')
            stats['by_crypto'][crypto] = {
                'count': crypto_deposits.count(),
                'total': sum(d.amount for d in crypto_deposits)
            }
        
        return Response(stats)

class WithdrawalCodeViewSet(viewsets.GenericViewSet):
    """ViewSet for withdrawal codes"""
    permission_classes = [IsAuthenticated]
    serializer_class = WithdrawalCodeSerializer
    
    def get_queryset(self):
        """Return codes for current user"""
        return WithdrawalCode.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def request_code(self, request):    
        """
        Request a new withdrawal code
        POST /api/withdrawal-codes/request_code/
        """
        serializer = WithdrawalCodeRequestSerializer(data={}, context={'request': request})
        serializer.is_valid(raise_exception=True)
    
        try:
            code = serializer.save()
            response_serializer = WithdrawalCodeSerializer(code)
            return Response({
                'message': 'Withdrawal code requested successfully. Please wait for admin approval.',
                'code': response_serializer.data
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def my_codes(self, request):
        """
        Get all withdrawal codes for current user
        GET /api/withdrawal-codes/my_codes/
        """
        codes = self.get_queryset()
        serializer = WithdrawalCodeSerializer(codes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active_code(self, request):
        """
        Get active (valid) withdrawal code for current user
        GET /api/withdrawal-codes/active_code/
        """
        code = WithdrawalCode.objects.filter(
            user=request.user,
            is_approved=True,
            is_used=False,
            expiry_date__gt=timezone.now()
        ).first()
        
        if code:
            serializer = WithdrawalCodeSerializer(code)
            return Response(serializer.data)
        
        return Response(
            {'message': 'No active withdrawal code found. Please request one.'},
            status=status.HTTP_404_NOT_FOUND
        )

class WithdrawalViewSet(viewsets.ModelViewSet):
    """ViewSet for withdrawals"""
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        """Return withdrawals for current user"""
        return Withdrawal.objects.filter(wallet__user=self.request.user).select_related(
            'wallet__user', 'payment_method', 'withdrawal_code'
        )

    def get_serializer_class(self):
        """Return appropriate serializer"""
        if self.action == 'create':
            return WithdrawalCreateSerializer
        return WithdrawalSerializer

    def create(self, request, *args, **kwargs):
        """Create a new withdrawal"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = serializer.save()
        
        response_serializer = WithdrawalSerializer(withdrawal)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing admin wallet information
    
    list: Get all admin wallets (should only be one)
    retrieve: Get specific wallet details
    """
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer
    
    def get_queryset(self):
        """Return the admin wallet"""
        return Wallet.objects.all()
    
    @action(detail=False, methods=['get'])
    def admin_wallet(self, request):
        """
        Get admin wallet addresses
        GET /api/wallets/admin_wallet/
        """
        try:
            wallet = Wallet.get_wallet()
            serializer = WalletSerializer(wallet)
            return Response(serializer.data)
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Admin wallet not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='by-currency/(?P<currency>[^/.]+)')
    def by_currency(self, request, currency=None):
        """
        Get specific currency wallet address
        GET /api/wallets/by-currency/btc/
        GET /api/wallets/by-currency/Bitcoin/
        """
        wallet = Wallet.get_wallet()
        
        # Normalize currency input to uppercase
        currency_normalized = currency.upper() if currency else ''
        
        # Extended mapping that handles both codes and full names
        currency_map = {
            # Full names
            'BITCOIN': ('btc_wallet', 'btc_qr', 'BTC'),
            'ETHEREUM': ('eth_wallet', 'eth_qr', 'ETH'),
            'TETHER': ('usdt_wallet', 'usdt_qr', 'USDT'),
            'LITECOIN': ('ltc_wallet', 'ltc_qr', 'LTC'),
            'BINANCE COIN': ('bnb_wallet', 'bnb_qr', 'BNB'),
            # Short codes
            'BTC': ('btc_wallet', 'btc_qr', 'BTC'),
            'ETH': ('eth_wallet', 'eth_qr', 'ETH'),
            'USDT': ('usdt_wallet', 'usdt_qr', 'USDT'),
            'LTC': ('ltc_wallet', 'ltc_qr', 'LTC'),
            'BNB': ('bnb_wallet', 'bnb_qr', 'BNB'),
        }
        
        if currency_normalized not in currency_map:
            return Response(
                {"error": f"Currency '{currency}' not supported. Valid options: BTC, ETH, USDT, LTC, BNB"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        wallet_field, qr_field, display_code = currency_map[currency_normalized]
        wallet_address = getattr(wallet, wallet_field, None)
        qr_code = getattr(wallet, qr_field, None)
        
        if not wallet_address:
            return Response(
                {"error": f"{display_code} wallet address not configured"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'currency': display_code,
            'wallet_address': wallet_address,
            'qr_code': request.build_absolute_uri(qr_code.url) if qr_code else None
        })

class PaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet for payment methods"""
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    
    def get_queryset(self):
        """Return payment methods for current user, excluding deposit and investment balance"""
        return PaymentMethod.objects.filter(
            is_active=True
        ).exclude(
            code__in=['DEPOSIT', 'REINVEST']
        )

class InvestmentPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving investment plans
    """
    queryset = InvestmentPlan.objects.all()
    serializer_class = InvestmentPlanSerializer
    permission_classes = [IsAuthenticated]
    


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing investment account details
    """
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get current account balance details"""
        try:
            account = Account.objects.get(user=request.user)
            serializer = self.get_serializer(account)
            return Response(serializer.data)
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class InvestmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing investments
    """
    serializer_class = InvestmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Investment.objects.filter(
            user=self.request.user
        ).select_related('plan').order_by('-start_date')
    
    @action(detail=False, methods=['post'])
    def create_investment(self, request):
        """
        Create a new investment (deposit or reinvestment)
        - Regular investments: Deduct from deposit_balance, mature to investment_balance
        - Reinvestments: Deduct from investment_balance, mature to investment_balance
        """
        user = self.request.user
        serializer = CreateInvestmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        amount = validated_data['amount']
        plan_id = validated_data['plan_id']
        investment_type = validated_data['investment_type']
        payment_method_id = validated_data.get('payment_method_id')
        
        is_reinvestment = investment_type == 'reinvest'
        
        try:
            # Get account with lock
            account = Account.objects.select_for_update().get(
                user=request.user
            )
            
            # Check account status
            if account.status != Account.STATUS_ACTIVE:
                return Response(
                    {'error': 'Your account is not active. You cannot make investments.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get investment plan
            try:
                plan = InvestmentPlan.objects.get(id=plan_id)
            except InvestmentPlan.DoesNotExist:
                return Response(
                    {'error': 'Investment plan not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Determine payment source and validate balance
            use_deposit_balance = False
            
            if is_reinvestment:
                # Reinvestments MUST use investment_balance
                if amount > account.investment_balance:
                    return Response(
                        {
                            'error': f'Insufficient investment balance for reinvestment. Available: ${account.investment_balance}, Requested: ${amount}'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                use_deposit_balance = False
                
            else:
                # Regular investments: prioritize deposit_balance
                if account.deposit_balance >= amount:
                    use_deposit_balance = True
                elif amount > account.deposit_balance:
                    return Response(
                        {
                            'error': f'Insufficient deposit balance. Available: ${account.deposit_balance}, Requested: ${amount}. Please make a deposit first.'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Process the investment
            success, message, investment_obj = self._process_investment(
                user=request.user,
                account=account,
                amount=amount,
                plan=plan,
                is_reinvestment=is_reinvestment,
                use_deposit_balance=use_deposit_balance,
                payment_method_id=payment_method_id
            )
            
            if success:
                investment_serializer = InvestmentSerializer(investment_obj)
                return Response(
                    {
                        'success': True,
                        'message': message,
                        'investment': investment_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Account.DoesNotExist:
            return Response(
                {'error': 'Investment account not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Investment creation error: {str(e)}")
            logger.exception(e)
            return Response(
                {'error': 'An error occurred while processing your investment.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_investment(self, user, account, amount, plan, 
                        is_reinvestment, use_deposit_balance, 
                        payment_method_id=None):
        """
        Internal method to process investment creation
        The Investment model now auto-calculates end_date in save()
        
        Balance Flow:
        - Regular Investment: deposit_balance -> invested_balance -> (maturity) -> investment_balance
        - Reinvestment: investment_balance -> invested_balance -> (maturity) -> investment_balance
        - active_investments: Increased when investment starts, decreased when it completes
        
        Returns:
            Tuple (success: bool, message: str, investment: Investment|None)
        """
        if not user:
            logger.error("USER IS NONE in _process_investment")
            return False, "User authentication required.", None
    
        if not hasattr(user, 'id') or not user.id:
            logger.error(f"USER HAS NO VALID ID: {user}")
            return False, "Invalid user account.", None
        
        if not plan:
            logger.error("PLAN IS NONE in _process_investment")
            return False, "Investment plan is required", None
        
        if not amount or amount <= 0:
            logger.error(f"INVALID AMOUNT: {amount}")
            return False, "Investment amount must be greater than zero", None
        
        logger.info(f"_process_investment: User={user.id}, Plan={plan.id}, Amount={amount}")
        
        try:
            with db_transaction.atomic():
                now = timezone.now()
                
                # Validate required fields
                if not plan:
                    return False, "Investment plan is required", None
                
                if not amount or amount <= 0:
                    return False, "Investment amount must be greater than zero", None
                
                # Check for duplicate investments (within last 10 seconds)
                recent_duplicate = Investment.objects.filter(
                    user=user,
                    plan=plan,
                    amount=amount,
                    start_date__gte=now - timezone.timedelta(seconds=10)
                ).exists()
                
                if recent_duplicate:
                    logger.warning(f"DUPLICATE DETECTED: User={user.username}, Amount={amount}, Plan={plan.name}")
                    return False, "Duplicate investment detected. Please wait before trying again.", None
                
                # ✅ Create Investment record - end_date will be auto-calculated by model
                try:
                    investment = Investment.objects.create(
                        user=user,
                        plan=plan,
                        amount=Decimal(str(amount)),
                        status='approved' if is_reinvestment or use_deposit_balance else 'pending',
                        is_reinvestment=is_reinvestment,
                        is_running=is_reinvestment or use_deposit_balance,
                        start_date=now,
                        # end_date will be auto-calculated in save()
                        roi=Decimal('0.00')  # Will be calculated next
                    )
                    
                    logger.info(f"Investment created: ID={investment.id}, end_date={investment.end_date}")
                    
                except serializers.ValidationError as e:
                    logger.error(f"Validation error creating investment: {str(ve)}")
                    return False, f"Validation error: {str(ve)}", None
                except Exception as create_error:
                    logger.error(f"Error creating investment record: {str(create_error)}")
                    logger.exception(create_error)
                    return False, f"Failed to create investment: {str(create_error)}", None
                
                # Calculate ROI
                try:
                    roi = investment.calculate_return()
                    if roi is None or roi < 0:
                        logger.error(f"Invalid ROI calculated: {roi}")
                        investment.delete()
                        return False, "Failed to calculate investment returns", None
                    
                    investment.roi = roi
                    investment.save(update_fields=['roi'])
                    logger.info(f"ROI calculated and saved: ${roi}")
                    
                except Exception as roi_error:
                    logger.error(f"Error calculating ROI: {str(roi_error)}")
                    investment.delete()
                    return False, "Failed to calculate investment returns", None
                
                # Get payment method
                try:
                    if is_reinvestment:
                        payment_method, _ = PaymentMethod.objects.get_or_create(
                            code='REINVEST',
                            defaults={
                                'name': 'Investment Balance',
                                'is_active': True,
                                'min_amount': Decimal('0.00'),
                                'max_amount': Decimal('999999.99'),
                                'processing_time': 'Instant'
                            }
                        )
                    elif use_deposit_balance:
                        payment_method, _ = PaymentMethod.objects.get_or_create(
                            code='DEPOSIT',
                            defaults={
                                'name': 'Deposit Balance',
                                'is_active': True,
                                'min_amount': Decimal('0.00'),
                                'max_amount': Decimal('999999.99'),
                                'processing_time': 'Instant'
                            }
                        )
                    else:
                        if not payment_method_id:
                            investment.delete()
                            return False, "Payment method is required", None
                        
                        payment_method = PaymentMethod.objects.get(id=payment_method_id)
                        
                except PaymentMethod.DoesNotExist:
                    logger.error(f"Payment method not found: {payment_method_id}")
                    investment.delete()
                    return False, "Invalid payment method selected", None
                except Exception as pm_error:
                    logger.error(f"Error getting payment method: {str(pm_error)}")
                    investment.delete()
                    return False, "Error processing payment method", None
                
                # Process based on investment type
                try:
                    if is_reinvestment:
                        # ✅ Deduct from investment_balance (source for reinvestments)
                        account.investment_balance -= amount
                        account.invested_balance += amount  # Track as actively invested
                        account.active_investments += amount  # ✅ ADD to active investments when it starts
                        account.total_invested += amount
                        account.last_investment = now
                        account.save(update_fields=[
                            'investment_balance', 'invested_balance', 'active_investments', 
                            'total_invested', 'last_investment'
                        ])
                        
                        # Create confirmed transaction
                        transaction_obj = InvestmentTransaction.objects.create(
                            user=user,
                            transaction_type=InvestmentTransaction.REINVESTMENT,
                            amount=amount,
                            status='confirmed',
                            confirmed=True,
                            payment_method=payment_method,
                            investment_plan=plan,
                            wallet_used=f"Investment Balance",
                            description=f"Reinvestment in {plan.name} plan - Expected ROI: ${roi}"
                        )
                        
                        # Send notification
                        # Notification.create_notification(
                        #     user=user,
                        #     title="Reinvestment Successful",
                        #     message=f"Your reinvestment of ${amount} in {plan.name} has been processed successfully. Expected ROI: ${roi}",
                        #     notification_type='investment',
                        #     link='/user/investments/'
                        # )
                        
                        message = f"Reinvestment of ${amount} processed successfully! Expected ROI: ${roi}"
                        
                    elif use_deposit_balance:
                        # ✅ Deduct from deposit_balance (source for new investments)
                        account.deposit_balance -= amount
                        account.invested_balance += amount  # Track as actively invested
                        account.active_investments += amount  # ✅ ADD to active investments when it starts
                        account.total_invested += amount
                        account.last_investment = now
                        account.save(update_fields=[
                            'deposit_balance', 'invested_balance', 'active_investments',
                            'total_invested', 'last_investment'
                        ])
                        
                        # Create confirmed transaction
                        transaction_obj = InvestmentTransaction.objects.create(
                            user=user,
                            transaction_type=InvestmentTransaction.INVESTMENT,
                            amount=amount,
                            status='confirmed',
                            confirmed=True,
                            payment_method=payment_method,
                            investment_plan=plan,
                            wallet_used="Deposit Balance",
                            description=f"Investment from deposit balance in {plan.name} - Expected ROI: ${roi}"
                        )
                        
                        message = f"Investment of ${amount} started successfully using deposit balance! Expected ROI: ${roi}"
                        
                    else:
                        # External payment method (PENDING APPROVAL)
                        transaction_obj = InvestmentTransaction.objects.create(
                            user=user,
                            transaction_type=InvestmentTransaction.DEPOSIT,
                            amount=amount,
                            status='pending',
                            confirmed=False,
                            payment_method=payment_method,
                            investment_plan=plan,
                            wallet_used=payment_method.name,
                            description=f"Deposit for investment in {plan.name} - Expected ROI: ${roi}"
                        )
                        
                        message = f"Investment of ${amount} submitted for approval. Expected ROI: ${roi}"
                    
                except Exception as process_error:
                    logger.error(f"Error processing investment: {str(process_error)}")
                    logger.exception(process_error)
                    # Rollback will happen automatically due to atomic block
                    return False, "Error processing investment. Please try again.", None
                
                logger.info(
                    f"INVESTMENT SUCCESS: User={user.username}, Amount=${amount}, "
                    f"Type={'REINVEST' if is_reinvestment else 'DEPOSIT' if use_deposit_balance else 'EXTERNAL'}, "
                    f"Investment={investment.id}, EndDate={investment.end_date}, "
                    f"ActiveInvestments=${account.active_investments}"
                )
                
                return True, message, investment
                
        except Exception as e:
            logger.error(f"Error in _process_investment: {str(e)}")
            logger.exception(e)
            return False, "An unexpected error occurred. Please try again.", None
    
    def validate_investment_plan(plan):
        """
        Validate that an investment plan has all required fields
        
        Returns:
            Tuple (valid: bool, error_message: str)
        """
        if not plan:
            return False, "Plan is None"
        
        if not hasattr(plan, 'duration') or plan.duration is None:
            return False, "Plan missing duration field"
        
        if not hasattr(plan, 'duration_unit') or not plan.duration_unit:
            return False, "Plan missing duration_unit field"
        
        if not hasattr(plan, 'interest_rate') or plan.interest_rate is None:
            return False, "Plan missing interest_rate field"
        
        try:
            duration = int(plan.duration)
            if duration <= 0:
                return False, f"Invalid plan duration: {duration}"
        except (ValueError, TypeError):
            return False, f"Plan duration is not a valid number: {plan.duration}"
        
        valid_units = [InvestmentPlan.DURATION_UNIT_HOURS, InvestmentPlan.DURATION_UNIT_DAYS]
        if plan.duration_unit not in valid_units:
            return False, f"Invalid duration_unit: {plan.duration_unit}"
        
        return True, "Plan is valid"
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active investments"""
        active_investments = self.get_queryset().filter(
            completed=False,
            status='approved'
        )
        serializer = self.get_serializer(active_investments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def completed(self, request):
        """Get all completed investments"""
        completed_investments = self.get_queryset().filter(completed=True)
        serializer = self.get_serializer(completed_investments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get investment statistics"""
        from .services import ROIService
        
        stats = ROIService.get_investment_statistics(request.user)
        return Response(stats) 
    
    
class InvestmentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing investment transactions
    """
    serializer_class = InvestmentTransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return InvestmentTransaction.objects.filter(
            user=self.request.user
        ).select_related('payment_method', 'investment_plan').order_by('-timestamp')
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending transactions"""
        pending_transactions = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(pending_transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def confirmed(self, request):
        """Get confirmed transactions"""
        confirmed_transactions = self.get_queryset().filter(status='confirmed')
        serializer = self.get_serializer(confirmed_transactions, many=True)
        return Response(serializer.data)


# @login_required
# def make_investment(request):
#     """Handle deposit and investment creation process."""
#     if not request.user.is_authenticated:
#         return redirect('login')

#     try:
#         # Get admin wallet for deposit addresses
#         admin_user = User.objects.get(username='admin')
#         admin_wallet = Wallet.objects.get(user=admin_user)
#     except (User.DoesNotExist, Wallet.DoesNotExist):
#         logger.error("Admin wallet configuration not found")
#         messages.error(request, "System configuration error. Please contact support.")
#         return redirect('dashboard')

#     account = get_object_or_404(Account, user=request.user)
#     plans = InvestmentPlan.objects.all().order_by('id')
#     payment_methods = PaymentMethod.objects.filter(is_active=True)

#     if request.method == 'POST':
#         if account.status != Account.STATUS_ACTIVE:
#             messages.error(request, "Your account is not active. You cannot make a deposit.")
#             return redirect('deposit')

#         # Get and validate form data
#         form_data = {
#             'amount': request.POST.get('amount', '').strip(),
#             'investment_type': request.POST.get('investment_type'),
#             'payment_method_id': request.POST.get('payment_method'),
#             'plan_id': request.POST.get('plan_id')
#         }

#         # Use the utility function to handle investment
#         success, message = handle_investment(request, account, form_data)
#         if success:
#             messages.success(request, message)
#         else:
#             messages.error(request, message)
#         return redirect('dashboard')

#     context = {
#         'account': account,
#         'plans': plans,
#         'payment_methods': payment_methods,
#         'admin_wallet': admin_wallet,
#     }
#     return render(request, 'user-admin/deposit.html', context)



# @login_required
# def withdrawal_view(request):
#     print("\n=== Starting Withdrawal Process ===")
#     user = request.user
#     print(f"User: {user.username}")
    
#     try:
#         account = Account.objects.get(user=request.user)
#         print(f"Account found: {account}")
#     except Account.DoesNotExist:
#         print("Error: Account not found")
#         return JsonResponse({
#             'success': False,
#             'message': "Account not found. Please contact support."
#         })

#     # Get available balance
#     available_balance = account.available_balance
#     print(f"Available balance: ${available_balance}")

#     # Calculate pending withdrawals
#     pending_withdrawals = Transaction.objects.filter(
#         user=user, 
#         transaction_type=Transaction.WITHDRAWAL,
#         status='pending'
#     ).aggregate(total_pending=Sum('amount'))['total_pending'] or Decimal('0.00')
#     print(f"Pending withdrawals: ${pending_withdrawals}")

#     # Check if the user has made any deposits
#     has_deposited = Transaction.objects.filter(
#         user=user,
#         transaction_type=Transaction.DEPOSIT,
#         status='confirmed'
#     ).exists()
#     print(f"Has deposited: {has_deposited}")

#     if request.method == 'POST':
#         print("\n=== Processing Withdrawal Request ===")
#         try:
#             # Check account status
#             if account.status != Account.STATUS_ACTIVE:
#                 print(f"Error: Account status is {account.status}")
#                 return JsonResponse({
#                     'success': False,
#                     'message': f"Your account is {account.status}. You cannot make a withdrawal."
#                 })

#             if not has_deposited:
#                 print("Error: User hasn't made any deposits")
#                 return JsonResponse({
#                     'success': False,
#                     'message': "You must make at least one deposit before you can withdraw funds."
#                 })

#             # Get form data
#             amount = Decimal(request.POST.get('amount', '0'))
#             payment_method_id = request.POST.get('payment_method')
#             wallet_address = request.POST.get('wallet_address')

#             print(f"Withdrawal request details:")
#             print(f"Amount: ${amount}")
#             print(f"Payment method ID: {payment_method_id}")
#             print(f"Wallet address: {wallet_address}")

#             # Validate payment method
#             try:
#                 payment_method = PaymentMethod.objects.get(id=payment_method_id, is_active=True)
#             except PaymentMethod.DoesNotExist:
#                 print("Error: Invalid payment method")
#                 return JsonResponse({
#                     'success': False,
#                     'message': "Invalid payment method selected."
#                 })

#             # Validate amount
#             if amount <= 0:
#                 print("Error: Invalid amount")
#                 return JsonResponse({
#                     'success': False,
#                     'message': "Please enter a valid amount."
#                 })

#             # Check against available balance
#             if amount > available_balance:
#                 print("Error: Insufficient available balance")
#                 return JsonResponse({
#                     'success': False,
#                     'message': f"Insufficient available balance. Your available balance is ${available_balance}"
#                 })

#             # Check if there are pending withdrawals
#             if pending_withdrawals > 0:
#                 print("Error: Has pending withdrawals")
#                 return JsonResponse({
#                     'success': False,
#                     'message': "You have pending withdrawal requests. Please wait for them to be processed."
#                 })

#             # Create withdrawal transaction
#             transaction = Transaction.objects.create(
#                 user=request.user,
#                 transaction_type=Transaction.WITHDRAWAL,
#                 amount=amount,
#                 payment_method=payment_method,
#                 wallet_used=wallet_address,
#                 timestamp=timezone.now(),
#                 status='pending'
#             )
#             print(f"Created transaction: {transaction}")

#             # Create notification for withdrawal request
#             Notification.create_notification(
#                 user=request.user,
#                 title="Withdrawal Request Submitted",
#                 message=f"Your withdrawal request of ${amount} via {payment_method.name} has been submitted and is pending approval",
#                 notification_type='transaction',
#                 link='/user/transactions/'
#             )

#             # Send notification to admin
#             try:
#                 ip = request.META.get('REMOTE_ADDR', 'Unknown IP')
#                 send_withdrawal_notification(amount, request.user.username, ip)
#                 print(f"Sent withdrawal notification to admin")
#             except Exception as e:
#                 print(f"Warning: Failed to send notification: {str(e)}")
#                 # Continue processing as this is not critical

#             return JsonResponse({
#                 'success': True,
#                 'message': "Your withdrawal request has been submitted for approval."
#             })

#         except InvalidOperation as e:
#             print(f"Error: Invalid decimal operation: {str(e)}")
#             return JsonResponse({
#                 'success': False,
#                 'message': "Invalid amount format. Please enter a valid number."
#             })
#         except Exception as e:
#             print(f"Error: Unexpected error during withdrawal: {str(e)}")
#             return JsonResponse({
#                 'success': False,
#                 'message': "An unexpected error occurred. Please try again later."
#             })

#     print("\n=== Rendering Withdrawal Page ===")
#     return render(request, 'user-admin/withdrawal.html', {
#         'account': account,
#         'available_balance': available_balance,
#         'pending_withdrawals': pending_withdrawals,
#         'has_deposited': has_deposited,
#         'payment_methods': PaymentMethod.objects.filter(is_active=True)
#     })
    
# def withdrawal_confirmation(request):
#     if request.method == 'GET':
#         try:
#             amount = request.GET.get('amount')
#             payment_method_id = request.GET.get('payment_method')
#             wallet_address = request.GET.get('wallet_address')

#             if not all([amount, payment_method_id, wallet_address]):
#                 messages.error(request, "Missing required withdrawal information")
#                 return redirect('withdrawal')

#             payment_method = PaymentMethod.objects.get(id=payment_method_id)
#             account = Account.objects.get(user=request.user)
#             amount = Decimal(amount)
            
#             # Calculate any fees or charges (if applicable)
#             charge_amount = Decimal('0.00')  # Add your fee calculation logic here
#             total_payable = amount + charge_amount

#             context = {
#                 'amount': amount,
#                 'charge_amount': charge_amount,
#                 'total_payable': total_payable,
#                 'payment_method': payment_method,
#                 'wallet_address': wallet_address,
#                 'account': account
#             }

#             return render(request, 'user-admin/withdrawal-confirmation.html', context)

#         except (PaymentMethod.DoesNotExist, Account.DoesNotExist, ValueError) as e:
#             messages.error(request, str(e))
#             return redirect('withdrawal')

#     elif request.method == 'POST':
#         try:
#             # Check for pending withdrawals
#             pending_withdrawals = Transaction.objects.filter(
#                 user=request.user,
#                 transaction_type=Transaction.WITHDRAWAL,
#                 status='pending'
#             ).exists()

#             if pending_withdrawals:
#                 return JsonResponse({
#                     'success': False,
#                     'message': "You have pending withdrawal requests. Please wait for them to be processed."
#                 })

#             amount = Decimal(request.POST.get('amount'))
#             payment_method_id = request.POST.get('payment_method')
#             wallet_address = request.POST.get('wallet_address')
            
#             payment_method = PaymentMethod.objects.get(id=payment_method_id)
#             account = Account.objects.get(user=request.user)

#             if amount <= 0:
#                 return JsonResponse({
#                     'success': False,
#                     'message': "Invalid withdrawal amount"
#                 })

#             if amount > account.available_balance:
#                 return JsonResponse({
#                     'success': False,
#                     'message': "Insufficient balance"
#                 })

#             # Create withdrawal transaction first to get the transactionid
#             transaction = Transaction.objects.create(
#                 user=request.user,
#                 transaction_type=Transaction.WITHDRAWAL,
#                 amount=amount,
#                 payment_method=payment_method,
#                 wallet_used=wallet_address,
#                 status='pending'
#             )
#             print(f"Created transaction: {transaction}")

#             # Create Transactions record with the same transactionid
#             Transactions.objects.create(
#                 user=request.user,
#                 transactionid=transaction.transactionid,  # Use the same transactionid
#                 transaction_type=Transaction.WITHDRAWAL,
#                 status='pending',
#                 amount=amount,
#                 payment_method=payment_method,
#                 wallet_used=wallet_address,
#                 timestamp=timezone.now(),
#                 description=f"New withdrawal for {request.user}"
#             )

#             ip = request.META.get('REMOTE_ADDR', 'Unknown IP')
#             send_withdrawal_notification(amount, request.user.username, ip)
#             send_withdrawal_notification_status(request.user, amount, request.user.username, status='pending')
#             print(f"Sent withdrawal notification to admin")
            
#             # Create notification
#             Notification.create_notification(
#                 user=request.user,
#                 title="Withdrawal Request Submitted",
#                 message=f"Your withdrawal request for ${amount} has been submitted and is pending approval.",
#                 notification_type='transaction',
#                 link='/user/transactions/'
#             )

#             return JsonResponse({
#                 'success': True,
#                 'message': "Your withdrawal request has been submitted successfully and is pending approval."
#             })

#         except Exception as e:
#             return JsonResponse({
#                 'success': False,
#                 'message': str(e)
#             })

#     return redirect('withdrawal')

# def get_active_deposit(user):
#     """Calculate total active deposits for a user"""
#     # Get all confirmed deposits and investments
#     active_deposits = Transaction.objects.filter(
#         user=user,
#         transaction_type=Transaction.DEPOSIT,
#         status='confirmed',
#         confirmed=True
#     ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
#     # Get active investments
#     active_investments = Investment.objects.filter(
#         user=user,
#         status='confirmed',
#         completed=False,
#         end_date__gt=timezone.now()
#     ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
#     total_active = active_deposits + active_investments
    
#     # Log the calculation for debugging
#     logger.info(f"Active Deposits for {user.username}:")
#     logger.info(f"- Confirmed deposits: ${active_deposits}")
#     logger.info(f"- Active investments: ${active_investments}")
#     logger.info(f"- Total active: ${total_active}")
    
#     return total_active

# def get_last_deposit(user):
#     try:
#         last_deposit = Transaction.objects.filter(
#             user=user,
#             transaction_type=Transaction.DEPOSIT,
#             confirmed=True,
#             status='confirmed'
#         ).latest('timestamp')  # Get the most recent deposit by timestamp
#         return {
#             'amount': last_deposit.amount,
#             'timestamp': last_deposit.timestamp
#         }
#     except Transaction.DoesNotExist:
#         return {
#             'amount': Decimal('0.00'),
#             'timestamp': None
#         }

# def get_last_withdrawal(user):
#     try:
#         last_withdrawal = Transaction.objects.filter(
#             user=user,
#             transaction_type=Transaction.WITHDRAWAL,
#             confirmed=True,
#             status='confirmed'
#         ).latest('timestamp')  # Get the most recent withdrawal by timestamp
#         return {
#             'amount': last_withdrawal.amount,
#             'timestamp': last_withdrawal.timestamp
#         }
#     except Transaction.DoesNotExist:
#         return {
#             'amount': Decimal('0.00'),
#             'timestamp': None
#         }

# def get_total_earnings(user):
#     # Fetch all confirmed withdrawals for the user
#     confirmed_withdrawals = Transaction.objects.filter(
#         user=user,
#         transaction_type=Transaction.WITHDRAWAL,
#         confirmed=True,
#         status='confirmed'
#     )
    
#     # Get the total amount withdrawn
#     total_withdrawn = confirmed_withdrawals.aggregate(
#         total_withdrawn=Sum('amount')
#     )['total_withdrawn'] or Decimal('0.00')
    
#     # Calculate earnings from ROI using the related InvestmentPlan's interest_rate
#     total_earnings_from_roi = confirmed_withdrawals.annotate(
#         roi_earnings=F('investment_plan__interest_rate') * F('amount') / 100
#     ).aggregate(
#         total_roi=Sum('roi_earnings')
#     )['total_roi'] or Decimal('0.00')

#     # The total earnings include the withdrawn amount plus the ROI earnings
#     total_earnings = total_withdrawn + total_earnings_from_roi
    
#     return total_earnings

# @login_required
# def account_details(request):
#     logger = logging.getLogger(__name__)
#     user = request.user
    
#     try:
#         # Fetch the user's account and profile
#         account = get_object_or_404(Account, user=user)
#         profile = get_object_or_404(Profilez, user=user)
#         # Process any matured investments when dashboard is accessed
#         matured_investments = Investment.objects.filter(
#             user=user,
#             completed=False,
#             status='approved',
#             end_date__lte=timezone.now()
#         )
        
#         if matured_investments.exists():
#             logger.info(f"Processing {matured_investments.count()} matured investments for {user.username}")
            
#             for investment in matured_investments:
#                 try:
#                     with db_transaction.atomic():
#                         # Calculate ROI if not already calculated
#                         if not investment.roi:
#                             investment.roi = investment.calculate_return()
                        
#                         # Update account balances
#                         account.available_balance += (investment.amount + investment.roi)  # Return principal + ROI
#                         account.total_earned += investment.roi
                        
#                         # Mark investment as completed
#                         investment.completed = True
#                         investment.is_running = False
#                         investment.save()
                        
#                         # Save account changes
#                         account.save(update_fields=['available_balance', 'total_earned'])
                        
#                         # Create notification
#                         Notification.create_notification(
#                             user=user,
#                             title="Investment Matured",
#                             message=(
#                                 f"Your investment of ${investment.amount} in {investment.plan.name} plan has matured.\n"
#                                 f"ROI Earned: ${investment.roi}\n"
#                                 f"Total Return: ${investment.amount + investment.roi}\n"
#                                 f"The funds have been added to your available balance."
#                             ),
#                             notification_type='investment',
#                             link='/user/investments/'
#                         )
                        
#                         logger.info(f"Processed matured investment: ${investment.amount} + ${investment.roi} ROI for {user.username}")
                        
#                 except Exception as e:
#                     logger.error(f"Error processing matured investment {investment.id}: {str(e)}")
            
#             # Update active investments after processing matured ones
#             account.update_active_investments()
            
#             # Refresh account to get latest values
#             account.refresh_from_db()

        
#         # Initialize default values
#         context = {
#             'user': user,
#             'profile': profile,
#             'account': account,
#             'total_commission': Decimal('0.00'),
#             'referrals_count': 0,
#             'profile_referral_link': '',
            
#             # Default values for all numeric fields
#             'available_balance': Decimal('0.00'),
#             'invested_balance': Decimal('0.00'),
#             'total_deposits': Decimal('0.00'),
#             'total_withdrawals': Decimal('0.00'),
#             'total_earned': Decimal('0.00'),
#             'referral_balance': Decimal('0.00'),
#             'pending_balance': Decimal('0.00'),
#             'active_investments': Decimal('0.00'),
#             'total_invested': Decimal('0.00'),
#             'total_roi_earned': Decimal('0.00'),
#             'pending_roi': Decimal('0.00'),
#             'expected_roi': Decimal('0.00'),
#             'active_deposit': Decimal('0.00'),
#             'total_earnings': Decimal('0.00'),
#             'last_deposit': Decimal('0.00'),
#             'last_withdrawal': Decimal('0.00'),
            
#             # Default values for dates
#             'last_deposit_date': None,
#             'last_withdrawal_date': None,
#             'last_access': timezone.now(),
            
#             # Default values for limits and status
#             'kyc_verified': False,
#             'withdrawal_limit': Decimal('0.00'),
#             'daily_withdrawal_limit': Decimal('0.00')
#         }
        
#         try:
#             # Get referrals and commission
#             referrals = Referral.objects.filter(referrer=profile)
#             context.update({
#                 'total_commission': sum(referral.total_commission for referral in referrals),
#                 'referrals_count': referrals.count(),
#                 'profile_referral_link': profile.referral_code,
#             })
#         except Exception as e:
#             logger.error(f"Error fetching referral data: {str(e)}")
        
#         try:
#             # Get investment statistics
#             investment_stats = ROIService.get_investment_statistics(user)
#             context.update({
#                 'total_invested': investment_stats['total_invested'],
#                 'total_roi_earned': investment_stats['total_roi_earned'],
#                 'pending_roi': investment_stats['pending_roi'],
#                 'expected_roi': investment_stats['expected_roi'],
#                 'active_investments': investment_stats['active_investments'],
#             })
#         except Exception as e:
#             logger.error(f"Error calculating investment statistics: {str(e)}")
        
#         try:
#             # Get transaction history
#             context.update({
#                 'active_deposit': get_active_deposit(user),
#                 'total_earnings': get_total_earnings(user),
#                 'last_deposit': get_last_deposit(user)['amount'],
#                 'last_deposit_date': get_last_deposit(user)['timestamp'],
#                 'last_withdrawal': get_last_withdrawal(user)['amount'],
#                 'last_withdrawal_date': get_last_withdrawal(user)['timestamp'],
#             })
#         except Exception as e:
#             logger.error(f"Error fetching transaction history: {str(e)}")
        
#         try:
#             # Update account-specific values
#             context.update({
#                 'available_balance': account.available_balance,
#                 'invested_balance': account.invested_balance,
#                 'total_deposits': account.total_deposits,
#                 'total_withdrawals': account.total_withdrawals,
#                 'total_earned': account.total_earned,
#                 'referral_balance': account.referral_balance,
#                 'pending_balance': account.pending_balance,
#                 'active_investments': account.active_investments,
#                 'kyc_verified': getattr(account, 'kyc_verified', False),
#                 'withdrawal_limit': account.withdrawal_limit,
#                 'daily_withdrawal_limit': account.daily_withdrawal_limit,
#             })
#         except Exception as e:
#             logger.error(f"Error fetching account details: {str(e)}")
        
#         return render(request, 'user-admin/dashboard.html', context)
        
#     except (Account.DoesNotExist, Profilez.DoesNotExist) as e:
#         logger.error(f"Account details error: {str(e)}")
#         messages.error(request, "Account or profile not found. Please contact support.")
#         return redirect('login')

# from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# @login_required
# def deposit_history(request):
#     """Display the user's deposit history with filtering options, pagination, and calculate the total amount."""
    
#     # Initialize filtering variables
#     transaction_type = ''
#     ec = '-1'
#     page = request.GET.get('page', 1)

#     # Check if the request method is POST
#     if request.method == 'GET':
#         transaction_type = request.GET.get('type', '')  
#         status = request.GET.get('status', '')  
#         date_time = request.GET.get('date_time', '')

#         # Apply filters based on user input
#         if transaction_type:
#             deposits = deposits.filter(transaction_type=transaction_type)

#         if status:
#             deposits = deposits.filter(status=status)
            
#         if date_time:
#             try:
#                 # Parse the date_time string into a datetime object
#                 parsed_date_time = parse_datetime(date_time)
#                 if not parsed_date_time:  # If `parse_datetime` fails, fallback to manual parsing
#                     parsed_date_time = datetime.strptime(date_time, '%Y-%m-%d')
#                 deposits = deposits.filter(timestamp__date=parsed_date_time.date())
#             except ValueError:
#                 # Handle invalid date format gracefully
#                 pass
            
#         # Handle GET request to just display deposits without filtering
#         deposits = TransactionHistory.objects.filter(
#             user=request.user,
#             transaction_type='deposit' # Filter by transaction type for deposits
#         ).order_by('-created_at')

#     # Calculate total amount before pagination
#     total_amount = deposits.aggregate(Sum('amount'))['amount__sum'] or 0

#     # Add pagination
#     paginator = Paginator(deposits, 10)  # Show 10 deposits per page
    
#     try:
#         deposits_page = paginator.page(page)
#     except PageNotAnInteger:
#         deposits_page = paginator.page(1)
#     except EmptyPage:
#         deposits_page = paginator.page(paginator.num_pages)

#     return render(request, 'user-admin/deposit-history.html', {
#         'deposits': deposits_page,
#         'transaction_type': transaction_type,
#         'status': status,
#         'date_time': date_time,
#         'total_amount': total_amount,
#     })

# from django.utils.dateparse import parse_datetime  # For parsing datetime
# @login_required
# def withdraw_history(request):
#     """Display the user's withdrawal history with filtering options, pagination, and calculate the total amount."""
    
#     # Initialize filtering variables
#     transaction_type = ''
#     status = ''
#     date_time = ''

#     # Start with the base query and add ordering
#     withdraws = Transactions.objects.filter(
#         user=request.user,
#         transaction_type='withdrawal'  # Filter by transaction type for withdrawals
#     ).order_by('-timestamp')  # Order by timestamp in descending order

#     # Check if the request method is GET
#     if request.method == 'GET':
#         transaction_type = request.GET.get('type', '')  
#         status = request.GET.get('status', '')  
#         date_time = request.GET.get('date_time', '')

#         # Apply filters based on user input
#         if transaction_type:
#             withdraws = withdraws.filter(transaction_type=transaction_type)

#         if status:
#             withdraws = withdraws.filter(status=status)
            
#         if date_time:
#             try:
#                 # Parse the date_time string into a datetime object
#                 parsed_date_time = parse_datetime(date_time)
#                 if not parsed_date_time:  # If `parse_datetime` fails, fallback to manual parsing
#                     parsed_date_time = datetime.strptime(date_time, '%Y-%m-%d')
#                 withdraws = withdraws.filter(timestamp__date=parsed_date_time.date())
#             except ValueError:
#                 # Handle invalid date format gracefully
#                 pass

#     # Calculate total amount after filtering
#     total_amount = withdraws.aggregate(Sum('amount'))['amount__sum'] or 0

#     # Pagination
#     page = request.GET.get('page', 1)  # Get the current page number from the request
#     paginator = Paginator(withdraws, 10)  # Show 10 transactions per page

#     try:
#         withdraws_paginated = paginator.page(page)
#     except PageNotAnInteger:
#         withdraws_paginated = paginator.page(1)  # Fallback to the first page
#     except EmptyPage:
#         withdraws_paginated = paginator.page(paginator.num_pages)  # Fallback to the last page

#     return render(request, 'user-admin/withdraw-history.html', {
#         'withdraws': withdraws_paginated,  # Pass paginated transactions to the template
#         'transaction_type': transaction_type,
#         'status': status,
#         'date_time': date_time,  # Pass the date_time back for use in the template
#         'total_amount': total_amount,
#     })

# def earning_history(request):
#     if not request.user.is_authenticated:
#         return redirect('login')

#     # Get the user's account
#     account = get_object_or_404(Account, user=request.user)

#     # Get the user's confirmed deposits and calculate total deposit
#     total_deposit = Transaction.objects.filter(
#         user=request.user,
#         transaction_type=Transaction.DEPOSIT,
#         confirmed=True
#     ).aggregate(total_deposit=Sum('amount'))['total_deposit'] or 0

#     # Calculate total profit/ROI from investments
#     total_profit = Investment.objects.filter(user=request.user).aggregate(
#         total_profit=Sum('roi')  # Assuming 'roi' is the field name for ROI
#     )['total_profit'] or 0

#     # Calculate total earnings (deposit + profit)
#     total_earnings = total_deposit + total_profit

#     return render(request, 'user-admin/earning-history.html', {
#         'total_deposit': total_deposit,
#         'total_profit': total_profit,
#         'total_earnings': total_earnings,
#     })

# def get_client_ip(request):
#     # Get the client's IP address
#     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#     if x_forwarded_for:
#         ip = x_forwarded_for.split(',')[0]
#     else:
#         ip = request.META.get('REMOTE_ADDR')
    
#     # Log and print the client's IP
#     logger.info(f"Client IP: {ip}")  # Log the client's IP
#     print(f"Client IP: {ip}")  # Print the client's IP
#     return ip

# def transactions(request):
#     # Get all transactions initially
#     transactions_list = InvestmentTransactions.objects.all().order_by('-timestamp')  # Order by latest first

#     # Apply filters based on query parameters
#     transaction_id = request.GET.get('transaction_id')
#     payment_method = request.GET.get('payment_method')
#     transaction_type = request.GET.get('transaction_type')
#     datetrx = request.GET.get('datetrx')
#     status = request.GET.get('status')

#     if transaction_id:
#         transactions_list = transactions_list.filter(transactionid__icontains=transaction_id)
#     if payment_method:
#         transactions_list = transactions_list.filter(payment_method__name__icontains=payment_method)  # Assuming 'name' is a field in PaymentMethod
#     if transaction_type:
#         transactions_list = transactions_list.filter(transaction_type__icontains=transaction_type)
#     if datetrx:
#         transactions_list = transactions_list.filter(timestamp__date=datetrx)
#     if status:
#         transactions_list = transactions_list.filter(status=status)

#     # Pagination
#     page = request.GET.get('page', 1)  # Default to page 1
#     paginator = Paginator(transactions_list, 10)  # Show 10 transactions per page

#     try:
#         transactions = paginator.page(page)
#     except PageNotAnInteger:
#         transactions = paginator.page(1)
#     except EmptyPage:
#         transactions = paginator.page(paginator.num_pages)

#     context = {
#         'transactions': transactions,
#     }
#     return render(request, 'user-admin/transaction.html', context)
#  Example usage in your existing views:
# from django.views.decorators.csrf import csrf_exempt
# @csrf_exempt
# def calculate_investment(request):
#     """Calculate investment returns based on amount"""
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             amount = Decimal(str(data.get('amount', 0)))
            
#             # Find the appropriate plan for the amount
#             plan = InvestmentPlan.objects.filter(
#                 min_investment__lte=amount,
#                 max_investment__gte=amount
#             ).first()
            
#             if not plan:
#                 return JsonResponse({
#                     'status': 'error',
#                     'message': 'No suitable investment plan found for this amount'
#                 })
            
#             # Calculate ROI
#             roi = amount * (plan.interest_rate / Decimal('100'))
#             total_value = amount + roi
            
#             return JsonResponse({
#                 'status': 'success',
#                 'data': {
#                     'plan_name': plan.name,
#                     'initial_investment': float(amount),
#                     'roi_rate': float(plan.interest_rate),
#                     'duration': plan.get_duration_display(),
#                     'expected_return': float(roi),
#                     'total_value': float(total_value)
#                 }
#             })
            
#         except (ValueError, TypeError, json.JSONDecodeError) as e:
#             return JsonResponse({
#                 'status': 'error',
#                 'message': str(e)
#             })
            
#     return JsonResponse({
#         'status': 'error',
#         'message': 'Invalid request method'
#     })

# @login_required
# def active_investment(request):
#     """
#     Display all investments that are:
#     1. Approved (both running and completed)
#     2. Ordered by completion status and start date
#     3. Paginated with filtering options
#     """
#     investments = Investment.objects.filter(
#         user=request.user,
#         status='approved'
#     ).order_by('completed', '-start_date').select_related('plan')

#     # Fetch distinct plan types
#     plan_types = InvestmentPlan.objects.values_list('name', flat=True).distinct()  # Assuming 'name' is the field for plan type

#     # Filtering
#     investment_type = request.GET.get('type', '')   
#     status = request.GET.get('status', '')  
#     date_time = request.GET.get('date_time', '')

#     if investment_type:
#         investments = investments.filter(plan__name=investment_type)

#     if status:
#         investments = investments.filter(status=status)

#     if date_time:
#         try:
#             parsed_date_time = parse_datetime(date_time) or datetime.strptime(date_time, '%Y-%m-%d')
#             investments = investments.filter(start_date__date=parsed_date_time.date())
#         except ValueError:
#             pass  # Handle invalid date formats gracefully

#     # Update status of each investment
#     for investment in investments:
#         investment.update_status()

#     # Pagination
#     page = request.GET.get('page', 1)
#     paginator = Paginator(investments, 10)  # Show 10 investments per page

#     try:
#         investments_page = paginator.page(page)
#     except PageNotAnInteger:
#         investments_page = paginator.page(1)
#     except EmptyPage:
#         investments_page = paginator.page(paginator.num_pages)

#     context = {
#         'investments': investments_page,
#         'plan_types': plan_types,  # Pass the plan types to the template
#         'investment_type': investment_type,
#         'status': status,
#         'date_time': date_time
#     }
#     return render(request, 'user-admin/active-investment.html', context)

