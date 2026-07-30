import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class AdminAuditConsumer(AsyncWebsocketConsumer):
    """Live audit-log updates for one session, viewed from the admin panel's
    Audit Log tab. Only ever sends a bare 'refresh' signal — the actual
    per-message folding logic (intents/entities/tool_results/confidence)
    stays single-sourced in SessionAgentLogView rather than being duplicated
    in JS, so the frontend just re-fetches that endpoint on this event."""

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group = f'agent_audit_{self.session_id}'
        user = self.scope.get('user')

        if not user or not user.is_authenticated or not user.is_admin_user():
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def agent_action_update(self, event):
        await self.send(text_data=json.dumps({'type': 'agent_action_update'}))


class StaffQueueConsumer(AsyncWebsocketConsumer):
    """Dashboard-wide socket: new-case notifications and live customer messages."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated or not (user.is_support_staff() or user.is_admin_user()):
            await self.close(code=4001)
            return
        await self.channel_layer.group_add('staff_queue', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('staff_queue', self.channel_name)

    async def new_case(self, event):
        await self.send(text_data=json.dumps({'type': 'queue_update', **{k: v for k, v in event.items() if k != 'type'}}))

    async def queue_update(self, event):
        await self.send(text_data=json.dumps({'type': 'queue_update'}))

    async def new_message(self, event):
        await self.send(text_data=json.dumps({'type': 'new_message', **{k: v for k, v in event.items() if k != 'type'}}))


class StaffConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.case_id = self.scope['url_route']['kwargs']['case_id']
        self.room_group = f'staff_case_{self.case_id}'
        user = self.scope.get('user')

        if not user or not user.is_authenticated or not (user.is_support_staff() or user.is_admin_user()):
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'staff_reply':
            content = data.get('content', '').strip()
            if not content:
                return
            message = await self.save_staff_message(content)
            # Also notify the customer's chat room
            session_id = await self.get_session_id()
            customer_group = f'chat_{session_id}'
            await self.channel_layer.group_send(customer_group, {
                'type': 'chat_message',
                'message': {
                    'id': message['id'],
                    'sender': 'staff',
                    'sender_name': message['sender_name'],
                    'content': content,
                    'created_at': message['created_at'],
                }
            })
            await self.channel_layer.group_send(self.room_group, {
                'type': 'staff_message',
                'message': {
                    'id': message['id'],
                    'sender': 'staff',
                    'sender_name': message['sender_name'],
                    'content': content,
                    'created_at': message['created_at'],
                }
            })

        elif msg_type == 'internal_note':
            content = data.get('content', '').strip()
            if content:
                await self.save_internal_note(content)

    async def staff_message(self, event):
        await self.send(text_data=json.dumps({'type': 'staff_message', **event['message']}))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'type': 'customer_message', **event['message']}))

    async def case_status_update(self, event):
        await self.send(text_data=json.dumps({'type': 'case_status_update', 'status': event['status']}))

    @database_sync_to_async
    def get_session_id(self):
        from .models import SupportCase
        return str(SupportCase.objects.get(id=self.case_id).session_id)

    @database_sync_to_async
    def save_staff_message(self, content):
        from .models import SupportCase
        from chatbot.models import ChatMessage
        case = SupportCase.objects.get(id=self.case_id)
        user = self.scope['user']
        msg = ChatMessage.objects.create(
            session=case.session,
            sender=ChatMessage.Sender.STAFF,
            sender_user=user,
            content=content,
        )
        return {
            'id': msg.id,
            'sender_name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'created_at': msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def save_internal_note(self, content):
        from .models import SupportCase, StaffNote
        case = SupportCase.objects.get(id=self.case_id)
        StaffNote.objects.create(case=case, staff=self.scope['user'], content=content)
