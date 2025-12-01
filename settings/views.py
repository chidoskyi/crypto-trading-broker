# from django.shortcuts import render

# # Create your views here.

# import logging

# # Set up logging
# logger = logging.getLogger(__name__)

# def get_client_ip(request):
#     # Get the client's IP address
#     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#     if x_forwarded_for:
#         ip = x_forwarded_for.split(',')[0]
#     else:
#         ip = request.META.get('REMOTE_ADDR')
    
#     # Log and print the client's IP
#     logger.info(f"Client IP: {ip}")  # Log the client's IP
#     print(f"Client IP: {ip}")  # Print the client's IP
#     return ip



# @login_required
# def security_and_2fa_view(request):
#     user = request.user

#     # Get or create security settings for the user
#     security_settings, _ = SecuritySettings.objects.get_or_create(user=user)

#     # Get or create 2FA settings for the user
#     tfa_settings, _ = TwoFactorSettings.objects.get_or_create(user=user)

#     # Generate secret if not already generated for 2FA
#     if not tfa_settings.tfa_secret:
#         tfa_settings.generate_secret()
#         tfa_settings.save()

#     # Create QR code URL for 2FA
#     secret = tfa_settings.tfa_secret
#     app_name = "Vertex Crypto"  # Your app name
#     username = user.username
#     qr_code_url = f"https://chart.googleapis.com/chart?chs=200x200&chld=M|0&cht=qr&chl=otpauth://totp/{username}@{app_name}?secret={secret}"

#     if request.method == 'POST':
#         action = request.POST.get('action')

#         if action == 'security':
#             # Handle IP and browser sensitivity settings
#             ip_sensitivity = request.POST.get('ip', 'disabled')
#             browser_change_detection = request.POST.get('browser', 'disabled') == 'enabled'

#             # Store previous settings for comparison
#             prev_ip_sensitivity = security_settings.ip_sensitivity
#             prev_browser_detection = security_settings.browser_change_detection

#             security_settings.ip_sensitivity = ip_sensitivity
#             security_settings.browser_change_detection = browser_change_detection
#             security_settings.save()

#             # Create notifications for changed settings
#             changes = []
#             if prev_ip_sensitivity != ip_sensitivity:
#                 changes.append(f"IP sensitivity changed to {ip_sensitivity}")
#             if prev_browser_detection != browser_change_detection:
#                 changes.append(f"Browser change detection {'enabled' if browser_change_detection else 'disabled'}")

#             if changes:
#                 Notification.create_notification(
#                     user=user,
#                     title="Security Settings Updated",
#                     message="The following security settings were updated: " + ", ".join(changes),
#                     notification_type='security',
#                     link='/user/security/'
#                 )

#             messages.success(request, "Security settings updated successfully.")
#             return redirect('security')

#         elif action == 'save_2fa':
#             # Enable 2FA
#             token = request.POST.get('code')
#             totp = tfa_settings.get_totp()

#             if totp.verify(token):
#                 tfa_settings.tfa_enabled = True
#                 tfa_settings.save()
                
#                 # Create a notification
#                 Notification.create_notification(
#                     user=user,
#                     title="2FA Enabled",
#                     message="Two-factor authentication has been enabled for your account.",
#                     notification_type='security'
#                 )
                
#                 messages.success(request, "Two-factor authentication enabled successfully.")
#             else:
#                 messages.error(request, "Invalid verification code. Please try again.")
#             return redirect('security')

#         elif action == 'disable_2fa':
#             # Disable 2FA
#             token = request.POST.get('code')
#             totp = tfa_settings.get_totp()

#             if totp.verify(token):
#                 tfa_settings.tfa_enabled = False
#                 tfa_settings.save()
                
#                 # Create a notification
#                 Notification.create_notification(
#                     user=user,
#                     title="2FA Disabled",
#                     message="Two-factor authentication has been disabled for your account.",
#                     notification_type='security'
#                 )
                
#                 messages.success(request, "Two-factor authentication disabled successfully.")
#             else:
#                 messages.error(request, "Invalid verification code. Please try again.")
#             return redirect('security')

#     return render(request, 'user-admin/security.html', {
#         'security_settings': security_settings,
#         'secret': secret,
#         'qr_code_url': qr_code_url,
#         'tfa_enabled': tfa_settings.tfa_enabled,
#     })

# @login_required
# def get_notifications(request):
#     """Get user's notifications"""
#     notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
#     notifications_data = [{
#         'id': notification.id,
#         'title': notification.title,
#         'message': notification.message,
#         'notification_type': notification.notification_type,
#         'link': notification.link,
#         'is_read': notification.is_read,
#         'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S')
#     } for notification in notifications]
    
#     return JsonResponse(notifications_data, safe=False)

# @login_required
# @require_http_methods(["POST"])
# def mark_notification_read(request, notification_id):
#     """Mark a notification as read"""
#     try:
#         notification = Notification.objects.get(id=notification_id, user=request.user)
#         notification.mark_as_read()
#         return JsonResponse({'status': 'success'})
#     except Notification.DoesNotExist:
#         return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

# @login_required
# @require_http_methods(["POST"])
# def mark_all_notifications_read(request):
#     """Mark all notifications as read"""
#     Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
#     return JsonResponse({'status': 'success'})

# def create_user_notification(user, title, message, notification_type='system', link=None):
#     """Helper function to create a notification"""
#     try:
#         notification = Notification.create_notification(
#             user=user,
#             title=title,
#             message=message,
#             notification_type=notification_type,
#             link=link
#         )
#         # Here you would typically trigger a real-time notification
#         # using your preferred method (WebSocket, Server-Sent Events, etc.)
#         return notification
#     except Exception as e:
#         print(f"Error creating notification: {str(e)}")
#         return None


