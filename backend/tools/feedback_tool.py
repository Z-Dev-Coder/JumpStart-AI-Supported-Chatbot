from typing import Dict, Any


def save_feedback(session_id: str, rating: str, reason: str = '', comment: str = '') -> Dict[str, Any]:
   
    from chatbot.models import ChatSession, CustomerFeedback

    try:
        session = ChatSession.objects.get(id=session_id)
        if hasattr(session, 'feedback'):
            return {'tool': 'save_feedback', 'success': True, 'message': 'Feedback already recorded.'}

        support_type = 'AI_ONLY'
        if hasattr(session, 'support_case'):
            support_type = 'AI_AND_HUMAN'

        CustomerFeedback.objects.create(
            session=session,
            rating=rating,
            reason=reason,
            comment=comment,
            support_type=support_type,
        )
        session.feedback_given = True
        session.save(update_fields=['feedback_given'])
        return {'tool': 'save_feedback', 'success': True, 'message': 'Feedback saved.'}
    except Exception as e:
        return {'tool': 'save_feedback', 'success': False, 'error': str(e)}
