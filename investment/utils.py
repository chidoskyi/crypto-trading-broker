from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db import transaction as db_transaction
from django.contrib.auth.models import User
from .models import (
    Investment, InvestmentPlan, InvestmentTransaction, InvestmentTransactions, 
    TransactionHistory, PaymentMethod
)
from users.models import Account
# from userauths.utils import (
#     send_deposit_notification, send_withdrawal_notification, 
#     send_reinvest_notification
# )
import logging

logger = logging.getLogger(__name__)


def _handle_reinvestment(user, account, amount, roi, currency, plan, investment):
    """
    ✅ Handle reinvestment transactions (AUTO-APPROVED)
    
    Args:
        user: User object
        account: Account object (should be locked with select_for_update)
        amount: Decimal - reinvestment amount
        roi: Decimal - expected ROI
        currency: str - currency code (e.g., 'USD')
        plan: InvestmentPlan object
        investment: Investment object (already created)
    
    Returns:
        Transaction object or None
    """
    try:
        with db_transaction.atomic():
            # ✅ Lock account to prevent race conditions
            account = Account.objects.select_for_update().get(id=account.id)
            
            # ✅ Validate sufficient balance
            if account.investment_balance < amount:
                logger.error(f"Insufficient balance for reinvestment: User {user.username}, Amount {amount}")
                raise ValueError("Insufficient balance for reinvestment")
            
            # ✅ Get or create BALANCE payment method
            payment_method, created = PaymentMethod.objects.get_or_create(
                code='BALANCE',
                defaults={
                    'name': 'Account Balance',
                    'is_active': True,
                    'min_amount': Decimal('0.00'),
                    'max_amount': Decimal('999999.99'),
                    'processing_time': 'Instant'
                }
            )
            
            now = timezone.now()
            
            # ✅ Deduct from available balance IMMEDIATELY
            account.investment_balance -= amount
            account.total_invested += amount
            account.last_investment = now
            account.save(update_fields=['investment_balance', 'total_invested', 'last_investment'])
            
            # ✅ Update active investments from database
            account.update_active_investments()
            
            # ✅ Create Transaction with CONFIRMED status (skip admin approval)
            transaction_obj = Transaction.objects.create(
                user=user,
                transaction_type=Transaction.REINVESTMENT,
                amount=amount,
                status='confirmed',  # ← AUTO-APPROVED
                confirmed=True,
                payment_method=payment_method,
                investment_plan=plan,
                wallet_used=f"{currency} Wallet (Balance)",
                description=f"Reinvestment in {plan.name} plan - Expected ROI: ${roi}"
            )
            
            # ✅ Create Transactions record (for history)
            Transactions.objects.create(
                user=user,
                transaction_type=Transaction.REINVESTMENT,
                amount=amount,
                status='confirmed',
                confirmed=True,
                payment_method=payment_method,
                investment_plan=plan,
                transactionid=transaction_obj.transactionid,
                timestamp=now,
                description=f"Reinvestment in {plan.name}"
            )
            
            # ✅ Create TransactionHistory record
            TransactionHistory.objects.create(
                user=user,
                transaction=transaction_obj,
                investment=investment,
                investment_plan=plan,
                transaction_type=Transaction.REINVESTMENT,
                status='confirmed',
                amount=amount,
                payment_method=payment_method,
                description=f"Reinvestment in {plan.name} - Expected ROI: ${roi}"
            )
            
            # ✅ Award referral commission (if applicable)
            try:
                from user.admin import TransactionAdmin
                admin_instance = TransactionAdmin(Transaction, None)
                admin_instance.award_referrer_on_investment(investment)
            except Exception as e:
                logger.error(f"Error awarding referral commission: {str(e)}")
            
            # ✅ Create notification
            Notification.create_notification(
                user=user,
                title="Reinvestment Successful",
                message=f"Your reinvestment of ${amount} in {plan.name} has been processed successfully. Expected ROI: ${roi}",
                notification_type='investment',
                link='/user/investments/'
            )
            
            logger.info(f"REINVESTMENT SUCCESS: User={user.username}, Amount=${amount}, Investment={investment.id}, Transaction={transaction_obj.transactionid}")
            
            return transaction_obj
            
    except Exception as e:
        logger.error(f"Error in _handle_reinvestment: {str(e)}")
        logger.exception(e)
        raise


