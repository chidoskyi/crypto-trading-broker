# loans/serializers.py
from rest_framework import serializers
from funds.serializers import TransactionSerializer
from loans.models import LoanProduct, Loan, LoanRepayment

class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = ['id', 'name', 'description', 'min_amount', 'max_amount',
                  'interest_rate', 'term_days', 'collateral_ratio',
                  'is_active', 'created_at']

class LoanSerializer(serializers.ModelSerializer):
    product_detail = LoanProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = Loan
        fields = ['id', 'product', 'product_detail', 'amount', 'interest_rate',
                  'term_days', 'collateral_amount', 'collateral_currency',
                  'outstanding_balance', 'status', 'applied_at', 'approved_at',
                  'disbursed_at', 'due_date', 'repaid_at']
        read_only_fields = ['id', 'interest_rate', 'outstanding_balance', 
                           'status', 'applied_at', 'approved_at', 'disbursed_at',
                           'due_date', 'repaid_at']
    
    def validate(self, attrs):
        product = attrs['product']
        amount = attrs['amount']
        
        if amount < product.min_amount or amount > product.max_amount:
            raise serializers.ValidationError(
                f"Amount must be between {product.min_amount} and {product.max_amount}"
            )
        
        # Calculate required collateral
        required_collateral = amount * product.collateral_ratio / 100
        if attrs['collateral_amount'] < required_collateral:
            raise serializers.ValidationError(
                f"Minimum collateral required: {required_collateral}"
            )
        
        return attrs

class LoanRepaymentSerializer(serializers.ModelSerializer):
    transaction_detail = TransactionSerializer(source='transaction', read_only=True)
    
    class Meta:
        model = LoanRepayment
        fields = ['id', 'loan', 'amount', 'principal_amount', 'interest_amount',
                  'transaction', 'transaction_detail', 'created_at']
        read_only_fields = ['id', 'principal_amount', 'interest_amount', 
                           'created_at']