# referrals/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from referrals.models import ReferralReward, ReferralTier
from users.serializers import UserSerializer

User = get_user_model()

class ReferralViewSet(viewsets.ViewSet):
    """Referral program endpoints"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def code(self, request):
        """Get user's referral code"""
        return Response({
            'referral_code': request.user.referral_code,
            'referral_link': f'{request.build_absolute_uri("/register")}?ref={request.user.referral_code}'
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get referral statistics"""
        referred_users = User.objects.filter(referred_by=request.user)
        rewards = ReferralReward.objects.filter(referrer=request.user)
        
        total_rewards = sum(reward.amount for reward in rewards)
        
        return Response({
            'total_referrals': referred_users.count(),
            'active_referrals': referred_users.filter(is_active=True).count(),
            'total_rewards': total_rewards,
            'pending_rewards': rewards.filter(
                transaction__isnull=True
            ).count()
        })
    
    @action(detail=False, methods=['get'])
    def rewards(self, request):
        """Get referral rewards"""
        rewards = ReferralReward.objects.filter(
            referrer=request.user
        ).order_by('-created_at')
        
        return Response([{
            'id': reward.id,
            'referred_user': reward.referred_user.username,
            'reward_type': reward.reward_type,
            'amount': reward.amount,
            'currency': reward.currency,
            'status': 'paid' if reward.transaction else 'pending',
            'created_at': reward.created_at
        } for reward in rewards])
    
    @action(detail=False, methods=['get'])
    def referred_users(self, request):
        """List referred users"""
        referred_users = User.objects.filter(referred_by=request.user)
        
        return Response([{
            'username': user.username,
            'email': user.email,
            'is_verified': user.is_verified,
            'created_at': user.created_at,
            'total_trades': user.order_set.filter(status='filled').count()
        } for user in referred_users])