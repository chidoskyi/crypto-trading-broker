# funds/serializers.py
import uuid
from rest_framework import serializers
from funds.models import Wallet, Transaction, Deposit, Withdrawal

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