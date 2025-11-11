# loans/admin.py
from django.contrib import admin
from loans.models import LoanProduct, Loan, LoanRepayment

@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'min_amount', 'max_amount', 'interest_rate', 
                   'term_days', 'is_active']
    list_filter = ['is_active']

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'outstanding_balance', 
                   'status', 'applied_at', 'due_date']
    list_filter = ['status', 'applied_at']
    search_fields = ['user__email']
    readonly_fields = ['applied_at', 'approved_at', 'disbursed_at']
    
    actions = ['approve_loans', 'reject_loans']
    
    def approve_loans(self, request, queryset):
        for loan in queryset.filter(status='pending'):
            # Call the approve logic
            pass
    approve_loans.short_description = "Approve selected loans"
    
    def reject_loans(self, request, queryset):
        for loan in queryset.filter(status='pending'):
            # Call the reject logic
            pass
    reject_loans.short_description = "Reject selected loans"

@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ['loan', 'amount', 'principal_amount', 
                   'interest_amount', 'created_at']
    list_filter = ['created_at']
    search_fields = ['loan__user__email']