from django.core.mail import send_mail, EmailMultiAlternatives
from users.models import Profile, Account
from .models import Investment
from django.template.loader import render_to_string
from django.conf import settings
import threading
from decimal import Decimal

import logging

# Set up logging
logger = logging.getLogger(__name__)    





class EmailThread(threading.Thread):
    def __init__(self, email):
        self.email = email
        threading.Thread.__init__(self)
        
    def run(self):
        self.email.send(fail_silently=False)

def send_welcome_email(user):
    # Retrieve the associated Profilez object
    profile = Profile.objects.get(user=user)
    
    # Using an f-string
    email_url = f"{settings.EMAIL_MESSAGE_URL}/userauths/login"


    # Prepare context for rendering the template
    context = {
        'username': user.username,
        'password': profile.password,  # Use plain text password from Profilez
        'email_url': email_url
    }

    # Render the email templates
    subject = 'Registration Info'
    text_content = render_to_string('emails/welcome_email.txt', context)  # Plain text email
    html_content = render_to_string('emails/welcome_email.html', context)  # HTML email
    recipient_email = user.email

    # Create the email message with both plain text and HTML versions
    email = EmailMultiAlternatives(
        subject,
        text_content,
        settings.ADMIN_EMAIL,
        [recipient_email]
    )
    email.attach_alternative(html_content, "text/html")

    # Start the email thread to send the email
    EmailThread(email).start()
    
from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import Profile, Referral
from .models import Investment

@receiver(post_save, sender=Profile)
def create_referral_code(sender, instance, created, **kwargs):
    if created:
        print(f"Profilez instance created for user: {instance.username}")  # Debugging
        if not instance.referral_code:
            print("Generating referral code...")  # Debugging
            instance.referral_code = instance.generate_referral_code()
            instance.save()
            print(f"Referral code generated: {instance.referral_code}")  # Debugging

        if instance.referred_by and not Referral.objects.filter(referee=instance).exists():
            print(f"User was referred by: {instance.referred_by.username}")  # Debugging
            Referral.objects.create(
                referrer=instance.referred_by,
                referee=instance,
                total_commission=00.00,  # Set your default reward amount here
                active_referrals= + 1
            )
            print("Referral instance created.")  # Debugging
                   
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from decimal import Decimal
from users.models import Profile, Referral 



def send_email_referral_commission(referrer_user, investor, commission, investment_type):
    """
    Sends an email notification to the referrer about the earned commission.
    """
    try:
        context = {
            'username': referrer_user.username,
            'referee': investor.username,
            'amount': commission,
            'investment_type': investment_type
        }
        
        html_content = render_to_string('emails/referral_commission.html', context)
        
        send_mail(
            subject="New Referral Commission Earned!",
            message=strip_tags(html_content),
            from_email=settings.ADMIN_EMAIL,
            recipient_list=[referrer_user.email],
            html_message=html_content,
            fail_silently=True
        )
        print(f"Referral commission email sent to {referrer_user.email}")
    except Exception as e:
        print(f"Error sending email notification: {str(e)}")


@receiver(post_save, sender=Investment)
def award_referrer_on_investment(sender, instance, created, **kwargs):
    if created and instance.amount > 0 and instance.is_reinvestment:  # Ensure it's a reinvestment
        investor = instance.user

        try:
            investor_profile = investor.profile
            if investor_profile.referred_by:
                referrer_profile = investor_profile.referred_by
                referrer_user = referrer_profile.user

                commission = instance.amount * Decimal('0.10')

                referral, _ = Referral.objects.get_or_create(
                    referrer=referrer_profile,
                    referee=investor_profile,
                    defaults={'total_commission': Decimal('0.00')}
                )

                referral.total_commission += commission
                referral.save()

                try:
                    referrer_account = Account.objects.get(user=referrer_user)
                    referrer_account.available_balance += commission
                    referrer_account.total_earned += commission
                    referrer_account.save()

                    Notification.create_notification(
                        user=referrer_user,
                        title="Referral Commission Earned",
                        message=f"You've earned ${commission} commission from {investor.username}'s reinvestment of ${instance.amount}!",
                        notification_type='referral',
                        link='/user/referrals/'
                    )

                    send_email_referral_commission(referrer_user, investor, commission, 'reinvestment')

                except Account.DoesNotExist:
                    logger.error(f"No account found for referrer: {referrer_user.username}")

        except Exception as e:
            logger.error(f"Error processing referral commission: {str(e)}")

