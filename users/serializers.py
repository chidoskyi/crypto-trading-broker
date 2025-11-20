# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import Country, Profile, User, KYCDocument
import random
import string
from django.core.cache import cache


class CountrySerializer(serializers.ModelSerializer):
    """Serializer for Country model"""
    class Meta:
        model = Country
        fields = ['id', 'name', 'iso', 'phone_code']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 
                  'phone_number', 'is_verified', 'kyc_status', 'referral_code',
                  'created_at']
        read_only_fields = ['id', 'is_verified', 'kyc_status', 'referral_code', 
                           'created_at']
        

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer that accepts username or email"""
    username_field = 'login'  # Changed from 'username'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the default username field and add our custom login field
        self.fields['login'] = serializers.CharField()
        self.fields.pop('username', None)
    
    def validate(self, attrs):
        # Get the login credential (can be username or email)
        login = attrs.get('login')
        password = attrs.get('password')
        remember = attrs.get('remember', False)
        
        # Try to find user by username or email
        user = None
        if '@' in login:
            # Looks like an email
            try:
                user = User.objects.get(email=login)
            except User.DoesNotExist:
                pass
        else:
            # Looks like a username
            try:
                user = User.objects.get(username=login)
            except User.DoesNotExist:
                pass
        
        if user is None:
            raise serializers.ValidationError('No account found with these credentials')
        
        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials')
        
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        
        # Generate tokens using the parent class logic
        refresh = self.get_token(user)

        if remember:
            # Extend refresh token to 30 days if remember me is checked
            from datetime import timedelta
            refresh.set_exp(lifetime=timedelta(days=30))

                    # Update last login
        from django.utils import timezone
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Get full user data using UserSerializer
        user_data = UserSerializer(user).data
        print(f"UserSerializer data: {user_data}")  # Debug line
        print(f"Type: {type(user_data)}")  # Debug line

        data = {
            'success': True,
            'user': user_data,  # Full user object
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }
        
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirmation = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    # Accept country as string (name) instead of ID
    country = serializers.CharField(required=True, write_only=True)
    country_details = CountrySerializer(source='country', read_only=True)
    
    # CAPTCHA fields
    captcha_key = serializers.CharField(write_only=True)
    captcha_value = serializers.CharField(write_only=True)
    
    # Optional referral code
    referred_by_code = serializers.CharField(
        required=False, 
        allow_blank=True,
        write_only=True
    )
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'password_confirmation',
            'first_name', 'last_name', 'phone_number', 'country', 
            'country_details', 'referred_by_code', 'referral_code',
            'captcha_key', 'captcha_value', 'is_verified', 'kyc_status'
        ]
        read_only_fields = ['id', 'referral_code', 'is_verified', 'kyc_status']
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': False},
            'phone_number': {'required': True},
        }
    
    def validate_email(self, value):
        """Check if email already exists"""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email address is already registered. Please use a different email or login."
            )
        return value.lower()
    
    def validate_username(self, value):
        """Check if username already exists and meets requirements"""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken. Please choose another one."
            )
        
        if len(value) < 3:
            raise serializers.ValidationError(
                "Username must be at least 3 characters long."
            )
        
        # Check for valid characters (alphanumeric and underscore)
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, and underscores."
            )
        
        return value.lower()
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        
        # Remove common separators
        cleaned = value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
        
        if len(cleaned) < 10:
            raise serializers.ValidationError(
                "Please enter a valid phone number with at least 10 digits."
            )
        
        # Check if phone already exists
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "This phone number is already registered."
            )
        
        return value
    
    def validate_country(self, value):
        """Validate and find country by name"""
        if not value or value == 'Select your country':
            raise serializers.ValidationError("Please select your country.")
        
        try:
            # Try exact match first
            country = Country.objects.get(name__iexact=value)
            return country
        except Country.DoesNotExist:
            # Try partial match
            country = Country.objects.filter(name__icontains=value).first()
            if country:
                return country
            
            raise serializers.ValidationError(
                f"Country '{value}' not found. Please select from the dropdown."
            )
    
    def validate(self, attrs):
        """Cross-field validation"""
        
        # Password confirmation validation
        password = attrs.get('password')
        password_confirmation = attrs.get('password_confirmation')
        
        if password != password_confirmation:
            raise serializers.ValidationError({
                "password_confirmation": "Passwords don't match. Please try again."
            })
        
        # Password strength validation (additional to Django's validators)
        if len(password) < 8:
            raise serializers.ValidationError({
                "password": "Password must be at least 8 characters long."
            })
        
        # CAPTCHA validation
        captcha_key = attrs.get('captcha_key')
        captcha_value = attrs.get('captcha_value')
        
        if not captcha_key or not captcha_value:
            raise serializers.ValidationError({
                "captcha": "Security verification is required."
            })
        
        # Validate CAPTCHA from cache
        stored_captcha = cache.get(f'captcha_{captcha_key}')
        
        if not stored_captcha:
            raise serializers.ValidationError({
                "captcha": "Security code has expired. Please refresh and try again."
            })
        
        if stored_captcha.upper() != captcha_value.upper().strip():
            raise serializers.ValidationError({
                "captcha": "Invalid security code. Please check and try again."
            })
        
        # Clean up used CAPTCHA
        cache.delete(f'captcha_{captcha_key}')
        
        return attrs
    
    def create(self, validated_data):
        """Create user with all provided data"""
        
        # Remove write-only fields
        validated_data.pop('password_confirmation')
        validated_data.pop('captcha_key')
        validated_data.pop('captcha_value')
        
        # Extract country object (already validated and converted)
        country = validated_data.pop('country')
        
        # Extract optional referral code
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        # Generate unique 8-character referral code
        referral_code = self.generate_unique_referral_code()
        
        # Handle referral relationship
        referred_by = None
        if referred_by_code:
            try:
                referred_by = User.objects.get(referral_code=referred_by_code)
            except User.DoesNotExist:
                # Silently ignore invalid referral codes
                pass
        
        # Extract password before creating user
        password = validated_data.pop('password')
        
        # Create user with all data
        user = User.objects.create(
            **validated_data,
            country=country,
            referral_code=referral_code,
            referred_by=referred_by,
            is_active=True,  # User can login immediately
            is_verified=False,  # Email not verified yet
            kyc_status='not_submitted'  # Default KYC status
        )
        
        # Set password (this hashes it properly)
        user.set_password(password)
        user.save()
        
        return user
    
    def generate_unique_referral_code(self):
        """Generate a unique 8-character referral code"""
        while True:
            # Generate code with uppercase letters and digits
            code = ''.join(random.choices(
                string.ascii_uppercase + string.digits, 
                k=8
            ))
            
            # Check if it's unique
            if not User.objects.filter(referral_code=code).exists():
                return code
            
class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ['id', 'document_type', 'document_number', 'document_front',
                  'document_back', 'selfie', 'address_proof', 'date_of_birth',
                  'address', 'city', 'country', 'postal_code', 'submitted_at',
                  'rejection_reason']
        read_only_fields = ['id', 'submitted_at', 'rejection_reason']



class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user_email', 'user_name', 'bio', 'location', 
            'website', 'profile_picture', 'is_complete',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_email', 'user_name', 'created_at', 'updated_at', 'is_complete']
    
    def get_user_name(self, obj):
        """Get user's full name"""
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    
    def validate_bio(self, value):
        """Validate bio length"""
        if value and len(value) < 10:
            raise serializers.ValidationError("Bio must be at least 10 characters long.")
        return value
    
    def validate_website(self, value):
        """Validate website URL format"""
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Website must start with http:// or https://")
        return value
    
    def validate_profile_picture(self, value):
        """Validate profile picture size and format"""
        if value:
            # Check file size (max 2MB)
            if value.size > 2 * 1024 * 1024:
                raise serializers.ValidationError("Profile picture must be less than 2MB.")
            
            # Check file format
            allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if value.content_type not in allowed_formats:
                raise serializers.ValidationError(
                    "Profile picture must be in JPEG, PNG, or GIF format."
                )
        
        return value

