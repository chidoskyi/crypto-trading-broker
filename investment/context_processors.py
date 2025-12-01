# from .models import Account
from decimal import Decimal
from django.db.models import Sum
from user.models import Account, Transaction, TransactionHistory
from userauths.models import Profilez as Profile


def user_balances(request):
    if request.user.is_authenticated:
        try:
            account = Account.objects.get(user=request.user)
            return {
                'total_balance': account.total_balance,
                'total_withdrawals': account.total_withdrawals,
                'total_deposits': account.total_deposits,
                'available_balance': account.available_balance,
                'invested_balance': account.invested_balance,
                'total_earned': account.total_earned,
                'active_investments': account.active_investments
            }
        except Account.DoesNotExist:
            return {
                'total_balance': Decimal('0.00'),
                'total_withdrawals': Decimal('0.00'),
                'total_deposits': Decimal('0.00'),
                'available_balance': Decimal('0.00'),
                'invested_balance': Decimal('0.00'),
                'total_earned': Decimal('0.00'),
                'active_investments': Decimal('0.00')
            }
    return {}

def deposit_history_context(request):
    """Context processor to include user deposit history details."""
    deposits = []
    transaction_type = ''
    ec = '-1'
    total_amount = 0

    if request.user.is_authenticated:
        # Handle filtering logic for the authenticated user
        # Start with the base query
        deposits = TransactionHistory.objects.filter(
            user=request.user,
            transaction__status='confirmed'
        ).order_by('-created_at')

        # Calculate total amount without any filtering
        total_amount = deposits.aggregate(Sum('amount'))['amount__sum'] or 0

    return {
        'deposits': deposits,
        'transaction_type': transaction_type,
        'ec': ec,
        'total_amount': total_amount,
    }
    
def pending_withdrawal(request):
    if request.user.is_authenticated:
        # Calculate the total pending withdrawal for the logged-in user
        total_pending_withdrawal = Transaction.objects.filter(
            user=request.user,
            transaction_type=Transaction.WITHDRAWAL,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        return {
            'total_pending_withdrawal': total_pending_withdrawal,
        }
    return {}

def profile_context(request):
    """
    Adds the user's profile to the template context.
    """
    context = {}
    if request.user.is_authenticated:
        try:
            profile = Profile.objects.get(user=request.user)
            context['profile'] = profile
        except Profile.DoesNotExist:
            # Handle the case where the profile does not exist
            context['profile'] = None
    else:
        context['profile'] = None
    return context

from django.conf import settings

def email_context(request):
    return {
        "admin_email": settings.ADMIN_EMAIL,
        "site_name": settings.SITE_NAME,
        "site_url": settings.EMAIL_MESSAGE_URL
    }

