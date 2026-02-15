import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Counsellor, CounsellorBooking, CounsellorChatMessage, CounsellorNotification


class CounsellorChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.booking_id = int(self.scope['url_route']['kwargs']['booking_id'])
        self.room_group_name = f'booking_{self.booking_id}'
        if not await self._user_can_access_booking(user.id, self.booking_id):
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return
        content = (payload.get('content') or '').strip()
        if not content:
            return
        message_data, notification_data = await self._save_message(self.scope['user'].id, self.booking_id, content)
        if not message_data:
            await self.send(text_data=json.dumps({
                'type': 'chat_locked',
                'message': 'This session has been completed/cancelled. Chat is disabled.',
            }))
            return
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat.message',
                'message': message_data,
            }
        )
        if notification_data and notification_data.get('target_user_id'):
            await self.channel_layer.group_send(
                f"doctor_{notification_data['target_user_id']}",
                {
                    'type': 'doctor.notification',
                    'notification': notification_data['notification'],
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
        }))

    @database_sync_to_async
    def _user_can_access_booking(self, user_id, booking_id):
        booking = CounsellorBooking.objects.select_related('counsellor').filter(pk=booking_id).first()
        if not booking:
            return False
        if booking.user_id == user_id:
            return True
        return bool(booking.counsellor.user_id and booking.counsellor.user_id == user_id)

    @database_sync_to_async
    def _save_message(self, sender_id, booking_id, content):
        booking = CounsellorBooking.objects.select_related('counsellor', 'user').get(pk=booking_id)
        if booking.status in ('completed', 'cancelled'):
            return None, None
        is_first_message = not CounsellorChatMessage.objects.filter(booking=booking).exists()
        msg = CounsellorChatMessage.objects.create(
            booking=booking,
            sender_id=sender_id,
            content=content,
        )
        message_data = {
            'id': msg.id,
            'sender': msg.sender.get_username(),
            'sender_id': msg.sender_id,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
        }
        notification_data = None
        if sender_id != booking.counsellor.user_id:
            notif = CounsellorNotification.objects.create(
                counsellor=booking.counsellor,
                booking=booking,
                actor_id=sender_id,
                event_type='chat_started' if is_first_message else 'message_received',
                title='Patient started chat' if is_first_message else 'New patient message',
                body=f'{msg.sender.get_username()}: {msg.content[:120]}',
            )
            notification_data = {
                'target_user_id': booking.counsellor.user_id,
                'notification': {
                    'id': notif.id,
                    'event_type': notif.event_type,
                    'title': notif.title,
                    'body': notif.body,
                    'booking_id': notif.booking_id,
                    'created_at': notif.created_at.isoformat(),
                    'is_read': notif.is_read,
                }
            }
        return message_data, notification_data


class DoctorNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return
        if not await self._is_counsellor(user.id):
            await self.close()
            return
        self.group_name = f'doctor_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def doctor_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'doctor_notification',
            'notification': event['notification'],
        }))

    @database_sync_to_async
    def _is_counsellor(self, user_id):
        return Counsellor.objects.filter(user_id=user_id).exists()
