# notifications/admin.py
from django.contrib import admin
from notifications.models import Notification, NotificationPreference

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'notification_type', 'title', 'is_read', 
                   'priority', 'created_at']
    list_filter = ['is_read', 'notification_type', 'priority', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    readonly_fields = ['created_at', 'read_at']
    
    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_read=True, read_at=timezone.now())
    mark_as_read.short_description = "Mark selected as read"
    
    actions = ['mark_as_read']

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_deposit', 'email_trade', 'push_deposit', 
                   'push_trade', 'app_all']
    search_fields = ['user__email']