from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from .models import Investment, InvestmentPlan, InvestmentTransaction
from users.models import Account
import logging

logger = logging.getLogger(__name__)

class ROIService:
    """
    Service class for handling Return on Investment (ROI) calculations and processing.
    Formula: ROI = Investment Amount * Interest Rate%
    """
    
    @staticmethod
    def calculate_roi(investment):
        """
        Calculate ROI for an investment using the formula: amount * interest_rate%
        
        Args:
            investment: Investment object to calculate ROI for
            
        Returns:
            Decimal: Calculated ROI amount rounded to 2 decimal places
        """
        try:
            # Simple ROI calculation: amount * interest_rate%
            roi = investment.amount * (investment.plan.interest_rate / Decimal('100'))
            return Decimal(str(round(float(roi), 2)))
        except Exception as e:
            logger.error(f"ROI calculation error for investment {investment.id}: {str(e)}")
            return Decimal('0.00')
    
    @staticmethod
    @transaction.atomic
    def process_roi_payout(investment):
        """
        Process ROI payout for an investment at maturity.
        Only processes if the investment has reached its end date.
        
        Args:
            investment: Investment object to process ROI for
            
        Returns:
            bool: True if payout was successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Only process if investment has reached end date and is not completed
                if investment.completed or timezone.now() < investment.end_date:
                    return False

                # Calculate ROI
                roi_amount = ROIService.calculate_roi(investment)
                if roi_amount <= 0:
                    return False

                # Update investment record
                investment.roi = roi_amount
                investment.completed = True
                investment.save()

                # Update user account
                account = Account.objects.select_for_update().get(user=investment.user)
                
                # Add ROI to earnings and available balance
                account.total_earned += roi_amount
                account.investment_balance += (investment.amount + roi_amount)  # Return principal + ROI
                
                # Save account changes
                account.save(update_fields=['total_earned', 'investment_balance'])

                # Recalculate active_investments based on current data
                account.update_active_investments()

                # Create transaction record
                InvestmentTransaction.objects.create(
                    user=investment.user,
                    transaction_type='investment',
                    amount=roi_amount,
                    status='completed',
                    confirmed=True,
                    description=f"ROI payout: {investment.plan.interest_rate}% on ${investment.amount} investment in {investment.plan.name}",
                    investment_plan=investment.plan
                )

                # Send notifications
                ROIService._send_notifications(investment, roi_amount)
                return True

        except Exception as e:
            logger.error(f"ROI payout processing failed: {str(e)}")
            return False

    @staticmethod
    def _send_notifications(investment, roi_amount):
        """Send notifications for ROI payout"""
        # Create in-app notification
        Notification.create_notification(
            user=investment.user,
            title="Investment ROI Received",
            message=(
                f"Your investment of ${investment.amount} in {investment.plan.name} has earned "
                f"${roi_amount} (Rate: {investment.plan.interest_rate}%)"
            ),
            notification_type='transaction'
        )

        # Send email notification
        try:
            send_mail(
                'Investment ROI Payout',
                f'''Your investment has generated returns!

Investment Details:
- Amount: ${investment.amount}
- Plan: {investment.plan.name}
- ROI Rate: {investment.plan.interest_rate}%
- ROI Amount: ${roi_amount}

The ROI has been credited to your available balance.
                ''',
                settings.ADMIN_EMAIL,
                [investment.user.email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send ROI payout email: {str(e)}")

    @staticmethod
    def process_all_pending_payouts():
        """
        Process ROI payouts for all matured investments.
        Only processes investments that have reached their end date.
        """
        # Get all investments that have reached their end date but aren't completed
        matured_investments = Investment.objects.filter(
            completed=False,
            end_date__lte=timezone.now()
        ).select_related('user', 'plan')

        results = {
            'total_processed': 0,
            'successful_payouts': 0,
            'failed_payouts': 0,
            'total_amount_paid': Decimal('0.00')
        }

        for investment in matured_investments:
            success = ROIService.process_roi_payout(investment)
            results['total_processed'] += 1
            
            if success:
                results['successful_payouts'] += 1
                results['total_amount_paid'] += investment.roi
            else:
                results['failed_payouts'] += 1

        return results

    @staticmethod
    def get_investment_statistics(user):
        """Get investment statistics for a user"""
        stats = {
            'total_invested': Decimal('0.00'),
            'active_investments': 0,
            'total_roi_earned': Decimal('0.00'),
            'pending_roi': Decimal('0.00'),
            'expected_roi': Decimal('0.00')
        }

        investments = Investment.objects.filter(user=user)
        
        for inv in investments:
            if not inv.completed:
                stats['active_investments'] += 1
                expected_roi = ROIService.calculate_roi(inv)
                stats['expected_roi'] += expected_roi
                if timezone.now() >= inv.end_date:
                    stats['pending_roi'] += expected_roi
            else:
                stats['total_roi_earned'] += inv.roi
            
            stats['total_invested'] += inv.amount

        return stats