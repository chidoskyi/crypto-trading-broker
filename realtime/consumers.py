import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from trading.services.market_service import MarketDataService

class TradingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time trading updates"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.user_group_name = f'user_{self.user.id}'
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave user group
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'subscribe_ticker':
            symbol = data.get('symbol')
            # Subscribe to ticker updates
            await self.subscribe_ticker(symbol)
        
        elif action == 'unsubscribe_ticker':
            symbol = data.get('symbol')
            await self.unsubscribe_ticker(symbol)
    
    async def subscribe_ticker(self, symbol):
        """Subscribe to ticker updates for a symbol"""
        ticker_group = f'ticker_{symbol}'
        await self.channel_layer.group_add(
            ticker_group,
            self.channel_name
        )
    
    async def unsubscribe_ticker(self, symbol):
        """Unsubscribe from ticker updates"""
        ticker_group = f'ticker_{symbol}'
        await self.channel_layer.group_discard(
            ticker_group,
            self.channel_name
        )
    
    async def ticker_update(self, event):
        """Send ticker update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'ticker_update',
            'data': event['data']
        }))
    
    async def order_update(self, event):
        """Send order update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'order_update',
            'data': event['data']
        }))
    
    async def trading_signal(self, event):
        """Send trading signal to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'trading_signal',
            'signal': event['signal']
        }))