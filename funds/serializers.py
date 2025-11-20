# funds/serializers.py
import uuid
from rest_framework import serializers
from funds.models import Wallet, Transaction, Deposit, Withdrawal, CryptoWalletAddress, PendingDeposit, DepositMethod

class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = ['id', 'currency', 'balance', 'locked_balance', 
                  'available_balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'locked_balance', 'created_at', 
                           'updated_at']
    
    def get_available_balance(self, obj):
        return obj.balance - obj.locked_balance

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_type', 'currency', 'amount', 'fee', 
                  'status', 'reference_id', 'external_id', 'notes',
                  'created_at', 'completed_at']
        read_only_fields = ['id', 'status', 'reference_id', 'created_at', 
                           'completed_at']

class DepositSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    
    class Meta:
        model = Deposit
        fields = ['id', 'transaction', 'payment_method', 'payment_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='deposit',
            currency=validated_data.get('currency', 'USD'),
            amount=validated_data.get('amount'),
            status='pending',
            reference_id=f'DEP-{uuid.uuid4().hex[:12].upper()}'
        )
        
        # Create deposit record
        deposit = Deposit.objects.create(
            transaction=transaction,
            payment_method=validated_data['payment_method'],
            payment_details=validated_data['payment_details']
        )
        
        return deposit

class WithdrawalSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    
    class Meta:
        model = Withdrawal
        fields = ['id', 'transaction', 'destination_type', 'destination_details']
    
    def create(self, validated_data):
        user = self.context['request'].user
        amount = validated_data.get('amount')
        currency = validated_data.get('currency', 'USD')
        
        # Check balance
        wallet = Wallet.objects.get(user=user, currency=currency)
        if wallet.balance < amount:
            raise serializers.ValidationError("Insufficient balance")
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='withdrawal',
            currency=currency,
            amount=amount,
            status='pending',
            reference_id=f'WDR-{uuid.uuid4().hex[:12].upper()}'
        )
        
        # Lock funds
        wallet.balance -= amount
        wallet.locked_balance += amount
        wallet.save()
        
        # Create withdrawal record
        withdrawal = Withdrawal.objects.create(
            transaction=transaction,
            destination_type=validated_data['destination_type'],
            destination_details=validated_data['destination_details']
        )
        
        return withdrawal

class DepositMethodSerializer(serializers.ModelSerializer):
    estimated_time = serializers.SerializerMethodField()
    
    class Meta:
        model = DepositMethod
        fields = ['id', 'currency', 'network', 'name', 'min_deposit',
                  'max_deposit', 'deposit_fee_percentage', 'deposit_fee_fixed',
                  'required_confirmations', 'estimated_time', 'contract_address',
                  'is_active']
    
    def get_estimated_time(self, obj):
        """Calculate estimated confirmation time"""
        total_seconds = obj.required_confirmations * obj.block_time_seconds
        minutes = total_seconds // 60
        return f"{minutes} minutes"

class CryptoWalletAddressSerializer(serializers.ModelSerializer):
    qr_code_url = serializers.SerializerMethodField()
    network_name = serializers.CharField(source='get_network_display', read_only=True)
    
    class Meta:
        model = CryptoWalletAddress
        fields = ['id', 'currency', 'network', 'network_name', 'address',
                  'qr_code', 'qr_code_url', 'total_received', 'total_deposits',
                  'created_at']
        read_only_fields = ['address', 'qr_code', 'total_received', 
                           'total_deposits', 'created_at']
    
    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
        return None

class PendingDepositSerializer(serializers.ModelSerializer):
    wallet_address_detail = CryptoWalletAddressSerializer(
        source='wallet_address', read_only=True
    )
    progress_percentage = serializers.SerializerMethodField()
    estimated_completion = serializers.SerializerMethodField()
    
    class Meta:
        model = PendingDeposit
        fields = ['id', 'currency', 'network', 'amount', 'tx_hash',
                  'from_address', 'confirmations', 'required_confirmations',
                  'status', 'progress_percentage', 'estimated_completion',
                  'detected_at', 'completed_at', 'wallet_address_detail']
    
    def get_progress_percentage(self, obj):
        if obj.required_confirmations == 0:
            return 100
        return min(100, (obj.confirmations / obj.required_confirmations) * 100)
    
    def get_estimated_completion(self, obj):
        if obj.status == 'completed':
            return None
        
        remaining = obj.required_confirmations - obj.confirmations
        if remaining <= 0:
            return "Completing now..."
        
        # Get block time from deposit method
        try:
            method = DepositMethod.objects.get(
                currency=obj.currency,
                network=obj.network
            )
            seconds = remaining * method.block_time_seconds
            minutes = seconds // 60
            return f"~{minutes} minutes"
        except DepositMethod.DoesNotExist:
            return "Unknown"