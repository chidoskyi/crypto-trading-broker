# trading/routing.py
from django.urls import path
from .consumers import TradingConsumer

websocket_urlpatterns = [
    path('ws/trading/', TradingConsumer.as_asgi()),
]