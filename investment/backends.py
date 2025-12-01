from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from user.models import Account

class AccountStatusBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(username=username)

            # Allow superuser login without an account
            if user.is_superuser:
                if user.check_password(password):
                    return user
            
            # Regular user account checks
            account = get_object_or_404(Account, user=user)

            # Check if the account is suspended
            if account.status == Account.STATUS_SUSPENDED:
                return None  # Prevent login for suspended accounts

            # Allow login for active accounts
            if user.check_password(password):
                return user  # Return the user for active accounts

        except User.DoesNotExist:
            return None  # User does not exist, return None
        except Account.DoesNotExist:
            return None  # Account does not exist, return None

        return None  # Default case