def _handle_investment(user, amount, roi, payment_method, plan, investment):
    """
    ✅ Handle new deposit/investment transactions (PENDING ADMIN APPROVAL)
    
    Args:
        user: User object
        amount: Decimal - deposit amount
        roi: Decimal - expected ROI
        payment_method: PaymentMethod object
        plan: InvestmentPlan object
        investment: Investment object (already created with status='pending')
    
    Returns:
        Transaction object or None
    """
    try:
        with db_transaction.atomic():
            now = timezone.now()
            
            # ✅ Create Transaction with PENDING status (requires admin approval)
            transaction_obj = Transaction.objects.create(
                user=user,
                transaction_type=Transaction.DEPOSIT,
                amount=amount,
                status='pending',  # ← REQUIRES ADMIN APPROVAL
                confirmed=False,
                payment_method=payment_method,
                investment_plan=plan,
                wallet_used=payment_method.name,
                description=f"Deposit for investment in {plan.name} - Expected ROI: ${roi}"
            )
            
            # ✅ Create Transactions record (for tracking)
            Transactions.objects.create(
                user=user,
                transaction_type=Transaction.DEPOSIT,
                amount=amount,
                status='pending',
                confirmed=False,
                payment_method=payment_method,
                investment_plan=plan,
                transactionid=transaction_obj.transactionid,
                timestamp=now,
                description=f"Pending deposit for {plan.name}"
            )
            
            # ✅ Create TransactionHistory record
            TransactionHistory.objects.create(
                user=user,
                transaction=transaction_obj,
                investment=investment,
                investment_plan=plan,
                transaction_type=Transaction.DEPOSIT,
                status='pending',
                amount=amount,
                payment_method=payment_method,
                description=f"Pending deposit for {plan.name} - Expected ROI: ${roi}"
            )
            
            # ✅ Create notification
            Notification.create_notification(
                user=user,
                title="Investment Pending Approval",
                message=f"Your investment of ${amount} in {plan.name} is pending admin approval. Expected ROI: ${roi}",
                notification_type='investment',
                link='/user/investments/'
            )
            
            logger.info(f"NEW DEPOSIT PENDING: User={user.username}, Amount=${amount}, Investment={investment.id}, Transaction={transaction_obj.transactionid}")
            
            return transaction_obj
            
    except Exception as e:
        logger.error(f"Error in _handle_new_deposit: {str(e)}")
        logger.exception(e)
        raise


