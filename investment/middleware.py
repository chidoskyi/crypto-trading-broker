# middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
from django.contrib.auth import logout
from user.models import SecuritySettings
from user.views import track_visitor



class VisitorTrackingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.is_ajax():  # Ensure it's not an AJAX request
            track_visitor(request)  
            
from django.utils.deprecation import MiddlewareMixin

class LoginSecurityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                security_settings = SecuritySettings.objects.get(user=request.user)
            except SecuritySettings.DoesNotExist:
                return

            # IP detection logic
            ip_sensitivity = security_settings.ip_sensitivity
            current_ip = request.META.get('REMOTE_ADDR')
            last_ip = request.session.get('last_ip')

            if ip_sensitivity != 'disabled':
                if last_ip and current_ip != last_ip:
                    # Trigger alert or log out based on sensitivity
                    if ip_sensitivity == 'always':
                        messages.error(request, "IP address change detected! Logging out.")
                        logout(request)

            request.session['last_ip'] = current_ip

            # Browser change detection logic
            if security_settings.browser_change_detection:
                current_browser = request.META.get('HTTP_USER_AGENT')
                last_browser = request.session.get('last_browser')

                if last_browser and current_browser != last_browser:
                    messages.error(request, "Browser change detected! Logging out.")
                    logout(request)

            request.session['last_browser'] = current_browser