# @receiver(post_save, sender=Investment)
# def award_referrer_on_investment(sender, instance, created, **kwargs):
#     """
#     Signal handler to award referrers when a new investment or reinvestment is created.
#     Awards 10% commission to the referrer.
#     """
#     if created and instance.amount and instance.amount > 0:
#         print(f"New {'reinvestment' if instance.is_reinvestment else 'investment'} created: {instance}")

#         # Get the user who made the investment
#         investor = instance.user
#         print(f"Investment made by user: {investor.username}")

#         try:
#             # Get the Profilez instance associated with the user
#             investor_profile = investor.profile
            
#             # Check if the user was referred by someone
#             if investor_profile.referred_by:
#                 referrer_profile = investor_profile.referred_by
#                 referrer_user = referrer_profile.user
#                 print(f"Referrer found: {referrer_user.username}")

#                 # Calculate 10% commission
#                 commission = instance.amount * Decimal('0.10')
#                 print(f"Commission amount calculated: {commission}")

#                 # Get or update referral record
#                 referral, created = Referral.objects.get_or_create(
#                     referrer=referrer_profile,
#                     referee=investor_profile,
#                     defaults={'total_commission': Decimal('0.00')}
#                 )

#                 # Update referral commission
#                 referral.total_commission += commission
#                 referral.save()
#                 print(f"Updated referral commission to: {referral.total_commission}")

#                 # Update referrer's account balance
#                 try:
#                     referrer_account = Account.objects.get(user=referrer_user)
#                     referrer_account.available_balance += commission
#                     referrer_account.total_earned += commission
#                     referrer_account.save()
#                     print(f"Updated referrer's balance: +${commission}")

#                     # Create notification for referrer
#                     Notification.create_notification(
#                         user=referrer_user,
#                         title="Referral Commission Earned",
#                         message=(
#                             f"You've earned ${commission} commission from "
#                             f"{investor.username}'s {'reinvestment' if instance.is_reinvestment else 'investment'} "
#                             f"of ${instance.amount}!"
#                         ),
#                         notification_type='referral',
#                         link='/user/referrals/'
#                     )

#                     # Send email notification
#                     try:
#                         context = {
#                             'username': referrer_user.username,
#                             'referee': investor.username,
#                             'amount': commission,
#                             'investment_type': 'reinvestment' if instance.is_reinvestment else 'investment'
#                         }
                        
#                         html_content = render_to_string('emails/referral_commission.html', context)
                        
#                         send_mail(
#                             subject="New Referral Commission Earned!",
#                             message=strip_tags(html_content),
#                             from_email=settings.DEFAULT_FROM_EMAIL,
#                             recipient_list=[referrer_user.email],
#                             html_message=html_content,
#                             fail_silently=True
#                         )
#                     except Exception as e:
#                         print(f"Error sending email notification: {str(e)}")

#                 except Account.DoesNotExist:
#                     print(f"No account found for referrer: {referrer_user.username}")

#         except Exception as e:
#             print(f"Error processing referral commission: {str(e)}")

# @receiver(post_save, sender=Investment)
# def award_referrer(sender, instance, created, **kwargs):
#     """
#     Signal handler to award referrers when a new investment is created.
#     - Awards 10% commission to the referrer.
#     - Updates the referrer's available_balance and total_earned.
#     - Sends email and in-app notifications.
#     """
#     if created and instance.amount and instance.amount > 0:
#         print(f"New investment created: {instance}")

#         # Get the user who made the investment
#         referee = instance.user
#         print(f"Investment made by user: {referee.username}")

#         try:
#             # Get the Profilez instance associated with the user
#             referee_profile = referee.profile  # Assuming the related_name is 'profile'
            
#             # Check if the user was referred by someone
#             if referee_profile.referred_by:
#                 # Get the referrer's User instance
#                 referrer_user = referee_profile.referred_by.user  # Get the User instance
#                 print(f"Referrer found: {referrer_user.username}")

#                 # Calculate 10% of the investment amount using Decimal
#                 total_commission = instance.amount * Decimal('0.10')
#                 print(f"Reward amount calculated: {total_commission}")

#                 # Update or create a Referral instance using the correct User instance
#                 referral, created = Referral.objects.get_or_create(
#                     referrer=referee_profile.referred_by,  # Use the Profilez instance for referrer
#                     referee=referee_profile,
#                     defaults={'total_commission': total_commission}
#                 )

#                 if created:
#                     print(f"Referral record created: {referral}")
#                 else:
#                     print(f"Referral record exists, updating reward amount. Previous reward: {referral.total_commission}")
#                     referral.total_commission += total_commission
#                     referral.save()
#                     print(f"Updated referral reward amount: {referral.total_commission}")

