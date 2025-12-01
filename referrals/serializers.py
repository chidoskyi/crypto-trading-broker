# referrals/serializers.py (MISSING - CREATE THIS FILE)
from rest_framework import serializers
from referrals.models import ReferralReward, ReferralTier
from users.serializers import UserSerializer

class ReferralTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralTier
        fields = ['id', 'name', 'min_referrals', 'commission_percentage', 
                  'bonus_amount', 'created_at']

class ReferralRewardSerializer(serializers.ModelSerializer):
    referrer_info = UserSerializer(source='referrer', read_only=True)
    referred_user_info = UserSerializer(source='referred_user', read_only=True)
    
    class Meta:
        model = ReferralReward
        fields = ['id', 'referrer', 'referrer_info', 'referred_user', 
                  'referred_user_info', 'reward_type', 'amount', 'currency',
                  'transaction', 'created_at']
        read_only_fields = ['id', 'created_at']