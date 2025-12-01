# notifications/serializers.py
from rest_framework import serializers
from notifications.models import Notification, NotificationPreference

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'message', 'link',
                  'is_read', 'read_at', 'priority', 'email_sent', 'push_sent',
                  'created_at']
        read_only_fields = ['id', 'created_at']

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['email_deposit', 'email_withdrawal', 'email_trade', 
                  'email_signal', 'email_kyc', 'email_security',
                  'push_deposit', 'push_withdrawal', 'push_trade',
                  'push_signal', 'push_kyc', 'push_security', 'app_all']