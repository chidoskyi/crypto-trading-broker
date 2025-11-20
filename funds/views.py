# funds/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from funds.models import Wallet, Transaction, Deposit, Withdrawal, CryptoWalletAddress, PendingDeposit, DepositMethod
from funds.serializers import (
    WalletSerializer, TransactionSerializer, 
    DepositSerializer, WithdrawalSerializer,
        CryptoWalletAddressSerializer, PendingDepositSerializer,
        DepositMethodSerializer
)
from funds.services.wallet_generator import wallet_generator

class DepositMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """Available deposit methods"""
    queryset = DepositMethod.objects.filter(is_active=True)
    serializer_class = DepositMethodSerializer
    permission_classes = [IsAuthenticated]

class CryptoWalletViewSet(viewsets.ReadOnlyModelViewSet):
    """Crypto wallet addresses"""
    serializer_class = CryptoWalletAddressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CryptoWalletAddress.objects.filter(
            user=self.request.user,
            is_active=True
        )
    
    @action(detail=False, methods=['post'])
    def generate_address(self, request):
        """Generate deposit address for currency/network"""
        currency = request.data.get('currency')
        network = request.data.get('network')
        
        if not currency or not network:
            return Response(
                {'error': 'currency and network are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate currency/network combination
        valid_combinations = {
            'BTC': ['BTC'],
            'ETH': ['ETH'],
            'USDT': ['ETH', 'BSC', 'TRC20'],
            'USDC': ['ETH', 'BSC'],
            'BNB': ['BSC'],
        }
        
        if currency not in valid_combinations:
            return Response(
                {'error': 'Invalid currency'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if network not in valid_combinations[currency]:
            return Response(
                {'error': f'Invalid network for {currency}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate or get existing address
        wallet_address = wallet_generator.generate_address(
            user=request.user,
            currency=currency,
            network=network
        )
        
        serializer = self.get_serializer(wallet_address)
        return Response(serializer.data)

class PendingDepositViewSet(viewsets.ReadOnlyModelViewSet):
    """Pending deposits"""
    serializer_class = PendingDepositSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PendingDeposit.objects.filter(
            user=self.request.user
        ).order_by('-detected_at')
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active (pending) deposits"""
        pending = self.get_queryset().filter(
            status__in=['detected', 'confirming']
        )
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    """Wallet management endpoints"""
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Transaction history endpoints"""
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['transaction_type', 'currency', 'status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

class DepositViewSet(viewsets.ModelViewSet):
    """Deposit management endpoints"""
    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Deposit.objects.filter(transaction__user=self.request.user)

class WithdrawalViewSet(viewsets.ModelViewSet):
    """Withdrawal management endpoints"""
    serializer_class = WithdrawalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Withdrawal.objects.filter(transaction__user=self.request.user)