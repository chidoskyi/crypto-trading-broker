# referrals/models.py
from django.db import models

class ReferralTier(models.Model):
    """Referral reward tiers"""
    name = models.CharField(max_length=100)
    min_referrals = models.IntegerField()
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferralReward(models.Model):
    """Track referral rewards"""
    referrer = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_rewards'
    )
    referred_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='referral_source'
    )
    reward_type = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'Signup Bonus'),
            ('first_deposit', 'First Deposit Bonus'),
            ('trading_commission', 'Trading Commission')
        ]
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    transaction = models.ForeignKey(
        'funds.Transaction',
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)