# serializers.py
from datetime import timedelta
from rest_framework import serializers
from django.utils import timezone
from .models import Deposit, Withdrawal, Wallet, PaymentMethod, WithdrawalCode, Investment, InvestmentPlan, InvestmentTransaction
from decimal import Decimal, InvalidOperation
from users.models import Account

class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment methods"""
    icon_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id',
            'name',
            'code',
            'icon_url',
            'is_active',
            'min_amount',
            'max_amount',
            'processing_time',
        ]
        read_only_fields = fields
    
    def get_icon_url(self, obj):
        """Return full URL for icon"""
        request = self.context.get('request')
        if obj.icon and request:
            return request.build_absolute_uri(obj.icon.url)
        return None


class WalletSerializer(serializers.ModelSerializer):
    # Remove username field since there's no user relationship
    class Meta:
        model = Wallet
        fields = [
            'id', 
            'btc_wallet', 'btc_qr',
            'eth_wallet', 'eth_qr', 
            'usdt_wallet', 'usdt_qr',
            'ltc_wallet', 'ltc_qr',
            'bnb_wallet', 'bnb_qr',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DepositSerializer(serializers.ModelSerializer):
    wallet_address = serializers.SerializerMethodField()
    # qr_code_url = serializers.SerializerMethodField()
    crypto_display = serializers.CharField(source='get_selected_crypto_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_details = PaymentMethodSerializer(source='payment_method', read_only=True)
    
    class Meta:
        model = Deposit
        fields = [
            'deposit_id',
            'amount',
            'payment_proof',
            'has_deposited',
            'status',
            'status_display',
            'wallet',
            'payment_method',
            'payment_method_details',
            'selected_crypto',
            'crypto_display',
            'wallet_address',
            'created_at',
        ]
        read_only_fields = ['deposit_id', 'wallet_address', 'status', 'created_at']
    
    def get_wallet_address(self, obj):
        """Return the selected wallet address"""
        return obj.get_admin_wallet_address()
    


class DepositCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating deposits - accepts payment method by name or code"""
    payment_method_name = serializers.CharField(write_only=True, required=True, allow_null=False)
    
    # Mapping for common name variations to crypto codes
    CRYPTO_NAME_MAPPING = {
        'bitcoin': 'BTC',
        'btc': 'BTC',
        'ethereum': 'ETH',
        'eth': 'ETH',
        'tether': 'USDT',
        'usdt': 'USDT',
        'litecoin': 'LTC',
        'ltc': 'LTC',
        'binance coin': 'BNB',
        'bnb': 'BNB',
    }
    
    class Meta:
        model = Deposit
        fields = [
            'amount',
            'payment_proof',
            'selected_crypto',
            'payment_method_name',
        ]
    
    def validate_amount(self, value):
        """Validate deposit amount"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
    
    def validate_selected_crypto(self, value):
        """Validate and normalize crypto code"""
        # Normalize the crypto code
        value_upper = value.upper()
        value_lower = value.lower()
        
        # Check if it's already a valid code
        valid_codes = [code for code, _ in Deposit.CRYPTO_CHOICES]
        if value_upper in valid_codes:
            return value_upper
        
        # Try to map from name to code
        if value_lower in self.CRYPTO_NAME_MAPPING:
            return self.CRYPTO_NAME_MAPPING[value_lower]
        
        raise serializers.ValidationError(
            f"Invalid cryptocurrency. Valid options: {', '.join(valid_codes)}"
        )
    
    def validate_payment_method_name(self, value):
        """Validate payment method by name or code"""
        # Normalize the value
        value_normalized = value.strip()
        
        # Try to find by name first (case-insensitive)
        try:
            payment_method = PaymentMethod.objects.get(
                name__iexact=value_normalized, 
                is_active=True
            )
            return payment_method
        except PaymentMethod.DoesNotExist:
            pass
        
        # Try to find by code as fallback
        try:
            payment_method = PaymentMethod.objects.get(
                code__iexact=value_normalized, 
                is_active=True
            )
            return payment_method
        except PaymentMethod.DoesNotExist:
            pass
        
        # Try to find by matching crypto code
        crypto_code = self.CRYPTO_NAME_MAPPING.get(value_normalized.lower(), value_normalized.upper())
        try:
            payment_method = PaymentMethod.objects.get(
                code__iexact=crypto_code,
                is_active=True
            )
            return payment_method
        except PaymentMethod.DoesNotExist:
            pass
        
        # If nothing found, raise error with available methods
        available_methods = PaymentMethod.objects.filter(is_active=True).values_list('name', flat=True)
        raise serializers.ValidationError(
            f"Payment method '{value}' not found or is not active. "
            f"Available methods: {', '.join(available_methods)}"
        )
    
    def validate(self, data):
        """Validate that the admin wallet exists and amount is within limits"""
        selected_crypto = data.get('selected_crypto')
        
        # Check if admin wallet address exists for selected crypto
        try:
            wallet = Wallet.get_wallet()
            wallet_field_name = f"{selected_crypto.lower()}_wallet"
            wallet_address = getattr(wallet, wallet_field_name, None)
            
            if not wallet_address:
                raise serializers.ValidationError(
                    f"Admin {selected_crypto} wallet address not configured. Please contact support."
                )
        except Exception as e:
            raise serializers.ValidationError(
                f"Error accessing wallet configuration: {str(e)}"
            )
        
        # Validate amount against payment method limits
        payment_method = data.get('payment_method_name')
        if payment_method:
            amount = data.get('amount')
            if amount < payment_method.min_amount:
                raise serializers.ValidationError(
                    f"Amount must be at least ${payment_method.min_amount} for {payment_method.name}"
                )
            if amount > payment_method.max_amount:
                raise serializers.ValidationError(
                    f"Amount must not exceed ${payment_method.max_amount} for {payment_method.name}"
                )
        
        return data
    
    def create(self, validated_data):
        """Create deposit with current user"""
        request = self.context.get('request')
        
        # Get payment method from validated data
        payment_method = validated_data.pop('payment_method_name')
        
        # Get the admin wallet
        admin_wallet = Wallet.get_wallet()
        
        deposit = Deposit.objects.create(
            user=request.user,
            wallet=admin_wallet,
            payment_method=payment_method,
            **validated_data
        )
        
        # # Generate QR code
        # deposit.generate_qr_code()
        deposit.save()
        
        return deposit


class DepositListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing deposits"""
    crypto_display = serializers.CharField(source='get_selected_crypto_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Deposit
        fields = [
            'deposit_id',
            'amount',
            'selected_crypto',
            'crypto_display',
            'status',
            'status_display',
            'has_deposited',
            'payment_method_name',
            'created_at',
        ]
        read_only_fields = fields


class WithdrawalCodeRequestSerializer(serializers.Serializer):
    """Serializer for requesting a withdrawal code"""
    
    def create(self, validated_data):
        """Create a withdrawal code request"""
        request = self.context.get('request')
        user = request.user
        
        # Check if user already has a pending code
        existing_code = WithdrawalCode.objects.filter(
            user=user,
            is_used=False,
            expiry_date__gt=timezone.now()
        ).first()
        
        if existing_code:
            raise serializers.ValidationError(
                f"You already have an active withdrawal code request. "
                f"Status: {'Approved' if existing_code.is_approved else 'Pending Approval'}. "
                f"Please wait for approval or use your existing code."
            )
        
        # Generate new code
        code = WithdrawalCode.generate_code(user)
        withdrawal_code = WithdrawalCode.objects.create(
            user=user,
            code=code,
            expiry_date=timezone.now() + timedelta(days=7),  # Valid for 7 days
            is_approved=False  # Admin must approve
        )
        
        return withdrawal_code


class WithdrawalCodeSerializer(serializers.ModelSerializer):
    """Serializer for withdrawal code"""
    is_valid = serializers.SerializerMethodField()
    time_until_expiry = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    
    class Meta:
        model = WithdrawalCode
        fields = [
            'code_id',
            'code',
            'is_approved',
            'is_used',
            'is_valid',
            'approval_status',
            'expiry_date',
            'time_until_expiry',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_is_valid(self, obj):
        """Check if code is valid"""
        return obj.is_valid()
    
    def get_time_until_expiry(self, obj):
        """Get time until expiry in human-readable format"""
        if obj.expiry_date < timezone.now():
            return "Expired"
        
        time_left = obj.expiry_date - timezone.now()
        days = time_left.days
        hours = int(time_left.seconds / 3600)
        
        if days > 0:
            return f"{days} day(s) {hours} hour(s)"
        return f"{hours} hour(s)"
    
    def get_approval_status(self, obj):
        """Get human-readable approval status"""
        if obj.is_used:
            return "Used"
        if not obj.is_approved:
            return "Pending Admin Approval"
        if timezone.now() > obj.expiry_date:
            return "Expired"
        return "Active"


class WithdrawalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating withdrawals - accepts payment method by name"""
    withdrawal_code_value = serializers.CharField(write_only=True, max_length=6)
    payment_method_name = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Withdrawal
        fields = [
            'amount',
            'wallet_address',
            'payment_method_name',
            'withdrawal_code_value',
        ]
    
    def validate_amount(self, value):
        """Validate withdrawal amount"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
    
    def validate_payment_method_name(self, value):
        """Validate payment method by name"""
        if not value:
            return None
            
        try:
            payment_method = PaymentMethod.objects.get(name__iexact=value, is_active=True)
            return payment_method
        except PaymentMethod.DoesNotExist:
            # Try to find by code as fallback
            try:
                payment_method = PaymentMethod.objects.get(code__iexact=value, is_active=True)
                return payment_method
            except PaymentMethod.DoesNotExist:
                raise serializers.ValidationError(
                    f"Payment method '{value}' not found or is not active. "
                    f"Available methods: {', '.join(PaymentMethod.objects.filter(is_active=True).values_list('name', flat=True))}"
                )
    
    def validate_withdrawal_code_value(self, value):
        """Validate the withdrawal code"""
        request = self.context.get('request')
        user = request.user
        
        try:
            code = WithdrawalCode.objects.get(
                code=value,
                user=user
            )
        except WithdrawalCode.DoesNotExist:
            raise serializers.ValidationError("Invalid withdrawal code")
        
        # Check if code is approved
        if not code.is_approved:
            raise serializers.ValidationError(
                "Your withdrawal code has not been approved yet. Please wait for admin approval."
            )
        
        # Check if code is already used
        if code.is_used:
            raise serializers.ValidationError("This withdrawal code has already been used")
        
        # Check if code is expired
        if timezone.now() > code.expiry_date:
            raise serializers.ValidationError("This withdrawal code has expired. Please request a new one.")
        
        return value
    
    def validate(self, data):
        """Validate amount against payment method limits if provided"""
        payment_method = data.get('payment_method_name')
        if payment_method:
            amount = data.get('amount')
            if amount < payment_method.min_amount:
                raise serializers.ValidationError(
                    f"Amount must be at least ${payment_method.min_amount} for {payment_method.name}"
                )
            if amount > payment_method.max_amount:
                raise serializers.ValidationError(
                    f"Amount must not exceed ${payment_method.max_amount} for {payment_method.name}"
                )
        
        return data
    
    def create(self, validated_data):
        """Create withdrawal with user's wallet"""
        request = self.context.get('request')
        wallet = Wallet.objects.get(user=request.user)
        
        # Get the withdrawal code
        code_value = validated_data.pop('withdrawal_code_value')
        withdrawal_code = WithdrawalCode.objects.get(
            code=code_value,
            user=request.user
        )
        
        # Get payment method from validated data
        payment_method = validated_data.pop('payment_method_name', None)
        
        # Create withdrawal
        withdrawal = Withdrawal.objects.create(
            wallet=wallet,
            withdrawal_code=withdrawal_code,
            payment_method=payment_method,
            **validated_data
        )
        
        return withdrawal


class WithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for withdrawal details"""
    user_email = serializers.CharField(source='wallet.user.email', read_only=True)
    code_info = WithdrawalCodeSerializer(source='withdrawal_code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_details = PaymentMethodSerializer(source='payment_method', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Withdrawal
        fields = [
            'withdrawal_id',
            'user_email',
            'amount',
            'wallet_address',
            'payment_method_name',
            'payment_method_details',
            'status',
            'status_display',
            'pending_withdrawals',
            'code_info',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
        
class DepositStatusUpdateSerializer(serializers.ModelSerializer):
    """Admin serializer for updating deposit status"""
    
    class Meta:
        model = Deposit
        fields = ['status', 'has_deposited']
    
    def validate_status(self, value):
        """Ensure valid status transition"""
        if value not in ['pending', 'confirmed', 'rejected']:
            raise serializers.ValidationError("Invalid status")
        return value
    
class InvestmentPlanSerializer(serializers.ModelSerializer):
    """Serializer for investment plans"""
    duration_display = serializers.CharField(source='get_duration_display', read_only=True)
    
    class Meta:
        model = InvestmentPlan
        fields = [
            'id', 'name', 'interest_rate', 'duration', 
            'duration_unit', 'duration_display', 'plan_types',
            'min_investment', 'max_investment'
        ]
        read_only_fields = ['id']


class InvestmentSerializer(serializers.ModelSerializer):
    """Serializer for investments"""
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_interest_rate = serializers.DecimalField(
        source='plan.interest_rate', 
        max_digits=5, 
        decimal_places=2, 
        read_only=True
    )
    progress_percentage = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Investment
        fields = [
            'id', 'plan', 'plan_name', 'plan_interest_rate',
            'amount', 'roi', 'start_date', 'end_date',
            'completed', 'is_running', 'is_reinvestment',
            'status', 'progress_percentage', 'remaining_seconds',
            'is_active'
        ]
        read_only_fields = [
            'id', 'roi', 'start_date', 'end_date', 
            'completed', 'status', 'plan_name', 
            'plan_interest_rate', 'is_active', 'progress_percentage'
        ]
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()
    
    def get_remaining_seconds(self, obj):
        return obj.get_remaining_seconds()
    
    def get_is_active(self, obj):
        return obj.is_active()


# class CreateInvestmentSerializer(serializers.Serializer):
#     """Serializer for creating new investments"""
#     amount = serializers.DecimalField(max_digits=12, decimal_places=2)
#     plan_id = serializers.IntegerField()
#     investment_type = serializers.ChoiceField(
#         choices=['invest', 'reinvest'],
#         default='invest'
#     )
#     payment_method_id = serializers.IntegerField(required=False, allow_null=True)
    
#     def validate_amount(self, value):
#         """Validate investment amount"""
#         if value <= 0:
#             raise serializers.ValidationError("Amount must be greater than zero.")
#         return value
    
#     def validate_plan_id(self, value):
#         """Validate plan exists"""
#         try:
#             plan = InvestmentPlan.objects.get(id=value)
#         except InvestmentPlan.DoesNotExist:
#             raise serializers.ValidationError("Invalid investment plan selected.")
#         return value
    
#     def validate(self, data):
#         """Cross-field validation"""
#         try:
#             plan = InvestmentPlan.objects.get(id=data['plan_id'])
#             amount = data['amount']
            
#             # Validate amount against plan limits
#             if amount < plan.min_investment:
#                 raise serializers.ValidationError({
#                     'amount': f"Minimum investment for this plan is ${plan.min_investment}"
#                 })
            
#             if amount > plan.max_investment:
#                 raise serializers.ValidationError({
#                     'amount': f"Maximum investment for this plan is ${plan.max_investment}"
#                 })
            
#             # Validate payment method for regular investments
#             is_reinvestment = data.get('investment_type') == 'reinvest'
#             if not is_reinvestment and not data.get('payment_method_id'):
#                 raise serializers.ValidationError({
#                     'payment_method_id': "Payment method is required for regular investments."
#                 })
            
#         except InvestmentPlan.DoesNotExist:
#             raise serializers.ValidationError({
#                 'plan_id': "Investment plan not found."
#             })
        
#         return data
class CreateInvestmentSerializer(serializers.Serializer):
    """Serializer for creating new investments"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    plan_id = serializers.IntegerField()
    investment_type = serializers.ChoiceField(
        choices=['invest', 'reinvest'],
        default='invest'
    )
    payment_method_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_amount(self, value):
        """Validate investment amount"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
    
    def validate_plan_id(self, value):
        """Validate plan exists"""
        try:
            plan = InvestmentPlan.objects.get(id=value)
        except InvestmentPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid investment plan selected.")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        try:
            plan = InvestmentPlan.objects.get(id=data['plan_id'])
            amount = data['amount']
            
            # Validate amount against plan limits
            if amount < plan.min_investment:
                raise serializers.ValidationError({
                    'amount': f"Minimum investment for this plan is ${plan.min_investment}"
                })
            
            if amount > plan.max_investment:
                raise serializers.ValidationError({
                    'amount': f"Maximum investment for this plan is ${plan.max_investment}"
                })
            
            # Only require payment_method_id for external payment investments
            # The ViewSet will determine if deposit_balance is sufficient
            # payment_method_id is only needed when using external payment methods
            
        except InvestmentPlan.DoesNotExist:
            raise serializers.ValidationError({
                'plan_id': "Investment plan not found."
            })
        
        return data

class AccountSerializer(serializers.ModelSerializer):
    """Serializer for investment account"""
    total_balance = serializers.DecimalField(
        source='total_balance',
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'username', 'available_balance', 'deposit_balance',
            'invested_balance', 'pending_balance', 'total_invested',
            'active_investments', 'total_earned', 'total_deposits',
            'total_withdrawals', 'pending_withdrawals', 'pending_investments',
            'status', 'total_balance', 'created_at', 'updated_at',
            'last_login', 'last_investment', 'last_withdrawal'
        ]
        read_only_fields = [
            'id', 'available_balance', 'invested_balance',
            'pending_balance', 'total_invested', 'active_investments',
            'total_earned', 'deposit_balance', 'total_deposits',
            'total_withdrawals', 'pending_withdrawals', 'pending_investments',
            'created_at', 'updated_at', 'last_login',
            'last_investment', 'last_withdrawal', 'total_balance'
        ]


class InvestmentTransactionSerializer(serializers.ModelSerializer):
    """Serializer for investment transactions"""
    payment_method_name = serializers.CharField(
        source='payment_method.name',
        read_only=True
    )
    plan_name = serializers.CharField(
        source='investment_plan.name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = InvestmentTransaction
        fields = [
            'id', 'transaction_type', 'amount', 'payment_method',
            'payment_method_name', 'wallet_used', 'timestamp',
            'confirmed', 'status', 'transactionid', 'description',
            'investment_plan', 'plan_name'
        ]
        read_only_fields = [
            'id', 'timestamp', 'transactionid', 
            'payment_method_name', 'plan_name'
        ]   
    