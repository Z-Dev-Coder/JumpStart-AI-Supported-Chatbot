import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group = f'chat_{self.session_id}'
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # The support chat is customer-only; staff/admin use the dashboards
        if not user.is_customer():
            await self.close(code=4003)
            return

        session = await self.get_session(self.session_id, user)
        if not session:
            await self.close(code=4004)
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'connection_established', 'session_id': str(self.session_id)}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'customer_message':
            content = data.get('content', '').strip()
            if not content:
                return
            if len(content) > 2000:
                await self.send_error('Message too long (max 2000 characters).')
                return

            message = await self.save_customer_message(content)
            await self.channel_layer.group_send(self.room_group, {
                'type': 'chat_message',
                'message': {
                    'id': message['id'],
                    'sender': 'customer',
                    'content': content,
                    'status': 'sent',
                    'created_at': message['created_at'],
                }
            })

            session_state = await self.get_session_state()
            if session_state == 'AI_ACTIVE':
                # Only the AI responds while no human is involved
                await self.run_agent(self.session_id, content, message['id'])
            else:
                # A human owns this session — surface the message on staff dashboards
                await self.channel_layer.group_send('staff_queue', {
                    'type': 'new_message',
                    'session_id': str(self.session_id),
                    'id': message['id'],
                    'sender': 'customer',
                    'content': content,
                    'created_at': message['created_at'],
                })

        elif msg_type == 'mark_read':
            await self.mark_messages_read(self.session_id)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'type': 'chat_message', **event['message']}))

    async def ai_response(self, event):
        await self.send(text_data=json.dumps({'type': 'ai_response', **event}))

    async def typing_start(self, event):
        await self.send(text_data=json.dumps({'type': 'typing_start', 'sender': event.get('sender', 'ai')}))

    async def typing_stop(self, event):
        await self.send(text_data=json.dumps({'type': 'typing_stop'}))

    async def status_update(self, event):
        await self.send(text_data=json.dumps({'type': 'status_update', 'state': event['state']}))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))

    @database_sync_to_async
    def get_session(self, session_id, user):
        from .models import ChatSession
        try:
            return ChatSession.objects.get(id=session_id, customer=user)
        except ChatSession.DoesNotExist:
            return None

    @database_sync_to_async
    def get_session_state(self):
        from .models import ChatSession
        return ChatSession.objects.get(id=self.session_id).state

    @database_sync_to_async
    def save_customer_message(self, content):
        from .models import ChatSession, ChatMessage
        session = ChatSession.objects.get(id=self.session_id)
        msg = ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.Sender.CUSTOMER,
            sender_user=self.scope['user'],
            content=content,
        )
        return {'id': msg.id, 'created_at': msg.created_at.isoformat()}

    @database_sync_to_async
    def mark_messages_read(self, session_id):
        from .models import ChatMessage
        ChatMessage.objects.filter(
            session_id=session_id,
            sender__in=['ai', 'staff'],
            message_status__in=['sent', 'delivered']
        ).update(message_status='read')

    async def run_agent(self, session_id, content, message_id):
        from agents.runner import run_agent_async
        await run_agent_async(session_id, content, message_id, self.room_group, self.channel_layer)
