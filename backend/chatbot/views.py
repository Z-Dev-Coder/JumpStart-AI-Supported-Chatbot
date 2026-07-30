import uuid
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser

from .models import ChatSession, ChatMessage, CustomerFeedback
from .serializers import ChatSessionSerializer, ChatMessageSerializer, FeedbackSerializer


def _is_staff_or_admin(user):
    return user.is_authenticated and (user.is_support_staff() or user.is_admin_user())


class IsCustomer(permissions.BasePermission):
    """The support chatbot is for customers; staff and admin work in dashboards."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_customer()


class ChatSessionListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        user = self.request.user
        if _is_staff_or_admin(user):
            # Staff/admin see every session (admin audit log view)
            qs = ChatSession.objects.select_related('customer').all()
            q = self.request.query_params.get('q')
            date = self.request.query_params.get('date')
            if q:
                qs = qs.filter(customer__username__icontains=q)
            if date:
                qs = qs.filter(started_at__date=date)
            return qs.order_by('-started_at')
        return ChatSession.objects.select_related('customer').filter(customer=user).order_by('-started_at')

    def perform_create(self, serializer):
        if not self.request.user.is_customer():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only customers can start chat sessions.')
        serializer.save(customer=self.request.user)


class ChatSessionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        if _is_staff_or_admin(self.request.user):
            return ChatSession.objects.all()
        return ChatSession.objects.filter(customer=self.request.user)

    def perform_destroy(self, instance):
        # Customers may only clear their own chat history, not active sessions
        # currently being staffed — that'd yank the rug from under an agent.
        if _is_staff_or_admin(self.request.user):
            instance.delete()
            return
        if instance.state in ('WAITING_FOR_STAFF', 'HUMAN_ACTIVE'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Cannot delete a session that is currently being handled by support.')
        instance.delete()


class ChatMessageListView(generics.ListAPIView):
    serializer_class = ChatMessageSerializer

    def get_queryset(self):
        session_id = self.kwargs['session_id']
        if _is_staff_or_admin(self.request.user):
            session = get_object_or_404(ChatSession, id=session_id)
        else:
            session = get_object_or_404(ChatSession, id=session_id, customer=self.request.user)
        return ChatMessage.objects.filter(
            session=session, is_internal_note=False
        ).order_by('created_at')


class SendMessageView(APIView):
    """HTTP fallback for when WebSocket is unavailable (2-3 sec polling)."""
    permission_classes = [IsCustomer]

    def post(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, customer=request.user)
        content = request.data.get('content', '').strip()
        if not content:
            return Response({'error': 'Message content required.'}, status=400)
        if len(content) > 2000:
            return Response({'error': 'Message too long.'}, status=400)

        message = ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.Sender.CUSTOMER,
            sender_user=request.user,
            content=content,
        )
        ai_message = None
        if session.state == ChatSession.State.AI_ACTIVE:
            # Run agent synchronously for HTTP fallback
            from agents.runner import run_agent_sync
            ai_message = run_agent_sync(session_id, content, message.id)
        else:
            # Human-handled session — notify staff dashboards
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)('staff_queue', {
                'type': 'new_message',
                'session_id': str(session.id),
                'id': message.id,
                'sender': 'customer',
                'content': content,
                'created_at': message.created_at.isoformat(),
            })
        session.refresh_from_db()
        # Include everything the agent produced (AI reply and/or handover system message)
        new_messages = ChatMessage.objects.filter(
            session=session, id__gt=message.id
        ).order_by('created_at')
        return Response({
            'customer_message': ChatMessageSerializer(message).data,
            'ai_response': ChatMessageSerializer(ai_message).data if ai_message else None,
            'new_messages': ChatMessageSerializer(new_messages, many=True).data,
            'session_state': session.state,
        })


class ActiveChatSessionView(APIView):
    """Read-only — does it ever create anything. Lets the chat widget check for
    an already-open conversation in the background (e.g. right after a page
    navigation) without silently starting a new session just because the
    page loaded. Returns 204 if the customer has no unresolved session."""
    permission_classes = [IsCustomer]

    def get(self, request):
        session = ChatSession.objects.filter(
            customer=request.user
        ).exclude(state=ChatSession.State.RESOLVED).order_by('-started_at').first()
        if not session:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({
            'session_id': str(session.id),
            'state': session.state,
            'feedback_given': session.feedback_given,
        })


class NewChatSessionView(APIView):
    """Get-or-create: resumes the customer's most recent unresolved session
    instead of always starting a new one — "click chat" should mean
    "continue where I left off", not "abandon my last conversation"."""
    permission_classes = [IsCustomer]

    def post(self, request):
        session = ChatSession.objects.filter(
            customer=request.user
        ).exclude(state=ChatSession.State.RESOLVED).order_by('-started_at').first()
        if session:
            return Response({
                'session_id': str(session.id),
                'state': session.state,
                'feedback_given': session.feedback_given,
            })
        session = ChatSession.objects.create(customer=request.user)
        from chatbot.models import ConversationState
        ConversationState.objects.create(session=session)
        return Response({
            'session_id': str(session.id),
            'state': session.state,
            'feedback_given': session.feedback_given,
        }, status=status.HTTP_201_CREATED)


class EndChatSessionView(APIView):
    """The customer's own "X" button — distinct from staff resolving a case.
    Only actually closes the session while it's still AI_ACTIVE (the customer
    hasn't been handed to / isn't waiting for a human yet); a session that's
    already queued or being handled by staff can't be unilaterally abandoned
    from here — it stays open so the next chat click correctly resumes it
    instead of orphaning a case someone is already working on."""
    permission_classes = [IsCustomer]

    def post(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, customer=request.user)
        if session.state == ChatSession.State.AI_ACTIVE:
            from django.utils import timezone
            session.state = ChatSession.State.RESOLVED
            session.resolved_at = timezone.now()
            session.save(update_fields=['state', 'resolved_at'])
        return Response({'state': session.state})


class SubmitFeedbackView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, customer=request.user)
        if hasattr(session, 'feedback'):
            return Response({'error': 'Feedback already submitted.'}, status=400)

        support_type = 'AI_ONLY'
        if hasattr(session, 'support_case'):
            support_type = 'AI_AND_HUMAN'

        serializer = FeedbackSerializer(data={
            **request.data,
            'session': session.id,
            'support_type': support_type,
        })
        serializer.is_valid(raise_exception=True)
        serializer.save(session=session, support_type=support_type)
        session.feedback_given = True
        session.save(update_fields=['feedback_given'])
        return Response({'detail': 'Thank you for your feedback!'})