class ProfileCompletionSerializer(serializers.ModelSerializer):
    """Serializer specifically for profile completion after registration"""
    
    class Meta:
        model = Profile
        fields = ['bio', 'location', 'website', 'profile_picture']
    
    def validate(self, attrs):
        """Ensure required fields for profile completion are present"""
        if not attrs.get('bio'):
            raise serializers.ValidationError({
                "bio": "Bio is required to complete your profile."
            })
        
        if not attrs.get('location'):
            raise serializers.ValidationError({
                "location": "Location is required to complete your profile."
            })
        
        return attrs
    
    def validate_bio(self, value):
        """Validate bio length"""
        if len(value) < 10:
            raise serializers.ValidationError("Bio must be at least 10 characters long.")
        return value   


class UserProfileSerializer(serializers.ModelSerializer):
    """Extended user profile with country details"""
    country = CountrySerializer(read_only=True)
    referred_users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'country', 'referral_code', 
            'referred_users_count', 'is_verified', 'kyc_status',
            'date_joined', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'referral_code', 'date_joined']
    
    def get_referred_users_count(self, obj):
        """Get count of users referred by this user"""
        return obj.referrals.count()
    

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        # Just clean the email, let EmailField handle validation
        return value.lower().strip()

class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True, 
        required=True,
        min_length=8,
        error_messages={
            'min_length': 'Password must be at least 8 characters long.'
        }
    )
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        
        # Validate password strength
        try:
            validate_password(new_password)
        except Exception as e:
            raise serializers.ValidationError({
                'new_password': list(e.messages)
            })
        
        return attrs