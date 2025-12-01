# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from users.models import Profile, User, KYCDocument, Country, Account

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
class ProfileAdmin(ModelAdmin):
    list_display = ['user', 'bio', 'location', 'website', 'created_at']
    search_fields = ['user__email', 'user__username', 'bio', 'location', 'website']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
admin.site.register(Account)
class AccountAdmin(ModelAdmin):
    # List Display
    list_display = (
        'user',
        'available_balance',
        'total_earned',
        'status',
        'created_at',
        'last_login',
        'account_actions',
        'active_investments'
    )
    
    # Search Fields
    search_fields = (
        'user__username',
        'user__email',
        'status',
    )
    
    # List Filter
    list_filter = (
        'status',
        'created_at',
        'last_login',
    )
    
    # Editable Fields in List View
    list_editable = (
        'status',
    )
    
    # Fieldsets for Detail View
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'status', 'created_at', 'updated_at', 'last_login'),
        }),
        ('Balances', {
            'fields': (
                'available_balance',
            ),
        }),
        ('Investment Statistics', {
            'fields': (
                'active_investments',
                'total_earned',
            ),
        }),
        ('Transaction Statistics', {
            'fields': (
                'total_deposits',
                'total_withdrawals',
                'pending_withdrawals',
            ),
        }),
        ('Referral System', {
            'fields': (
                'referral_balance',
                'total_referral_earnings',
            ),
        }),
        ('Withdrawal Limits', {
            'fields': (
                'withdrawal_limit',
                'daily_withdrawal_limit',
            ),
        }),
        ('Timestamps', {
            'fields': (
                'last_investment',
                'last_withdrawal',
            ),
        }),
    )
    
    # Read-Only Fields
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_login',
        'last_investment',
        'last_withdrawal',
    )
    exclude = ('invested_balance', 'pending_balance', 'total_invested')
    
    # Custom Actions
    actions = ['activate_accounts', 'suspend_accounts']
    
    def activate_accounts(self, request, queryset):
        queryset.update(status=Account.STATUS_ACTIVE)
    activate_accounts.short_description = "Activate selected accounts"
    
    def suspend_accounts(self, request, queryset):
        queryset.update(status=Account.STATUS_SUSPENDED)
    suspend_accounts.short_description = "Suspend selected accounts"
    
    # Custom Method for Admin Actions
    def account_actions(self, obj):
        return format_html(
            '<a class="button" href="{}">View</a>&nbsp;'
            '<a class="button" href="{}">Edit</a>',
            f'/admin/users/account/{obj.id}/',
            f'/admin/users/account/{obj.id}/change/',
        )
    account_actions.short_description = 'Actions'
    account_actions.allow_tags = True

