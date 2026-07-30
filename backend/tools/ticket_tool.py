from typing import Dict, Any


def create_support_ticket(
    session_id: str,
    issue_type: str,
    description: str,
    priority: str = 'normal',
) -> Dict[str, Any]:
    
    from chatbot.models import ChatSession
    from staff.models import SupportCase

    try:
        session = ChatSession.objects.get(id=session_id)
        # Don't create a duplicate if one already exists
        if hasattr(session, 'support_case'):
            return {
                'tool': 'create_support_ticket',
                'success': True,
                'ticket_id': session.support_case.id,
                'message': 'Ticket already exists for this session.',
            }
        case = SupportCase.objects.create(
            session=session,
            handover_reason=SupportCase.HandoverReason.EXPLICIT_REQUEST,
            ai_summary=description,
            customer_goal=issue_type,
            priority=priority,
        )
        return {
            'tool': 'create_support_ticket',
            'success': True,
            'ticket_id': case.id,
            'message': f'Support ticket #{case.id} created with priority {priority}.',
        }
    except Exception as e:
        return {
            'tool': 'create_support_ticket',
            'success': False,
            'error': str(e),
        }
