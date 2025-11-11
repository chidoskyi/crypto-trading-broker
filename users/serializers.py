# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import Profile, User, KYCDocument

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

        # Get full user data using UserSerializer
        user_data = UserSerializer(user).data
        print(f"UserSerializer data: {user_data}")  # Debug line
        print(f"Type: {type(user_data)}")  # Debug line

        data = {
            'user': user_data,  # Full user object
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }
        
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    referred_by_code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password_confirm', 
                  'first_name', 'last_name', 'phone_number', 'referred_by_code']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        referred_by_code = validated_data.pop('referred_by_code', None)
        
        # Generate unique referral code
        import random
        import string
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Handle referral
        referred_by = None
        if referred_by_code:
            try:
                referred_by = User.objects.get(referral_code=referred_by_code)
            except User.DoesNotExist:
                pass
        
        user = User.objects.create_user(
            **validated_data,
            referral_code=referral_code,
            referred_by=referred_by
        )
        
        return user

class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ['id', 'document_type', 'document_number', 'document_front',
                  'document_back', 'selfie', 'address_proof', 'date_of_birth',
                  'address', 'city', 'country', 'postal_code', 'submitted_at',
                  'rejection_reason']
        read_only_fields = ['id', 'submitted_at', 'rejection_reason']



class ProfileSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'bio', 'website', 'location', 'phone', 
            'profile_picture', 'gender', 'birthday'
        ]