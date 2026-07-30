"""Agent runner — called from both WebSocket consumer (async) and HTTP fallback (sync)."""
import json
from typing import Optional


def _build_initial_state(session_id: str, content: str, message_id: int, customer_id: int) -> dict:
    # Resume multi-turn context: the clarification counter (and prior entities)
    # must survive across messages or "max 2 attempts" can never trip.
    clarification_attempts = 0
    order_lookup_attempts = 0
    prior_entities = {}
    prior_missing_fields = []
    prior_customer_goal = ''
    prior_pending_handover_reason = ''
    try:
        from chatbot.models import ConversationState
        conv = ConversationState.objects.filter(session_id=session_id).first()
        if conv:
            clarification_attempts = conv.clarification_attempts
            order_lookup_attempts = conv.order_lookup_attempts
            prior_entities = conv.entities or {}
            prior_missing_fields = conv.missing_fields or []
            prior_customer_goal = conv.customer_goal or ''
            prior_pending_handover_reason = conv.pending_handover_reason or ''
    except Exception:
        pass
    return {
        'session_id': session_id,
        'customer_id': customer_id,
        'message_id': message_id,
        'customer_message': content,
        'intents': [],
        'customer_goal': '',
        'entities': prior_entities,
        'missing_fields': [],
        'clarification_attempts': clarification_attempts,
        'order_lookup_attempts': order_lookup_attempts,
        '_prior_missing_fields': prior_missing_fields,
        '_gained_new_entity': False,
        '_prior_customer_goal': prior_customer_goal,
        '_prior_pending_handover_reason': prior_pending_handover_reason,
        'pending_handover_reason': '',
        'planned_steps': [],
        'completed_steps': [],
        'current_step': '',
        'tool_call_count': 0,
        'suggested_action': '',
        'retrieved_documents': [],
        'tool_result': {},
        'tools_used': [],
        'response': '',
        'quick_replies': [],
        'confidence': 0.0,
        'confidence_band': 'LOW',
        'sentiment': 'neutral',
        'requires_handover': False,
        'handover_reason': '',
        'requires_clarification': False,
        'regeneration_attempts': 0,
        'verification_passed': False,
        'safety_passed': True,
        'error': '',
    }


def _latest_system_message(session_id: str):
    from chatbot.models import ChatMessage
    return ChatMessage.objects.filter(
        session_id=session_id, sender=ChatMessage.Sender.SYSTEM
    ).order_by('-created_at').first()


def _save_ai_message(session_id: str, response: str, quick_replies: list):
    from chatbot.models import ChatSession, ChatMessage
    session = ChatSession.objects.get(id=session_id)
    msg = ChatMessage.objects.create(
        session=session,
        sender=ChatMessage.Sender.AI,
        content=response,
        quick_replies=quick_replies,
    )
    return msg


async def run_agent_async(session_id: str, content: str, message_id: int, room_group: str, channel_layer):
    """Run agent and push results via WebSocket channel layer."""
    from channels.db import database_sync_to_async
    from chatbot.models import ChatSession

    session = await database_sync_to_async(ChatSession.objects.get)(id=session_id)
    customer_id = session.customer_id

    # Signal typing
    await channel_layer.group_send(room_group, {'type': 'typing_start', 'sender': 'ai'})

    try:
        from agents.graph import get_graph
        from asgiref.sync import sync_to_async

        graph = get_graph()
        initial = _build_initial_state(session_id, content, message_id, customer_id)

        # LangGraph is sync — run in thread pool
        final_state = await sync_to_async(graph.invoke)(initial)

        response = final_state.get('response', '')
        quick_replies = final_state.get('quick_replies', [])

        await channel_layer.group_send(room_group, {'type': 'typing_stop'})

        if response:
            msg = await database_sync_to_async(_save_ai_message)(session_id, response, quick_replies)
            await channel_layer.group_send(room_group, {
                'type': 'ai_response',
                'content': response,
                'quick_replies': quick_replies,
                'confidence_band': final_state.get('confidence_band', ''),
                'message_id': msg.id,
                'created_at': msg.created_at.isoformat(),
            })

        if final_state.get('requires_handover'):
            # The handover tool saved a system message — push it to the customer
            sys_msg = await database_sync_to_async(_latest_system_message)(session_id)
            if sys_msg:
                await channel_layer.group_send(room_group, {
                    'type': 'chat_message',
                    'message': {
                        'id': sys_msg.id,
                        'sender': 'system',
                        'content': sys_msg.content,
                        'created_at': sys_msg.created_at.isoformat(),
                    }
                })
            await channel_layer.group_send(room_group, {
                'type': 'status_update',
                'state': 'WAITING_FOR_STAFF',
            })

    except Exception as e:
        await channel_layer.group_send(room_group, {'type': 'typing_stop'})
        msg = await database_sync_to_async(_save_ai_message)(
            session_id,
            'I\'m sorry, something went wrong. Let me connect you with a human agent.',
            ['Talk to a human'],
        )
        await channel_layer.group_send(room_group, {
            'type': 'ai_response',
            'content': msg.content,
            'quick_replies': msg.quick_replies,
            'confidence_band': 'LOW',
            'message_id': msg.id,
            'created_at': msg.created_at.isoformat(),
        })


def run_agent_sync(session_id: str, content: str, message_id: int):
    """HTTP fallback — run agent synchronously and return AI message."""
    from chatbot.models import ChatSession

    session = ChatSession.objects.get(id=session_id)
    customer_id = session.customer_id

    try:
        from agents.graph import get_graph
        graph = get_graph()
        initial = _build_initial_state(session_id, content, message_id, customer_id)
        final_state = graph.invoke(initial)

        response = final_state.get('response', '')
        quick_replies = final_state.get('quick_replies', [])

        if response:
            return _save_ai_message(session_id, response, quick_replies)
    except Exception as e:
        from chatbot.models import ChatMessage
        return ChatMessage.objects.create(
            session_id=session_id,
            sender=ChatMessage.Sender.AI,
            content='I\'m sorry, something went wrong. Please try again or contact us for help.',
            quick_replies=['Talk to a human'],
        )
    return None
