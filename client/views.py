from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime
from trading.models import TradingPair, Transaction



def index(request):
    return render(request, 'client/index.html')
def about(request):
    return render(request, 'client/about.html') 
def leader(request):
    return render(request, 'client/leaders.html')
def market(request):
    return render(request, 'client/markets.html')
def become_leader(request):
    return render(request, 'client/become-a-leader.html')
def support(request):
    return render(request, 'client/support.html')
def calender(request):
    return render(request, 'client/calendar.html')
def partnerships_program(request):
    return render(request, 'client/partnership-program.html')
def user_guide(request):
    return render(request, 'client/user-guide.html')
def help_center(request):
    return render(request, 'client/help-center.html')
def leader_guide(request):
    return render(request, 'client/leader-guide.html')
def privacy_policy(request):
    return render(request, 'client/privacy-policy.html')
def cookies_policy(request):
    return render(request, 'client/cookies-policy.html')
def risk_disclaimer(request):
    return render(request, 'client/risk-disclaimer.html')
def autoprotect(request):
    return render(request, 'client/autoprotect.html')
def affiliate_guide(request):
    return render(request, 'client/affiliate-guide.html')
def become_leader(request):
    return render(request, 'client/become-a-leader.html')
def become_affiliate(request):
    return render(request, 'client/become-an-affiliate.html')
def login(request):
    return render(request, 'client/login.html')
def register(request):
    return render(request, 'client/register.html')
def complete_profile(request):
    return render(request, 'client/complete-profile.html')
def password_reset_request(request):
    return render(request, 'client/forgot-password.html')
def password_reset(request, uidb64, token):
    context = { 'uidb64': uidb64, 'token': token }
    return render(request, 'client/password-reset.html', context)
def dashboard(request):
    return render(request, 'user-dashboard/dashboard.html')
def buy_plan(request):
    return render(request, 'user-dashboard/buy-plan.html')
def account_history(request):
    return render(request, 'user-dashboard/account-history.html')
def portfolio(request):
    return render(request, 'user-dashboard/portfolio.html')
def trading_history(request):
    return render(request, 'user-dashboard/trading-history.html')
def trading(request):
    return render(request, 'user-dashboard/trade.html')
def trading_view2(request):
    return render(request, 'user-dashboard/trading-view2.html')

def trading_view(request, pairId):
    trading_pair = get_object_or_404(TradingPair, id=pairId)
    context = {
        'pair_id': pairId,  # Make sure this is here!
        # other context variables...
    }
    return render(request, 'user-dashboard/trading-view.html', context)

def copy_trading(request):
    return render(request, 'user-dashboard/copy-trading.html')
def copy_trade_experts(request):
    return render(request, 'user-dashboard/copy-trade-experts.html')
def bot_trading(request):
    return render(request, 'user-dashboard/bot-trading.html')
def signal(request):
    return render(request, 'user-dashboard/signal.html')
def withdrawals(request):
    return render(request, 'user-dashboard/withdrawals.html')
def transfer_funds(request):
    return render(request, 'user-dashboard/transfer-funds.html')
def loans(request):
    return render(request, 'user-dashboard/loan.html')
def loan_history(request):
    return render(request, 'user-dashboard/view-loan.html')
def support(request):
    return render(request, 'user-dashboard/support.html')
def account_settings(request):
    return render(request, 'user-dashboard/account-settings.html')
def refer_user(request):
    return render(request, 'user-dashboard/refer-user.html')
def verify_account(request):
    return render(request, 'user-dashboard/verify-account.html')
def kyc_form(request):
    return render(request, 'user-dashboard/kyc-form.html')
def notifications(request):
    return render(request, 'user-dashboard/notifications.html')
def connect_wallet(request):
    return render(request, 'user-dashboard/connect-wallet.html')

