# users/views.py
import uuid
from rest_framework import generics, status, viewsets, mixins, permissions
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from rest_framework import serializers
from django.contrib.auth import get_user_model
from users.serializers import (
    CustomTokenObtainPairSerializer, ProfileCompletionSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer, ProfileSerializer, UserProfileSerializer, UserSerializer, UserRegistrationSerializer, KYCDocumentSerializer, AccountSerializer, ChangePasswordSerializer, UserProfileUpdateSerializer, CountrySerializer
)
from users.models import KYCDocument, Profile, Account, User, Country
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
import random
import string


User = get_user_model()


class CaptchaView(APIView):
    """Generate CAPTCHA code for registration security"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Generate and return a new CAPTCHA"""
        try:
            # Generate random CAPTCHA code (6 characters: letters and numbers)
            captcha_code = ''.join(random.choices(
                string.ascii_uppercase + string.digits, 
                k=6
            ))
            
            # Generate unique key for this CAPTCHA
            captcha_key = str(uuid.uuid4())
            
            # Store in cache for 10 minutes (600 seconds)
            cache.set(
                f'captcha_{captcha_key}', 
                captcha_code, 
                timeout=600
            )
            
            return Response({
                'captcha_key': captcha_key,
                'captcha_code': captcha_code,
                'expires_in': 600  # seconds
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to generate CAPTCHA',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Handle user registration with transaction"""
        try:
            # Log registration attempt
            logger.info(f"Registration attempt for email: {request.data.get('email')}")
            
            # Validate and create user
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Create user (wrapped in transaction)
            user = serializer.save()
            
            logger.info(f"User registered successfully: {user.email} (ID: {user.id})")
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Prepare user data for response
            user_data = UserSerializer(user).data

            # Check if profile is complete (you might want to add this logic)
            # profile_complete = hasattr(user, 'profile') and user.profile.is_complete
            
            return Response({
                'success': True,
                'user': user_data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                # 'profile_complete': profile_complete, 
                # 'redirect': '/complete-profile' if not profile_complete else '/dashboard',
                'message': 'Registration successful! Welcome to Isotradex.'
            }, status=status.HTTP_201_CREATED)
            
        except serializers.ValidationError as e:
            # Handle validation errors
            logger.warning(f"Registration validation error: {e.detail}")
            return Response({
                'success': False,
                'errors': e.detail,
                'message': 'Please correct the errors and try again.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected registration error: {str(e)}", exc_info=True)
            
            return Response({
                'success': False,
                'error': 'Registration failed',
                'detail': 'An unexpected error occurred. Please try again later.',
                'message': str(e) if settings.DEBUG else 'Registration failed. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RefreshCaptchaView(APIView):
    """Refresh CAPTCHA if user needs a new one"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Delete old CAPTCHA and generate new one"""
        old_captcha_key = request.data.get('old_captcha_key')
        
        # Delete old CAPTCHA if provided
        if old_captcha_key:
            cache.delete(f'captcha_{old_captcha_key}')
        
        # Generate new CAPTCHA
        captcha_code = ''.join(random.choices(
            string.ascii_uppercase + string.digits, 
            k=6
        ))
        captcha_key = str(uuid.uuid4())
        
        cache.set(f'captcha_{captcha_key}', captcha_code, timeout=600)
        
        return Response({
            'captcha_key': captcha_key,
            'captcha_code': captcha_code,
            'expires_in': 600
        }, status=status.HTTP_200_OK)


# Optional: Country list endpoint if you want to populate dropdown dynamically
class CountryListView(generics.ListAPIView):
    queryset = Country.objects.all().order_by('name')
    serializer_class = CountrySerializer
    permission_classes = [AllowAny]
    
class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # You can add additional login tracking or logging here
        if response.status_code == 200:
            # Log successful login, update last_login, etc.
            print(f"User logged in successfully")  # Replace with proper logging
        
        return response



class PasswordResetRequestView(generics.GenericAPIView):
    """Handle password reset requests"""
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        
        if user:
            # Generate reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build reset URL
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
            
            # Send email
            try:
                send_mail(
                    subject='Password Reset Request - Isotradex',
                    message=f'''
Hello {user.username},

You requested a password reset for your Isotradex account.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you didn't request this reset, please ignore this email.

Best regards,
Isotradex Team
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                logger.info(f"Password reset email sent to: {email}")
                
            except Exception as e:
                logger.error(f"Failed to send password reset email to {email}: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'Failed to send reset email. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Always return success to prevent email enumeration
        return Response({
            'success': True,
            'message': 'If an account with that email exists, a password reset link has been sent.'
        }, status=status.HTTP_200_OK)

class PasswordResetConfirmView(generics.GenericAPIView):
    """Handle password reset confirmation"""
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, uidb64, token):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user is not None and default_token_generator.check_token(user, token):
            # Token is valid, reset password
            new_password = serializer.validated_data['new_password']
            user.set_password(new_password)
            user.save()
            
            logger.info(f"Password reset successful for user: {user.email}")
            
            return Response({
                'success': True,
                'message': 'Password has been reset successfully. You can now login with your new password.'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'Invalid or expired reset link. Please request a new password reset.'
            }, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetValidateView(generics.GenericAPIView):
    """Validate password reset token"""
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user is not None and default_token_generator.check_token(user, token):
            return Response({
                'success': True,
                'message': 'Reset token is valid.'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'Invalid or expired reset link.'
            }, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(generics.GenericAPIView):
    """Change user password"""
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Change user password"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        logger.info(f"Password changed successfully for user: {user.email}")
        
        return Response({
            'success': True,
            'message': 'Password has been changed successfully.'
        }, status=status.HTTP_200_OK)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Return the current authenticated user"""
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        """Get user profile"""
        serializer = self.get_serializer(request.user)
        return Response({
            'success': True,
            'user': serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        """Update user profile"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response({
                'success': True,
                'user': serializer.data,
                'message': 'Profile updated successfully'
            })
        except serializers.ValidationError as e:
            return Response({
                'success': False,
                'errors': e.detail,
                'message': 'Failed to update profile'
            }, status=status.HTTP_400_BAD_REQUEST)

class ProfileCompletionView(APIView):
    """Complete user profile after registration"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Handle profile completion"""
        try:
            # Get or create profile
            profile, created = Profile.objects.get_or_create(user=request.user)
            
            # Check if profile is already completed
            if not created and profile.is_complete:
                return Response({
                    'success': True,
                    'message': 'Profile already completed',
                    'redirect': '/dashboard'
                }, status=status.HTTP_200_OK)
            
            # Validate and save profile data
            serializer = ProfileCompletionSerializer(profile, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                
                logger.info(f"Profile completed for user: {request.user.email}")
                
                return Response({
                    'success': True,
                    'profile': ProfileSerializer(profile).data,
                    'message': 'Profile completed successfully!',
                    'redirect': '/dashboard'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'errors': serializer.errors,
                    'message': 'Please correct the errors and try again.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Profile completion error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to complete profile',
                'detail': str(e) if settings.DEBUG else 'An error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """Get current user's profile"""
        try:
            profile, created = Profile.objects.get_or_create(user=request.user)
            serializer = ProfileSerializer(profile)
            
            return Response({
                'success': True,
                'profile': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching profile: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to fetch profile'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


class UserLogoutView(APIView):
    """User logout endpoint"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Handle user logout"""
        try:
            # Get refresh token from request
            refresh_token = request.data.get('refresh_token')
            
            if refresh_token:
                try:
                    # Blacklist the refresh token
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception as e:
                    logger.warning(f"Token blacklist failed: {str(e)}")
            
            logger.info(f"User logged out: {request.user.email}")
            
            return Response({
                'success': True,
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({
                'success': True,
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)


class KYCViewSet(viewsets.ModelViewSet):
    """KYC verification endpoints"""
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return KYCDocument.objects.all()
        return KYCDocument.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Submit KYC documents"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user already submitted KYC
        if KYCDocument.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'KYC already submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        kyc = serializer.save(user=request.user)
        request.user.kyc_status = 'pending'
        request.user.save()
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve KYC (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kyc = self.get_object()
        kyc.user.kyc_status = 'approved'
        kyc.user.is_verified = True
        kyc.user.save()
        
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.save()
        
        return Response({'message': 'KYC approved'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject KYC (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        kyc = self.get_object()
        kyc.user.kyc_status = 'rejected'
        kyc.user.save()
        
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = request.data.get('reason', '')
        kyc.save()
        
        return Response({'message': 'KYC rejected'})
    
    
class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    """Account management endpoints"""
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get the current user's account"""
        return Account.objects.get(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get all account balances"""
        try:
            account = Account.objects.get(user=request.user)
            
            return Response({
                'status': account.status,
                'balances': {
                    'deposit_balance': str(account.deposit_balance),
                    'trading_balance': str(account.trading_balance),
                    'investment_balance': str(account.investment_balance),
                    'available_balance': str(account.available_balance),
                    'invested_balance': str(account.invested_balance),
                    'pending_balance': str(account.pending_balance),
                    'total_balance': str(account.total_balance),
                },
                'statistics': {
                    'total_deposits': str(account.total_deposits),
                    'total_withdrawals': str(account.total_withdrawals),
                    'total_earned': str(account.total_earned),
                    'active_investments': str(account.active_investments),
                }
            })
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def transfer_to_trading(self, request):
        """
        Transfer funds from deposit_balance to trading_balance
        This is how users fund their trading account
        """
        amount = request.data.get('amount')
        
        # Validate amount
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount <= 0:
            return Response(
                {'error': 'Amount must be greater than zero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get user's account with row lock
            account = Account.objects.select_for_update().get(user=request.user)
            
            # Check account status
            if account.status != Account.STATUS_ACTIVE:
                return Response(
                    {'error': f'Account is {account.status}. Transfers not allowed.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check sufficient balance
            if account.deposit_balance < amount:
                return Response(
                    {
                        'error': 'Insufficient deposit balance',
                        'required': str(amount),
                        'available': str(account.deposit_balance)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Perform transfer
            account.deposit_balance -= amount
            account.trading_balance += amount
            account.save()
            
            # Log the transfer
            logger.info(
                f"Balance transfer: User {request.user.id} transferred "
                f"${amount} from deposit to trading balance"
            )
            
            # Create transaction record (optional)
            from funds.models import Transaction
            Transaction.objects.create(
                user=request.user,
                transaction_type='transfer',
                currency='USD',
                amount=amount,
                status='completed',
                reference_id=f'TRANSFER-DEPOSIT-TO-TRADING-{timezone.now().timestamp()}',
                # description='Transfer from deposit balance to trading balance',
                completed_at=timezone.now()
            )
            
            return Response({
                'message': 'Transfer successful',
                'amount_transferred': str(amount),
                'balances': {
                    'deposit_balance': str(account.deposit_balance),
                    'trading_balance': str(account.trading_balance),
                    'total_balance': str(account.total_balance),
                }
            }, status=status.HTTP_200_OK)
            
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Transfer failed for user {request.user.id}: {str(e)}")
            return Response(
                {'error': 'Transfer failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def transfer_to_investment(self, request):
        """
        Transfer funds from deposit_balance to investment_balance
        For users who want to invest in plans
        """
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount <= 0:
            return Response(
                {'error': 'Amount must be greater than zero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            account = Account.objects.select_for_update().get(user=request.user)
            
            if account.status != Account.STATUS_ACTIVE:
                return Response(
                    {'error': f'Account is {account.status}. Transfers not allowed.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if account.deposit_balance < amount:
                return Response(
                    {
                        'error': 'Insufficient deposit balance',
                        'required': str(amount),
                        'available': str(account.deposit_balance)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Perform transfer
            account.deposit_balance -= amount
            account.investment_balance += amount
            account.save()
            
            logger.info(
                f"Balance transfer: User {request.user.id} transferred "
                f"${amount} from deposit to investment balance"
            )
            
            return Response({
                'message': 'Transfer successful',
                'amount_transferred': str(amount),
                'balances': {
                    'deposit_balance': str(account.deposit_balance),
                    'investment_balance': str(account.investment_balance),
                    'total_balance': str(account.total_balance),
                }
            }, status=status.HTTP_200_OK)
            
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Transfer failed for user {request.user.id}: {str(e)}")
            return Response(
                {'error': 'Transfer failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def transfer_from_trading(self, request):
        """
        Transfer funds from trading_balance back to deposit_balance
        Useful when user wants to withdraw profits or stop trading
        """
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount <= 0:
            return Response(
                {'error': 'Amount must be greater than zero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            account = Account.objects.select_for_update().get(user=request.user)
            
            if account.status != Account.STATUS_ACTIVE:
                return Response(
                    {'error': f'Account is {account.status}. Transfers not allowed.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if user has open positions
            from trading.models import Position
            open_positions = Position.objects.filter(user=request.user)
            if open_positions.exists():
                # Calculate total margin used
                total_margin_used = sum(
                    (pos.quantity * pos.entry_price) / pos.leverage 
                    for pos in open_positions
                )
                
                available_to_transfer = account.trading_balance - Decimal(str(total_margin_used))
                
                if amount > available_to_transfer:
                    return Response(
                        {
                            'error': 'Cannot transfer funds. You have open positions.',
                            'trading_balance': str(account.trading_balance),
                            'margin_used': str(total_margin_used),
                            'available_to_transfer': str(available_to_transfer)
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if account.trading_balance < amount:
                return Response(
                    {
                        'error': 'Insufficient trading balance',
                        'required': str(amount),
                        'available': str(account.trading_balance)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Perform transfer
            account.trading_balance -= amount
            account.deposit_balance += amount
            account.save()
            
            logger.info(
                f"Balance transfer: User {request.user.id} transferred "
                f"${amount} from trading to deposit balance"
            )
            
            return Response({
                'message': 'Transfer successful',
                'amount_transferred': str(amount),
                'balances': {
                    'trading_balance': str(account.trading_balance),
                    'deposit_balance': str(account.deposit_balance),
                    'total_balance': str(account.total_balance),
                }
            }, status=status.HTTP_200_OK)
            
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Transfer failed for user {request.user.id}: {str(e)}")
            return Response(
                {'error': 'Transfer failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def transfer_limits(self, request):
        """
        Get available transfer limits based on current balances and open positions
        """
        try:
            account = Account.objects.get(user=request.user)
            
            # Calculate margin used in open positions
            from trading.models import Position
            open_positions = Position.objects.filter(user=request.user)
            
            total_margin_used = Decimal('0')
            if open_positions.exists():
                total_margin_used = sum(
                    (pos.quantity * pos.entry_price) / pos.leverage 
                    for pos in open_positions
                )
            
            available_to_transfer_from_trading = max(
                Decimal('0'),
                account.trading_balance - total_margin_used
            )
            
            return Response({
                'deposit_balance': str(account.deposit_balance),
                'trading_balance': str(account.trading_balance),
                'investment_balance': str(account.investment_balance),
                'limits': {
                    'can_transfer_to_trading': str(account.deposit_balance),
                    'can_transfer_to_investment': str(account.deposit_balance),
                    'can_transfer_from_trading': str(available_to_transfer_from_trading),
                    'margin_used_in_positions': str(total_margin_used),
                },
                'open_positions': open_positions.count()
            })
            
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
            
class ProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Profile management endpoints.
    Provides read operations by default (GET /profile/) and custom update actions.
    
    - GET /profile/ - Retrieve current user's profile
    - PATCH /profile/update/ - Update current user's profile
    - Custom actions for profile picture management and public profile access
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    def get_queryset(self):
        """
        Filter queryset to only show the current user.
        This is used by ReadOnlyModelViewSet's list/retrieve actions.
        """
        return User.objects.filter(id=self.request.user.id)

    def get_profile_object(self):
        """
        Helper method to fetch or create the profile for the current user.
        """
        profile, created = Profile.objects.get_or_create(
            user=self.request.user,
            defaults={
                'display_name': self.request.user.get_full_name() or self.request.user.username,
                'is_complete': False
            }
        )
        return profile
    
    # --- Update Action (since ReadOnlyModelViewSet doesn't include update) ---
    
    @action(detail=False, methods=['patch', 'put'], parser_classes=[MultiPartParser, FormParser, JSONParser])
    @transaction.atomic
    def update_profile(self, request):
        """
        PATCH/PUT /profile/update_profile/
        Updates the current user's profile and user information.
        """
        try:
            user = request.user
            profile = self.get_profile_object()
            
            # Use UserProfileUpdateSerializer for handling the update
            serializer = UserProfileUpdateSerializer(user, data=request.data, partial=True, context={'request': request})
            
            if not serializer.is_valid():
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save will handle both user and profile updates
            serializer.save()
            
            # Return full user profile data using UserProfileSerializer
            user_serializer = UserProfileSerializer(request.user)
            
            return Response({
                'message': 'Profile updated successfully',
                'data': user_serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            return Response(
                {'error': 'Failed to update profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
    # --- Custom Actions ---
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def get_by_username(self, request):
        """
        GET /profile/get_by_username/?username=<username>
        Get profile by username (public endpoint)
        """
        username = request.query_params.get('username')
        if not username:
            return Response(
                {'error': 'Username parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(username=username)
            profile = get_object_or_404(Profile, user=user)
            
            public_fields = ['id', 'display_name', 'bio', 'location', 'website', 'profile_picture']
            profile_data = {field: getattr(profile, field) for field in public_fields}
            
            user_data = {
                'username': user.username,
                'date_joined': user.date_joined,
                'is_verified': user.is_verified
            }
            
            return Response({
                'profile': profile_data,
                'user': user_data
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching profile by username: {e}")
            return Response(
                {'error': 'Failed to fetch profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    @transaction.atomic
    def upload_profile_picture(self, request):
        """
        POST /profile/upload_profile_picture/
        Upload profile picture
        """
        try:
            profile = self.get_profile_object() 
            profile_picture_file = request.FILES.get('profile_picture')
            
            if not profile_picture_file:
                # 💡 DRF standard error format for consistency
                return Response(
                    {'profile_picture': ['No profile picture file provided in the request.']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 1. Use the Serializer *only* for validation logic
            # We construct data from request.FILES, but we only need to validate the file field.
            # We pass it through the serializer's validation functions.
            validation_serializer = ProfileSerializer(
                profile, 
                data={'profile_picture': profile_picture_file}, 
                partial=True
            )
            
            if not validation_serializer.is_valid():
                # 💡 Returns the clean DRF error dictionary structure
                return Response(validation_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # 2. If validation passes, assign and save directly to the model
            profile.profile_picture = profile_picture_file
            profile.save()
            
            # 3. Success response
            picture_url = profile.profile_picture.url if profile.profile_picture else None
            
            return Response({
                'message': 'Profile picture uploaded successfully',
                'profile_picture_url': picture_url
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error uploading profile picture: {e}")
            return Response(
                {'error': 'Failed to upload profile picture due to a server error.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'])
    @transaction.atomic
    def delete_profile_picture(self, request):
        """
        DELETE /profile/delete_profile_picture/
        Remove profile picture
        """
        try:
            profile = self.get_profile_object()
            
            if not profile.profile_picture:
                return Response(
                    {'error': 'No profile picture to delete'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profile.profile_picture.delete(save=False)
            profile.profile_picture = None
            profile.save()
            
            return Response({
                'message': 'Profile picture deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deleting profile picture: {e}")
            return Response(
                {'error': 'Failed to delete profile picture'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )