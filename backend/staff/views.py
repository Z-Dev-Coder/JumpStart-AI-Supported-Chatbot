from django.shortcuts import render, get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SupportCase
from .serializers import SupportCaseSerializer, SupportCaseDetailSerializer
from chatbot.models import ChatSession, ChatMessage
from chatbot.serializers import ChatMessageSerializer


class IsStaffOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_support_staff() or request.user.is_admin_user()
        )


class QueueView(generics.ListAPIView):
    """Returns waiting, active, and resolved cases for the staff queue."""
    serializer_class = SupportCaseSerializer
    permission_classes = [IsStaffOrAdmin]
    pagination_class = None  # dashboard tabs need the full queue, not one page

    def get_queryset(self):
        session_state_map = {
            'waiting': 'WAITING_FOR_STAFF',
            'active': 'HUMAN_ACTIVE',
            'resolved': 'RESOLVED',
        }
        qs = SupportCase.objects.select_related('session__customer', 'assigned_staff')
        # Accept ?status=all|waiting|active|resolved or ?state=WAITING_FOR_STAFF|...
        state_param = self.request.query_params.get('state', '')
        status_filter = self.request.query_params.get('status', 'waiting')
        if state_param in session_state_map.values():
            qs = qs.filter(session__state=state_param)
        elif status_filter == 'all':
            qs = qs.filter(session__state__in=session_state_map.values())
        else:
            qs = qs.filter(session__state=session_state_map.get(status_filter, 'WAITING_FOR_STAFF'))
        # 'high' sorts before 'normal' alphabetically — urgent cases surface first
        return qs.order_by('priority', 'created_at')


class AcceptCaseView(APIView):
    """Atomically assign a case to the staff member."""
    permission_classes = [IsStaffOrAdmin]

    def post(self, request, case_id):
        with transaction.atomic():
            case = get_object_or_404(
                SupportCase.objects.select_for_update(),
                id=case_id,
                session__state='WAITING_FOR_STAFF'
            )
            # Check max active cases (3)
            active_count = SupportCase.objects.filter(
                assigned_staff=request.user,
                session__state='HUMAN_ACTIVE'
            ).count()
            if active_count >= 3:
                return Response({'error': 'You already have 3 active cases.'}, status=400)

            case.assigned_staff = request.user
            case.accepted_at = timezone.now()
            case.save(update_fields=['assigned_staff', 'accepted_at'])

            session = case.session
            session.state = ChatSession.State.HUMAN_ACTIVE
            session.save(update_fields=['state'])

        # Notify customer via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{session.id}',
            {
                'type': 'status_update',
                'state': 'HUMAN_ACTIVE',
            }
        )
        return Response(SupportCaseDetailSerializer(case).data)


class ResolveCaseView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def post(self, request, case_id):
        case = get_object_or_404(SupportCase, id=case_id, assigned_staff=request.user)
        case.resolved_at = timezone.now()
        case.save(update_fields=['resolved_at'])
        session = case.session
        session.state = ChatSession.State.RESOLVED
        session.resolved_at = timezone.now()
        session.save(update_fields=['state', 'resolved_at'])

        # Prompt customer feedback
        sys_msg = ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.Sender.SYSTEM,
            content='Your support session has been resolved. Please rate your experience.',
        )

        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{session.id}',
            {'type': 'status_update', 'state': 'RESOLVED'}
        )
        return Response({'detail': 'Case resolved.'})


class ReturnToAIView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def post(self, request, case_id):
        case = get_object_or_404(SupportCase, id=case_id, assigned_staff=request.user)
        session = case.session
        session.state = ChatSession.State.AI_ACTIVE
        session.save(update_fields=['state'])

        ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.Sender.SYSTEM,
            content='You have been transferred back to AI support.',
        )
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{session.id}',
            {'type': 'status_update', 'state': 'AI_ACTIVE'}
        )
        return Response({'detail': 'Session returned to AI.'})