def deposits(request):
    """Step 1: Deposit form - store in session and render"""
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        amount = request.POST.get('amount')
        
        print(f"DEBUG - Received: payment_method={payment_method}, amount={amount}")  # Debug line
        
        if not payment_method or not amount:
            messages.error(request, 'Please fill in all required fields')
            return render(request, 'user-dashboard/deposits.html')
        
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                messages.error(request, 'Amount must be greater than 0')
                return render(request, 'user-dashboard/deposits.html')
        except ValueError:
            messages.error(request, 'Invalid amount')
            return render(request, 'user-dashboard/deposits.html')
        
        # Store in Django session with timestamp
        request.session['deposit_payment_method'] = payment_method
        request.session['deposit_amount'] = amount
        request.session['deposit_time'] = timezone.now().isoformat()  # Add timestamp
        request.session.modified = True
        
        print(f"DEBUG - Stored in session: {request.session.get('deposit_payment_method')}, {request.session.get('deposit_amount')}, time: {request.session.get('deposit_time')}")
        
        return redirect('payments')
    
    return render(request, 'user-dashboard/deposits.html')

def payments(request):
    """Step 2: Payment page - get data from session with expiration"""
    
    # Get data from session
    selected_crypto = request.session.get('deposit_payment_method')
    amount = request.session.get('deposit_amount')
    deposit_time_str = request.session.get('deposit_time')
    
    print(f"[PAYMENTS VIEW] Session data: crypto={selected_crypto}, amount={amount}, time={deposit_time_str}")
    
    # Check if session data exists
    if not selected_crypto or not amount or not deposit_time_str:
        messages.warning(request, 'Please complete the deposit form first')
        return redirect('deposits')
    
    # Check if session data is expired (older than 1 hour)
    try:
        # Parse the stored timestamp
        if isinstance(deposit_time_str, str):
            deposit_time = datetime.fromisoformat(deposit_time_str)
        else:
            # If it's already a datetime object (shouldn't happen with JSON serialization)
            deposit_time = deposit_time_str
        
        # Calculate time difference
        time_diff = timezone.now() - deposit_time
        
        if time_diff > timedelta(hours=1):
            # Clear expired session data
            session_keys_to_remove = [
                'deposit_payment_method', 
                'deposit_amount', 
                'deposit_time'
            ]
            
            for key in session_keys_to_remove:
                if key in request.session:
                    del request.session[key]
            
            request.session.modified = True
            
            messages.warning(request, 'Your deposit session has expired. Please start over.')
            return redirect('deposits')
            
    except (ValueError, TypeError) as e:
        print(f"Error parsing session timestamp: {e}")
        # If there's an error parsing the timestamp, clear the session
        session_keys_to_remove = [
            'deposit_payment_method', 
            'deposit_amount', 
            'deposit_time'
        ]
        
        for key in session_keys_to_remove:
            if key in request.session:
                del request.session[key]
        
        request.session.modified = True
        
        messages.warning(request, 'Invalid session data. Please start over.')
        return redirect('deposits')
    
    # Normalize crypto code (in case full name was stored)
    crypto_mapping = {
        'bitcoin': 'BTC',
        'ethereum': 'ETH',
        'tether': 'USDT',
        'usdt': 'USDT',
        'litecoin': 'LTC',
        'binance coin': 'BNB',
        'bnb': 'BNB',
    }
    
    # Convert to uppercase and map if needed
    selected_crypto_normalized = crypto_mapping.get(
        selected_crypto.lower(), 
        selected_crypto.upper()
    )
    
    context = {
        'selected_crypto': selected_crypto_normalized,
        'amount': amount,
    }
    
    return render(request, 'user-dashboard/payments.html', context)


def deposit_success(request):
    return render(request, 'user-dashboard/deposit-success.html')

def join_investment(request):
    return render(request, 'user-dashboard/join-investment.html')

def investment_history(request):
    return render(request, 'user-dashboard/investment-history.html')

def transactions(request):
    return render(request, 'user-dashboard/transactions.html')

def transaction_details(request, transaction_id):
    transaction = Transaction.objects.get(id=transaction_id)
    return render(request, 'user-dashboard/transaction-details.html', {'transaction': transaction})
