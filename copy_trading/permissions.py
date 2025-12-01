from rest_framework import permissions


class IsTrader(permissions.BasePermission):
    """
    Permission to check if user is a registered trader
    """
    def has_permission(self, request, view):
        return hasattr(request.user, 'trader') and request.user.trader.is_active


class IsSubscriptionOwner(permissions.BasePermission):
    """
    Permission to check if user owns the subscription
    """
    def has_object_permission(self, request, view, obj):
        return obj.follower == request.user


class IsCopiedTradeOwner(permissions.BasePermission):
    """
    Permission to check if user owns the copied trade
    """
    def has_object_permission(self, request, view, obj):
        return obj.subscription.follower == request.user