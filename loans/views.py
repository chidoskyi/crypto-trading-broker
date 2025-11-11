# loans/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from loans.models import LoanProduct, Loan, LoanRepayment
from loans.serializers import (
    LoanProductSerializer, LoanSerializer, LoanRepaymentSerializer
)
from funds.models import Wallet, Transaction

class LoanProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Loan product listing"""
    serializer_class = LoanProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = LoanProduct.objects.filter(is_active=True)

class LoanViewSet(viewsets.ModelViewSet):
    """Loan management"""
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Loan.objects.all()
        return Loan.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Apply for a loan"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user has KYC verified
        if not request.user.is_verified:
            return Response(
                {'error': 'KYC verification required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has active loans
        active_loans = Loan.objects.filter(
            user=request.user,
            status__in=['approved', 'active']
        ).count()
        
        if active_loans >= 3:
            return Response(
                {'error': 'Maximum active loans reached'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check collateral availability
        collateral_currency = serializer.validated_data['collateral_currency']
        collateral_amount = serializer.validated_data['collateral_amount']
        
        wallet = Wallet.objects.get(
            user=request.user,
            currency=collateral_currency
        )
        
        if wallet.balance < collateral_amount:
            return Response(
                {'error': 'Insufficient collateral'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Lock collateral
        wallet.balance -= collateral_amount
        wallet.locked_balance += collateral_amount
        wallet.save()
        
        # Create loan
        product = serializer.validated_data['product']
        loan = Loan.objects.create(
            user=request.user,
            product=product,
            amount=serializer.validated_data['amount'],
            interest_rate=product.interest_rate,
            term_days=product.term_days,
            collateral_amount=collateral_amount,
            collateral_currency=collateral_currency,
            outstanding_balance=serializer.validated_data['amount']
        )
        
        return Response(
            LoanSerializer(loan).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve loan (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        loan = self.get_object()
        
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update loan status
        loan.status = 'approved'
        loan.approved_by = request.user
        loan.approved_at = timezone.now()
        loan.disbursed_at = timezone.now()
        loan.due_date = timezone.now().date() + timedelta(days=loan.term_days)
        loan.save()
        
        # Credit user's wallet
        wallet, _ = Wallet.objects.get_or_create(
            user=loan.user,
            currency='USD'
        )
        wallet.balance += loan.amount
        wallet.save()
        
        # Create transaction
        Transaction.objects.create(
            user=loan.user,
            transaction_type='loan',
            currency='USD',
            amount=loan.amount,
            status='completed',
            reference_id=f'LOAN-{loan.id}',
            completed_at=timezone.now()
        )
        
        return Response({'message': 'Loan approved and disbursed'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject loan (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        loan = self.get_object()
        
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Unlock collateral
        wallet = Wallet.objects.get(
            user=loan.user,
            currency=loan.collateral_currency
        )
        wallet.balance += loan.collateral_amount
        wallet.locked_balance -= loan.collateral_amount
        wallet.save()
        
        # Update loan status
        loan.status = 'rejected'
        loan.approved_by = request.user
        loan.approved_at = timezone.now()
        loan.save()
        
        return Response({'message': 'Loan rejected'})
    
    @action(detail=True, methods=['post'])
    def repay(self, request, pk=None):
        """Make loan repayment"""
        loan = self.get_object()
        
        if loan.status not in ['approved', 'active']:
            return Response(
                {'error': 'Loan is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = Decimal(str(request.data.get('amount')))
        
        if amount <= 0:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check wallet balance
        wallet = Wallet.objects.get(
            user=request.user,
            currency='USD'
        )
        
        if wallet.balance < amount:
            return Response(
                {'error': 'Insufficient balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate principal and interest
        total_interest = (loan.amount * loan.interest_rate / 100 * 
                         loan.term_days / 365)
        total_due = loan.amount + total_interest
        paid_so_far = loan.amount - loan.outstanding_balance
        
        # Simple allocation: pay interest first
        remaining_interest = total_interest - (paid_so_far * 
                                              (total_interest / loan.amount))
        
        if amount <= remaining_interest:
            interest_amount = amount
            principal_amount = Decimal('0')
        else:
            interest_amount = remaining_interest
            principal_amount = amount - interest_amount
        
        # Deduct from wallet
        wallet.balance -= amount
        wallet.save()
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='loan_repayment',
            currency='USD',
            amount=amount,
            status='completed',
            reference_id=f'REPAY-{loan.id}-{timezone.now().timestamp()}',
            completed_at=timezone.now()
        )
        
        # Create repayment record
        LoanRepayment.objects.create(
            loan=loan,
            amount=amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            transaction=transaction
        )
        
        # Update loan
        loan.outstanding_balance -= principal_amount
        
        if loan.outstanding_balance <= Decimal('0.01'):
            loan.outstanding_balance = Decimal('0')
            loan.status = 'repaid'
            loan.repaid_at = timezone.now()
            
            # Release collateral
            collateral_wallet = Wallet.objects.get(
                user=request.user,
                currency=loan.collateral_currency
            )
            collateral_wallet.balance += loan.collateral_amount
            collateral_wallet.locked_balance -= loan.collateral_amount
            collateral_wallet.save()
        else:
            loan.status = 'active'
        
        loan.save()
        
        return Response({
            'message': 'Repayment successful',
            'outstanding_balance': loan.outstanding_balance
        })

class LoanRepaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Loan repayment history"""
    serializer_class = LoanRepaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LoanRepayment.objects.filter(loan__user=self.request.user)