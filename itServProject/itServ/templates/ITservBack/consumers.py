# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if user.is_authenticated:
            self.group_name = f'user_{user.id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            # Envoyer le compte initial des notifications non lues
            unread_count = user.notifications.filter(is_read=False).count()
            await self.send(text_data=json.dumps({
                'type': 'initial_count',
                'unread_count': unread_count
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_notification(self, event):
        message = event['message']
        notification_id = event.get('notification_id')
        unread_count = event.get('unread_count', None)
        data = {
            'type': 'notification',
            'message': message,
            'notification_id': notification_id
        }
        if unread_count is not None:
            data['unread_count'] = unread_count
        await self.send(text_data=json.dumps(data))