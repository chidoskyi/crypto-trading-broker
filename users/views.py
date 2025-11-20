# users/views.py
import uuid
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
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
    CustomTokenObtainPairSerializer, ProfileCompletionSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer, ProfileSerializer, UserProfileSerializer, UserSerializer, UserRegistrationSerializer, KYCDocumentSerializer
)
from django.db import transaction
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from users.models import KYCDocument, Profile
import random
import string


User = get_user_model()

import random
import string

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
    """Get list of all countries"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from .models import Country
        
        countries = Country.objects.all().order_by('name')
        country_list = [
            {'id': country.id, 'name': country.name} 
            for country in countries
        ]
        
        return Response({
            'countries': country_list,
            'count': len(country_list)
        }, status=status.HTTP_200_OK)
    
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