def handle_investment(request, account, form_data):
    """ 
    ✅ Main handler for both regular investments and reinvestments
    
    Args:
        request: HTTP request object
        account: User's Account object
        form_data: Dict with keys: amount, investment_type, payment_method_id, plan_id
    
    Returns:
        Tuple (success: bool, message: str)
    """
    try:
        # ========== VALIDATION ==========
        if not all([form_data.get('amount'), form_data.get('plan_id')]):
            return False, "Missing required investment details."

        # Parse amount
        amount_str = ''.join(c for c in form_data['amount'] if c.isdigit() or c == '.')
        is_reinvestment = form_data.get('investment_type') == 'reinvest'
        
        try:
            amount = Decimal(amount_str).quantize(Decimal('0.01'))
            if amount <= 0:
                return False, "Amount must be greater than zero."
        except (InvalidOperation, ValueError):
            return False, "Invalid amount format. Please enter a valid number."

        # Get investment plan
        try:
            selected_plan = InvestmentPlan.objects.get(id=form_data['plan_id'])
        except InvestmentPlan.DoesNotExist:
            return False, "Invalid investment plan selected."

        # Validate amount against plan limits
        if amount < selected_plan.min_investment or amount > selected_plan.max_investment:
            return False, f"Investment amount must be between ${selected_plan.min_investment} and ${selected_plan.max_investment}."

        # Get payment method
        try:
            if is_reinvestment:
                payment_method, _ = PaymentMethod.objects.get_or_create(
                    code='BALANCE',
                    defaults={
                        'name': 'Account Balance',
                        'is_active': True,
                        'min_amount': Decimal('0.00'),
                        'max_amount': Decimal('999999.99'),
                        'processing_time': 'Instant'
                    }
                )
            else:
                payment_method = PaymentMethod.objects.get(id=form_data['payment_method_id'])
        except (PaymentMethod.DoesNotExist, ValueError):
            return False, "Invalid payment method selected."

        # Validate reinvestment balance
        if is_reinvestment:
            # Refresh account from database
            account.refresh_from_db()
            if amount > account.available_balance:
                return False, f"Insufficient balance. Available: ${account.available_balance}, Requested: ${amount}"

        # ========== PROCESS INVESTMENT ==========
        with db_transaction.atomic():
            # ✅ Lock account to prevent concurrent modifications
            account = InvestmentAccount.objects.select_for_update().get(id=account.id)
            
            now = timezone.now()
            
            # ✅ Check for duplicate investments (within last 10 seconds)
            recent_duplicate = Investment.objects.filter(
                user=request.user,
                plan=selected_plan,
                amount=amount,
                start_date__gte=now - timezone.timedelta(seconds=10)
            ).exists()
            
            if recent_duplicate:
                logger.warning(f"DUPLICATE DETECTED: User={request.user.username}, Amount={amount}, Plan={selected_plan.name}")
                return False, "Duplicate investment detected. Please wait before trying again."

            # Calculate end date
            if selected_plan.duration_unit == InvestmentPlan.DURATION_UNIT_HOURS:
                end_date = now + timezone.timedelta(hours=selected_plan.duration)
            else:
                end_date = now + timezone.timedelta(days=selected_plan.duration)

            # ✅ Create Investment record
            investment = Investment.objects.create(
                user=request.user,
                plan=selected_plan,
                amount=amount,
                status='approved' if is_reinvestment else 'pending',
                is_reinvestment=is_reinvestment,
                is_running=is_reinvestment,  # Auto-start only reinvestments
                start_date=now,
                end_date=end_date
            )

            # Calculate ROI
            roi = investment.calculate_return()
            investment.roi = roi
            investment.save(update_fields=['roi'])

            # ✅ Route to appropriate handler
            try:
                if is_reinvestment:
                    transaction_obj = _handle_reinvestment(
                        user=request.user,
                        account=account,
                        amount=amount,
                        roi=roi,
                        currency='USD',  # Or get from form_data
                        plan=selected_plan,
                        investment=investment
                    )
                    
                    # Send email notification
                    send_reinvest_notification(
                        request.user, 
                        amount, 
                        payment_method.name, 
                        selected_plan
                    )
                    
                    return True, f"Reinvestment of ${amount} processed successfully! Expected ROI: ${roi}"
                    
                else:
                    transaction_obj = _handle_investment(
                        user=request.user,
                        amount=amount,
                        roi=roi,
                        payment_method=payment_method,
                        plan=selected_plan,
                        investment=investment
                    )
                    
                    # Send email notification
                    send_deposit_notification(
                        request.user, 
                        amount, 
                        payment_method.name, 
                        selected_plan
                    )
                    
                    return True, f"Investment of ${amount} submitted for approval. Expected ROI: ${roi}"
                    
            except ValueError as ve:
                logger.error(f"Validation error: {str(ve)}")
                return False, str(ve)
            except Exception as e:
                logger.error(f"Transaction creation error: {str(e)}")
                logger.exception(e)
                return False, "Error processing transaction. Please try again."

    except Exception as e:
        logger.error(f"Investment handling error: {str(e)}")
        logger.exception(e)
        return False, "An error occurred. Please contact support."


import secrets
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
import threading
from django.core.mail import send_mail





class EmailThread(threading.Thread):
    def __init__(self, email):
        self.email = email  # Ensure this is an EmailMultiAlternatives instance
        threading.Thread.__init__(self)

    def run(self):
        self.email.send(fail_silently=False)

def send_password_reset_email(user):
    email = user.email
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    
    # Construct the reset link with uid and token in query parameters
    reset_link = f"{settings.EMAIL_MESSAGE_URL}/userauths/reset/{uid}/{token}/"


    # Prepare email context
    context = {
        'username': user.username,
        'reset_link': reset_link,
    }

    # Render the email templates
    subject = 'Password Reset Request'
    text_content = render_to_string('emails/password_reset_request.txt', context)
    html_content = render_to_string('emails/password_reset_request.html', context)

    email_message = EmailMultiAlternatives(
        subject,
        text_content,
        settings.ADMIN_EMAIL,
        [email],
    )
    email_message.attach_alternative(html_content, "text/html")
    EmailThread(email_message).start()


def send_verification_email(user):
    email = user.email
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    
    # Save the token to the user's profile
    profile = user.profile
    profile.verification_token = token
    profile.save()
    
    # Construct the verification link with path parameters instead of query parameters
    verification_link = f"{settings.EMAIL_MESSAGE_URL}/userauths/verify-email/{uidb64}/{token}/"

    # Prepare email context
    context = {
        'username': user.username,
        'verification_link': verification_link,
    }

    # Render the email templates
    subject = 'Verify Your Email Address'
    text_content = render_to_string('emails/verify_email.txt', context)
    html_content = render_to_string('emails/verify_email.html', context)

    email_message = EmailMultiAlternatives(
        subject,
        text_content,
        settings.ADMIN_EMAIL,
        [email],
    )
    email_message.attach_alternative(html_content, "text/html")
    
    # Send the email asynchronously
    EmailThread(email_message).start()


