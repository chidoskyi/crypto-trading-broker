# from django.db import models

# # Create your models here.



# class Visitor(models.Model):
#     ip_address = models.GenericIPAddressField()
#     city = models.CharField(max_length=255, blank=True, null=True)
#     region = models.CharField(max_length=255, blank=True, null=True)
#     country = models.CharField(max_length=255, blank=True, null=True)
#     latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
#     longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
#     organization = models.CharField(max_length=255, blank=True, null=True)
#     visited_at = models.DateTimeField(default=timezone.now)

#     def __str__(self):
#         return f"Visitor from {self.city}, {self.country} - IP: {self.ip_address}"



# class SecuritySettings(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     ip_sensitivity = models.CharField(max_length=10, choices=[
#         ('disabled', 'Disabled'),
#         ('medium', 'Medium'),
#         ('high', 'High'),
#         ('always', 'Paranoic'),
#     ], default='disabled')
#     browser_change_detection = models.BooleanField(default=False)

#     def __str__(self):
#         return f"Security settings for {self.user.username}"
    


# class TwoFactorSettings(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     tfa_enabled = models.BooleanField(default=False)
#     tfa_secret = models.CharField(max_length=16, blank=True)  # Secret key for 2FA

#     def generate_secret(self):
#         """Generates a new base32 secret key for the user."""
#         self.tfa_secret = pyotp.random_base32()
#         self.save()

#     def get_totp(self):
#         """Returns the Time-based One-Time Password (TOTP) object."""
#         return pyotp.TOTP(self.tfa_secret)


# # Model for email templates
# class EmailTemplateMessage(models.Model):
#     recipients = models.ManyToManyField(User, related_name='emails', blank=True, db_table='user_emailtemplatemessage_recipients')
#     subject = models.CharField(max_length=255)
#     body = models.TextField()                                               
#     created_at = models.DateTimeField(auto_now_add=True)
#     is_read = models.BooleanField(default=False)
#     send_to_all = models.BooleanField(default=False, verbose_name='Send to all users')

#     def __str__(self):
#         if self.send_to_all:
#             return f"Message to: All Users | Subject: {self.subject}"
#         else:
#             recipient_emails = ', '.join([user.email for user in self.recipients.all()[:5]])
#             if self.recipients.count() > 5:
#                 recipient_emails += f" and {self.recipients.count() - 5} more"
#             return f"Message to: {recipient_emails} | Subject: {self.subject}"

#     @property
#     def email_list(self):
#         """Returns a comma-separated list of recipient email addresses."""
#         if self.send_to_all:
#             return "All Users"
#         return ', '.join([user.email for user in self.recipients.all()])

#     class Meta:
#         db_table = 'user_emailtemplatemessage'


# # class Notification(models.Model):
# #     NOTIFICATION_TYPES = [
# #         ('verification', 'Verification'),
# #         ('transaction', 'Transaction'),
# #         ('security', 'Security'),
# #         ('system', 'System'),
# #         ('referral', 'referral'),
# #         ('investment', 'investment'),
# #     ]

# #     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
# #     title = models.CharField(max_length=255)
# #     message = models.TextField()
# #     notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
# #     link = models.CharField(max_length=255, blank=True, null=True)  # Optional link to redirect user
# #     is_read = models.BooleanField(default=False)
# #     created_at = models.DateTimeField(auto_now_add=True)

# #     class Meta:
# #         ordering = ['-created_at']

# #     def __str__(self):
# #         return f"{self.notification_type}: {self.title} for {self.user.username}"

# #     @classmethod
# #     def create_notification(cls, user, title, message, notification_type, link=None):
# #         """Helper method to create a notification"""
# #         notification = cls.objects.create(
# #             user=user,
# #             title=title,
# #             message=message,
# #             notification_type=notification_type,
# #             link=link
# #         )
# #         return notification

# #     def mark_as_read(self):
# #         """Mark notification as read"""
# #         self.is_read = True
# #         self.save()
