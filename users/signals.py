from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model  
from django.db import transaction
from .models import Profile, Account

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to automatically create a profile when a new user is created
    """
    if created:
        # Use transaction.atomic to ensure data consistency
        with transaction.atomic():
            Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal to automatically save the profile when the user is saved
    """
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        # If profile doesn't exist, create one
        Profile.objects.create(user=instance)
        
@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    """
    Signal to automatically create an account when a new user is created
    """
    if created:
        # Use transaction.atomic to ensure data consistency
        with transaction.atomic():
            Account.objects.get_or_create(user=instance)
            
def save_user_account(sender, instance, **kwargs):
    """
    Signal to automatically save the account when the user is saved
    """
    try:
        instance.account.save()
    except Account.DoesNotExist:
        # If account doesn't exist, create one
        Account.objects.create(user=instance)   