#                 # Award the referrer (update their available_balance and total_earned) using the User instance
#                 try:
#                     referrer_account = Account.objects.get(user=referrer_user)  # Use the User instance
#                     referrer_account.available_balance += total_commission
#                     referrer_account.total_earned += total_commission  # Add commission to total_earned
#                     referrer_account.total_balance_with_roi += total_commission  # Add commission to total balance with ROI
#                     referrer_account.save()
#                     print(f"Referrer's new available_balance: {referrer_account.available_balance}")
#                     print(f"Referrer's new total_earned: {referrer_account.total_earned}")
#                 except Account.DoesNotExist:
#                     print(f"No Account found for referrer: {referrer_user.username}")
#                     return

#                 # Mark the reward as awarded
#                 referral.is_awarded = True
#                 referral.save()
#                 print(f"Referral reward marked as awarded for referrer: {referrer_user.username}")

#                 # Send email notification to the referrer using the User instance
#                 send_referral_email_notification(referrer_user, referee, total_commission)

#                 # Send in-app notification to the referrer using the User instance
#                 send_referral_app_notification(referrer_user, referee, total_commission)

#             else:
#                 print("No referrer found for this investment.")
#         except Profilez.DoesNotExist:
#             print("No Profilez instance found for this user.")
#             return
#     else:
#         print("Investment instance updated or has no valid amount.")


def send_referral_email_notification(referrer, referee, commission):
    """
    Sends an email notification to the referrer about the commission earned.
    """
    try:
        subject = "You've Earned a Referral Commission!"
        
        # Create a simple HTML message without requiring a template
        html_message = f"""
        <html>
            <body>
                <h2>Congratulations {referrer.username}!</h2>
                <p>You've earned a referral commission of ${commission} from {referee.username}'s investment.</p>
                <p>This amount has been added to your available balance.</p>
                <br>
                <p>Thank you for being a valued member of our community!</p>
                <p>Best regards,<br>Vertex Crypto Team</p>
            </body>
        </html>
        """
        
        plain_message = f"""
        Congratulations {referrer.username}!
        
        You've earned a referral commission of ${commission} from {referee.username}'s investment.
        This amount has been added to your available balance.
        
        Thank you for being a valued member of our community!
        
        Best regards,
        Vertex Crypto Team
        """
        
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = referrer.email

        # Create and send the email
        email = EmailMultiAlternatives(
            subject,
            plain_message,
            from_email,
            [to_email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email in a thread
        EmailThread(email).start()
        
        print(f"Email notification sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")
        # Continue execution even if email fails
        pass


def send_referral_app_notification(referrer, referee, commission):
    """
    Sends an in-app notification to the referrer about the commission earned.
    """
    try:
        Notification.objects.create(
            user=referrer,
            title="Referral Commission Earned",
            message=f"You've earned ${commission} from {referee.username}'s investment!",
            notification_type='referral',
            link='/user/referrals/',
        )
        print(f"In-app notification created for {referrer.username}")
    except Exception as e:
        print(f"Failed to create in-app notification: {str(e)}")


# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.utils import timezone
# from user.models import Account, Investment, InvestmentPlan, Transaction
# import logging

# logger = logging.getLogger(__name__)

# @receiver(post_save, sender=Transaction)
# def update_investment_status(sender, instance, **kwargs):
#     """
#     Signal to update investment status when transaction status changes
#     """
#     try:
#         # Check if this transaction is associated with an investment
#         investment = Investment.objects.filter(
#             user=instance.user,
#             amount=instance.amount,
#             status='pending'
#         ).first()

#         if investment:
#             if instance.status == 'confirmed':
#                 # Update investment status and details
#                 now = timezone.now()
#                 investment.status = 'approved'
                
#                 if not investment.is_reinvestment:
#                     investment.start_date = now
#                     if investment.plan.duration_unit == InvestmentPlan.DURATION_UNIT_HOURS:
#                         investment.end_date = now + timezone.timedelta(hours=investment.plan.duration)
#                     else:
#                         investment.end_date = now + timezone.timedelta(days=investment.plan.duration)

#                 # Calculate ROI
#                 investment.roi = investment.calculate_return()
#                 investment.save()

#                 # Update account balances
#                 account = Account.objects.get(user=instance.user)
#                 if not investment.is_reinvestment:
#                     account.invested_balance += investment.amount
#                     account.active_investments += investment.amount
#                     account.last_investment = now
#                     account.save(update_fields=['invested_balance', 'active_investments', 'last_investment'])

#             elif instance.status == 'rejected':
#                 investment.status = 'rejected'
#                 investment.save()

#     except Exception as e:
#         logger.error(f"Error updating investment status: {str(e)}")
