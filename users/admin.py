# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from users.models import Profile, User, KYCDocument, Country

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'is_verified', 'kyc_status', 'created_at', 'is_active', 'is_staff', 'first_name', 'last_name']  # FIXED: Added first_name and last_name for better identification
    list_filter = ['is_verified', 'kyc_status', 'is_staff', 'is_active']  # FIXED: Now these are actual fields
    search_fields = ['email', 'username', 'referral_code']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    # FIXED: Use proper fieldsets structure
    fieldsets = (
        (None, {'fields': ('first_name', 'last_name','email', 'username', 'password')}),
        ('Personal Info', {'fields': ('phone_number', 'country')}),
        ('Verification Status', {'fields': ('is_verified', 'kyc_status')}),
        ('Referral Info', {'fields': ('referral_code', 'referred_by')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )

@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'document_type', 'submitted_at', 'reviewed_at', 'reviewed_by']
    list_filter = ['document_type', 'user__kyc_status']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['submitted_at']

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'iso', 'phone_code']
    search_fields = ['name', 'iso']
    
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'bio', 'location', 'website', 'created_at']
    search_fields = ['user__email', 'user__username', 'bio', 'location', 'website']
    readonly_fields = ['created_at']
    ordering = ['-created_at']