# Function to send an email with the new password
def send_new_password_email(user, new_password):
    email = user.email

    # Prepare email context
    context = {
        'username': user.username,
        'new_password': new_password,
    }

    # Render the email templates
    subject = 'Your New Password'
    text_content = render_to_string('emails/new_password.txt', context)
    html_content = render_to_string('emails/new_password.html', context)

    email_message = EmailMultiAlternatives(
        subject,
        text_content,
        settings.ADMIN_EMAIL,
        [email],
    )
    email_message.attach_alternative(html_content, "text/html")

    # Start the email thread with the correct email_message
    EmailThread(email_message).start()

# Send Email Notification
def send_login_notification(username, ip):
    subject = "Admin Login"
    message = f"{username} entered your admin area IP = {ip}"
    
    # Debugging: Print the email message to the console
    print("Sending email with message: ", message)

    from_email = settings.ADMIN_EMAIL
    recipient_list = [settings.ADMIN_EMAIL]  # Admin email from settings

    # Attempt to send the email and log success/failure
    try:
        send_mail(subject, message, from_email, recipient_list)
        print(f"Email sent successfully to {recipient_list}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_deposit_notification(user, amount, payment_method, investment_plan):
    subject = 'Deposit Request Notification'
    duration_display = investment_plan.get_duration_display()
    message = (
        f'User {user.username} saved deposit ${amount:.2f} of {payment_method} '
        f'to {investment_plan.interest_rate}% after {duration_display}'
    )
    
    send_mail(
        subject,
        message,
        settings.ADMIN_EMAIL,  # From email
        [settings.ADMIN_EMAIL],  # To email - change this to the admin's email
        fail_silently=False,
    )
def send_reinvest_notification(user, amount, payment_method, investment_plan):
    subject = 'Reinvestment Notification'
    duration_display = investment_plan.get_duration_display()
    message = (
        f'User {user.username} reinvested ${amount:.2f} of {payment_method} '
        f'to {investment_plan.interest_rate}% after {duration_display}'
    )
    
    send_mail(
        subject,
        message,
        settings.ADMIN_EMAIL,  # From email
        [settings.ADMIN_EMAIL],  # To email - change this to the admin's email
        fail_silently=False,
    )


def send_withdrawal_notification(amount, username, ip):
    subject = 'Withdrawal Request has been sent'
    message = (
        f'User {username} requested to withdraw  ${amount:.2f} from IP {ip} '  
    )
    
    send_mail(
        subject,
        message,
        settings.ADMIN_EMAIL,  # From email
        [settings.ADMIN_EMAIL],  # To email - change this to the admin's email
        fail_silently=False,
    )
    
def send_withdrawal_notification_status(user, amount, username, status):
    """
    Send a notification to the user about the status of their withdrawal request.
    
    :param user: The user object.
    :param amount: The withdrawal amount.
    :param username: The username of the user.
    :param status: The status of the withdrawal (e.g., 'pending', 'rejected', 'confirmed').
    """
    email = user.email

    # Define a clean subject
    if status == 'pending':
        subject = 'We’ve received your withdrawal request'
    elif status == 'rejected':
        subject = 'Update on your recent withdrawal request'
    elif status == 'confirmed':
        subject = 'Your withdrawal has been processed'
    else:
        subject = 'Withdrawal request status update'

    # Clean message with less spammy formatting
    message = (
        f"Hi {username},\n\n"
        f"We wanted to let you know that your withdrawal request of ${amount:.2f} is currently marked as *{status}*.\n\n"
        f"If you have any questions or concerns, feel free to reach out to our support team.\n\n"
        f"Thank you for choosing VertexOption Global.\n\n"
        f"— The VertexOption Team"
    )

    # Send the email
    send_mail(
        subject,
        message,
        settings.ADMIN_EMAIL,  # From email
        [email],  # To email
        fail_silently=False,
    )

    
def send_referral_email(referrer, referee):
    """Send email notifications for referral events."""
    # Email to referrer
    referrer_subject = "Someone used your referral link!"
    referrer_message = render_to_string('emails/referral_used.html', {
        'referrer': referrer,
        'referee': referee,
    })
    
    send_mail(
        referrer_subject,
        referrer_message,
        settings.ADMIN_EMAIL,
        [referrer.email],
        html_message=referrer_message,
    )

    # Welcome email to referee
    referee_subject = "Welcome - Thanks for joining through a referral!"
    referee_message = render_to_string('emails/referee_welcome.html', {
        'referee': referee,
        'referrer': referrer,
    })
    
    send_mail(
        referee_subject,
        referee_message,
        settings.ADMIN_EMAIL,
        [referee.email],
        html_message=referee_message,
    )