class CaseMessagesView(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsStaffOrAdmin]

    def get_queryset(self):
        case = get_object_or_404(SupportCase, id=self.kwargs['case_id'])
        return ChatMessage.objects.filter(session=case.session).order_by('created_at')

    def create(self, request, *args, **kwargs):
        """Staff sends a reply (relayed to the customer) or an internal note."""
        case = get_object_or_404(SupportCase, id=self.kwargs['case_id'])
        content = (request.data.get('content') or '').strip()
        if not content:
            return Response({'error': 'Message content required.'}, status=400)
        is_note = bool(request.data.get('is_internal_note'))

        message = ChatMessage.objects.create(
            session=case.session,
            sender=ChatMessage.Sender.STAFF,
            sender_user=request.user,
            content=content,
            is_internal_note=is_note,
        )

        if not is_note:
            # Push the reply to the customer's chat in real time
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            sender_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
            async_to_sync(channel_layer.group_send)(
                f'chat_{case.session_id}',
                {
                    'type': 'chat_message',
                    'message': {
                        'id': message.id,
                        'sender': 'staff',
                        'sender_name': sender_name,
                        'content': content,
                        'created_at': message.created_at.isoformat(),
                    }
                }
            )
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class IsAdminRole(permissions.BasePermission):
    """Role-based admin check (plan requires role permissions, not is_staff flag)."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_user()


class AdminOverviewView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        today_sessions = ChatSession.objects.filter(started_at__date=today).count()
        yesterday_sessions = ChatSession.objects.filter(started_at__date=yesterday).count()
        resolved_today = ChatSession.objects.filter(resolved_at__date=today).count()
        handover_today = SupportCase.objects.filter(created_at__date=today).count()

        from chatbot.models import ConversationState
        avg_conf = ConversationState.objects.filter(
            session__started_at__date=today
        ).values_list('confidence', flat=True)
        avg_confidence = sum(avg_conf) / len(avg_conf) if avg_conf else 0

        from django.contrib.auth import get_user_model
        User = get_user_model()
        active_staff = User.objects.filter(
            role='staff',
            assigned_cases__session__state='HUMAN_ACTIVE'
        ).distinct().count()

        ai_resolution_rate = (
            (resolved_today - handover_today) / resolved_today * 100
            if resolved_today > 0 else 0
        )

        # Sentiment distribution (today's conversations)
        sentiments = ConversationState.objects.filter(
            session__started_at__date=today
        ).values_list('sentiment', flat=True)
        sent_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        for s in sentiments:
            sent_counts[s] = sent_counts.get(s, 0) + 1

        # Handover trend — cases created per day over the last 7 days
        handover_trend = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            handover_trend.append(SupportCase.objects.filter(created_at__date=day).count())

        # Staff workload — real counts per staff member, not mock data. This
        # (and peak_hours below) previously lived as hardcoded arrays in the
        # frontend and never reflected actual DB state, including deletions.
        staff_workload = []
        for staff_user in User.objects.filter(role='staff'):
            cases = SupportCase.objects.filter(assigned_staff=staff_user)
            resolved = cases.filter(resolved_at__isnull=False)
            avg_minutes = 0
            if resolved.exists():
                deltas = [
                    (c.resolved_at - c.accepted_at).total_seconds() / 60
                    for c in resolved if c.accepted_at and c.resolved_at
                ]
                avg_minutes = round(sum(deltas) / len(deltas), 1) if deltas else 0
            staff_workload.append({
                'label': staff_user.get_full_name() or staff_user.username,
                'cases': cases.count(),
                'avg_minutes': avg_minutes,
            })

        # Peak chat hours — 7x24 matrix of session start times, last 4 weeks
        peak_hours = [[0] * 24 for _ in range(7)]
        recent_sessions = ChatSession.objects.filter(
            started_at__date__gte=today - timedelta(days=28)
        ).values_list('started_at', flat=True)
        for started_at in recent_sessions:
            local = timezone.localtime(started_at)
            peak_hours[local.weekday()][local.hour] += 1

        return Response({
            'chats_today': today_sessions,
            'chats_yesterday': yesterday_sessions,
            'ai_resolution_rate': round(max(ai_resolution_rate, 0), 1),
            'avg_confidence': round(avg_confidence, 2),
            'handover_rate': round(handover_today / today_sessions * 100, 1) if today_sessions > 0 else 0,
            'active_staff': active_staff,
            'resolved_today': resolved_today,
            'sentiment_positive': sent_counts['positive'],
            'sentiment_neutral': sent_counts['neutral'],
            'sentiment_negative': sent_counts['negative'],
            'handover_trend_7d': handover_trend,
            'staff_workload': staff_workload,
            'peak_hours': peak_hours,
        })


class SessionAgentLogView(APIView):
    """Per-message AI reasoning log for one chat session — powers the admin
    Audit Log tab so an admin can see, for every customer message, what the
    agent detected (intent/entities/sentiment), which tool it called, the
    confidence it computed, and whether/why it escalated to a human."""
    permission_classes = [IsAdminRole]

    def get(self, request, session_id):
        from services.models import AgentAction
        from knowledge.models import RAGRetrievalLog

        actions = AgentAction.objects.filter(session_id=session_id).order_by('created_at')
        rag_logs = RAGRetrievalLog.objects.filter(session_id=session_id)
        rag_by_message = {}
        for log in rag_logs:
            rag_by_message.setdefault(log.message_id, []).append({
                'similarity_scores': log.similarity_scores,
                'confidence_band': log.confidence_band,
            })

        # Fold each message_id's scattered node-level rows into one summary —
        # this is what the frontend actually renders per customer message.
        by_message = {}
        for a in actions:
            mid = a.message_id
            if mid is None:
                continue
            entry = by_message.setdefault(mid, {
                'message_id': mid,
                'intents': [], 'customer_goal': '', 'entities': {}, 'sentiment': None,
                'tools_used': [], 'tool_results': [],
                'confidence': None, 'confidence_band': None,
                'requires_handover': False, 'handover_reason': '',
                'requested_clarification': False, 'clarification_missing_fields': [],
                'injection_blocked': False,
                'created_at': a.created_at.isoformat(),
            })
            if a.action_type == 'detect_intent':
                entry['intents'] = a.tool_output.get('intents', [])
                entry['customer_goal'] = a.tool_output.get('customer_goal', '')
                entry['entities'] = a.tool_output.get('entities', {})
                entry['sentiment'] = a.tool_output.get('sentiment')
            elif a.action_type == 'execute_tool':
                # tool_name='none' is execute_tool's placeholder for "no tool
                # was needed" (tool_category='none', e.g. a plain FAQ answer
                # generated straight from conversation) — it's not a real
                # tool call, so surfacing it here would read as a fake tool.
                if a.tool_name and a.tool_name != 'none':
                    entry['tools_used'].append(a.tool_name)
                    entry['tool_results'].append({'tool_name': a.tool_name, 'success': a.success, 'output': a.tool_output})
            elif a.action_type == 'verify_result':
                entry['confidence'] = a.confidence_at_action
                entry['confidence_band'] = a.tool_output.get('confidence_band')
                entry['requires_handover'] = a.tool_output.get('requires_handover', False)
                entry['handover_reason'] = a.tool_output.get('handover_reason', '')
            elif a.action_type == 'generate_clarification':
                # No tool is ever called on this path — this is what tells the
                # admin a blank tool/confidence area means "asked a follow-up
                # question", not "something silently failed."
                entry['requested_clarification'] = True
                entry['clarification_missing_fields'] = a.tool_output.get('missing_fields', [])
            elif a.action_type == 'route_handover':
                entry['requires_handover'] = True
                entry['handover_reason'] = entry['handover_reason'] or a.action_type
            elif a.action_type == 'injection_guard':
                # NOT an escalation — guard_reply blocks the message with a
                # canned refusal and routes straight to save_state, never
                # through execute_handover (see agents/graph.py). Grouping
                # this with route_handover made the admin audit log falsely
                # claim every blocked injection attempt was escalated to a
                # human, when the session actually stayed AI_ACTIVE.
                entry['injection_blocked'] = True
            entry['rag'] = rag_by_message.get(mid, [])

        return Response({'messages': list(by_message.values())})


# ─── Template Views ────────────────────────────────────────────────────────────

def staff_dashboard(request):
    if not request.user.is_authenticated or not (
        request.user.is_support_staff() or request.user.is_admin_user()
    ):
        from django.shortcuts import redirect
        return redirect('home')
    return render(request, 'staff/dashboard.html')


def staff_case_view(request, case_id):
    if not request.user.is_authenticated or not (
        request.user.is_support_staff() or request.user.is_admin_user()
    ):
        from django.shortcuts import redirect
        return redirect('home')
    case = get_object_or_404(SupportCase, id=case_id)
    return render(request, 'staff/dashboard.html', {'active_case_id': case_id})


def staff_account(request):
    """Staff's own account/profile management — separate from the case dashboard."""
    if not request.user.is_authenticated or not (
        request.user.is_support_staff() or request.user.is_admin_user()
    ):
        from django.shortcuts import redirect
        return redirect('home')
    return render(request, 'staff/account.html')
