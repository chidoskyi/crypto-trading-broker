# loans/models.py
from django.db import models
from decimal import Decimal

class LoanProduct(models.Model):
    """Available loan products"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Annual %
    term_days = models.IntegerField()
    collateral_ratio = models.DecimalField(max_digits=5, decimal_places=2)  # %
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    """User loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_days = models.IntegerField()
    collateral_amount = models.DecimalField(max_digits=20, decimal_places=2)
    collateral_currency = models.CharField(max_length=10)
    outstanding_balance = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_loans'
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    repaid_at = models.DateTimeField(null=True, blank=True)

class LoanRepayment(models.Model):
    """Loan repayment transactions"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.ForeignKey('funds.Transaction', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)