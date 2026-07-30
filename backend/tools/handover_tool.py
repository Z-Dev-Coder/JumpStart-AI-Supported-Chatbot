from typing import Dict, Any

# Customer-facing explanation shown right before the "waiting for agent" card,
# so the handover never looks like it happened silently/out of nowhere.
HANDOVER_MESSAGES = {
    'explicit_request': "Sure — connecting you with a member of our support team now. Please wait a moment.",
    'low_confidence': "I want to make sure you get this right, so I'm bringing in a human teammate to help. Please wait a moment.",
    'no_evidence': "I couldn't find enough information to answer that confidently, so I'm connecting you with a human agent. Please wait a moment.",
    'tool_failure': "Sorry, I ran into a technical issue on my end. Let me connect you with a human agent who can help. Please wait a moment.",
    'repeated_failure': "I'm having trouble resolving this for you, so I'm handing you over to a human agent. Please wait a moment.",
    'sensitive_issue': "This needs a closer look from our support team, so I'm connecting you with a human agent. Please wait a moment.",
    'clarification_failed': "I'm not able to gather enough details to help with this myself, so I'm connecting you with a human agent. Please wait a moment.",
    'frustrated_customer': "I'm sorry this hasn't gone smoothly. Let me connect you with a human agent right away.",
}
DEFAULT_HANDOVER_MESSAGE = "I'm not able to fully handle this myself, so I'm connecting you with a human support agent. Please wait a moment."


def handover_to_human(
    session_id: str,
    reason: str,
    ai_summary: str,
    customer_goal: str,
    detected_intents: list,
    detected_entities: dict,
    tools_used: list,
    rag_sources: list,
    confidence: float,
    suggested_action: str = '',
    policy_reason: str = '',
) -> Dict[str, Any]:

    from chatbot.models import ChatSession, ChatMessage
    from staff.models import SupportCase
    from django.utils import timezone

    try:
        session = ChatSession.objects.get(id=session_id)

        # Idempotent — don't create a second case
        if hasattr(session, 'support_case'):
            case = session.support_case
        else:
            case = SupportCase.objects.create(
                session=session,
                handover_reason=reason,
                ai_summary=ai_summary,
                customer_goal=customer_goal,
                detected_intents=detected_intents,
                detected_entities=detected_entities,
                tools_used=tools_used,
                rag_sources=rag_sources,
                ai_confidence=confidence,
                suggested_action=suggested_action,
                priority='high' if (
                    confidence < 0.40
                    or reason in ('frustrated_customer', 'sensitive_issue')
                ) else 'normal',
            )

        session.state = ChatSession.State.WAITING_FOR_STAFF
        session.save(update_fields=['state'])

        # System message visible to customer — explains *why* before the
        # waiting card appears, instead of the handover looking silent/abrupt.
        # When a policy check (e.g. return/cancellation eligibility) already
        # produced a factual answer, lead with that instead of a content-free
        # line — a human still has to execute the action, but the customer
        # shouldn't have to wait for staff just to hear the policy answer.
        message = HANDOVER_MESSAGES.get(reason, DEFAULT_HANDOVER_MESSAGE)
        if policy_reason:
            message = f"{policy_reason} {message}"
        ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.Sender.SYSTEM,
            content=message,
        )

        # Notify staff queue via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'staff_queue',
            {
                'type': 'new_case',
                'case_id': case.id,
                'customer_name': session.customer.get_full_name() or session.customer.username,
                'reason': reason,
                'confidence': confidence,
            }
        )

        return {
            'tool': 'handover_to_human',
            'success': True,
            'case_id': case.id,
            'new_state': 'WAITING_FOR_STAFF',
        }
    except Exception as e:
        return {
            'tool': 'handover_to_human',
            'success': False,
            'error': str(e),
        }
