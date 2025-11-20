# users/models.py
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from encrypted_fields.fields import EncryptedCharField


class Country(models.Model):
    name = models.CharField(max_length=100)
    iso = models.CharField(max_length=3, unique=True)
    phone_code = models.CharField(max_length=10)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (+{self.phone_code})"


class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """Extended user model with trading platform features"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    username = models.CharField(_('username'), max_length=150, unique=True)  # ADD THIS
    first_name = models.CharField(_('first name'), max_length=150) 
    last_name = models.CharField(_('last name'), max_length=150) 
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    country = models.ForeignKey('Country', on_delete=models.SET_NULL, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('not_submitted', 'Not Submitted')
        ],
        default='not_submitted'
    )
    referral_code = models.CharField(max_length=10, unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    
    # FIX: Remove default=timezone.now since auto_now_add is present
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ADD THREE REQUIRED FIELDS FOR AbstractBaseUser
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
    
    def get_profile(self):
        """Safely get or create user profile"""
        from users.models import Profile
        profile, created = Profile.objects.get_or_create(user=self)
        return profile
    

class KYCDocument(models.Model):
    """Store KYC verification documents"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('passport', 'Passport'),
            ('drivers_license', 'Driver\'s License'),
            ('national_id', 'National ID')
        ]
    )
    document_number = EncryptedCharField(max_length=100)
    document_front = models.FileField(upload_to='kyc/documents/')
    document_back = models.FileField(upload_to='kyc/documents/', null=True)
    selfie = models.FileField(upload_to='kyc/selfies/')
    address_proof = models.FileField(upload_to='kyc/address/')
    date_of_birth = models.DateField()
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kyc_reviews'
    )
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f"KYC Document for {self.user.email} - {self.document_type}"

class Profile(models.Model):
    """User profile model"""
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        unique=True
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    kyc = models.OneToOneField(KYCDocument, on_delete=models.SET_NULL, null=True, blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        help_text="User profile picture"
    )
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
    
    def __str__(self):
        return f"{self.user.email}'s Profile"

    @property
    def is_complete(self):
        """Check if profile has required fields filled"""
        return bool(self.bio and self.location)