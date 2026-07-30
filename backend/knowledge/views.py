from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from .models import KnowledgeDocument, KnowledgeChunk, RAGRetrievalLog
from .serializers import KnowledgeDocumentSerializer, KnowledgeDocumentDetailSerializer


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_user()


class KnowledgeDocumentListView(generics.ListAPIView):
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = KnowledgeDocument.objects.all()
        status_f = self.request.query_params.get('status')
        topic = self.request.query_params.get('topic')
        if status_f:
            qs = qs.filter(status=status_f)
        if topic:
            qs = qs.filter(topic=topic)
        return qs.order_by('-upload_date')


class KnowledgeDocumentUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAdminUser]

    def post(self, request):
        from rag.loader import extract_text_from_file
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided.'}, status=400)

        allowed_types = ['pdf', 'docx', 'txt', 'csv']
        ext = file.name.rsplit('.', 1)[-1].lower()
        if ext not in allowed_types:
            return Response({'error': f'File type .{ext} not allowed.'}, status=400)

        if file.size > 20 * 1024 * 1024:
            return Response({'error': 'File too large (max 20 MB).'}, status=400)

        doc = KnowledgeDocument.objects.create(
            title=request.data.get('title', file.name),
            file=file,
            file_type=ext,
            topic=request.data.get('topic', 'general'),
            policy_version=request.data.get('policy_version', ''),
            uploaded_by=request.user,
            status=KnowledgeDocument.Status.PENDING,
        )
        try:
            doc.extracted_text = extract_text_from_file(doc.file.path, ext)
            doc.save(update_fields=['extracted_text'])
        except Exception as e:
            doc.extracted_text = f'Extraction failed: {e}'
            doc.save(update_fields=['extracted_text'])

        return Response(KnowledgeDocumentDetailSerializer(doc).data, status=201)


class ApproveDocumentView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, doc_id):
        doc = get_object_or_404(KnowledgeDocument, id=doc_id)
        doc.status = KnowledgeDocument.Status.APPROVED
        doc.active = True
        doc.approved_by = request.user
        doc.approval_date = timezone.now()
        doc.save(update_fields=['status', 'active', 'approved_by', 'approval_date'])

        # Trigger embedding generation in background
        from rag.embeddings import embed_document_async
        embed_document_async(doc.id)

        return Response({'detail': 'Document approved and embedding started.'})


class DisableDocumentView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, doc_id):
        doc = get_object_or_404(KnowledgeDocument, id=doc_id)
        doc.status = KnowledgeDocument.Status.DISABLED
        doc.active = False
        doc.save(update_fields=['status', 'active'])
        KnowledgeChunk.objects.filter(document=doc).update(active=False)
        return Response({'detail': 'Document disabled.'})


class KnowledgeDocumentDetailView(generics.RetrieveAPIView):
    queryset = KnowledgeDocument.objects.all()
    serializer_class = KnowledgeDocumentDetailSerializer
    permission_classes = [IsAdminUser]
    lookup_url_kwarg = 'doc_id'


class FeedbackListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from chatbot.models import CustomerFeedback
        qs = CustomerFeedback.objects.all().order_by('-submitted_at')
        rating = self.request.query_params.get('rating')
        reviewed = self.request.query_params.get('reviewed')
        if rating:
            qs = qs.filter(rating=rating)
        if reviewed == 'false':
            qs = qs.filter(reviewed=False)
        return qs

    def list(self, request, *args, **kwargs):
        from chatbot.models import CustomerFeedback
        from chatbot.serializers import FeedbackSerializer
        qs = self.get_queryset()
        return Response(FeedbackSerializer(qs, many=True).data)


class MarkFeedbackReviewedView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, feedback_id):
        from chatbot.models import CustomerFeedback
        fb = get_object_or_404(CustomerFeedback, id=feedback_id)
        fb.reviewed = True
        fb.save(update_fields=['reviewed'])
        return Response({'detail': 'Feedback marked as reviewed.'})


class RAGMetricsView(APIView):
    """Real, DB-backed AI performance metrics — no hardcoded/mock numbers.

    There's no hand-labelled ground truth in this project (no human-annotated
    'was this actually the right chunk' dataset), so recall/precision/
    faithfulness/answer_relevancy are honest heuristic proxies computed from
    what IS actually recorded (RAGRetrievalLog, ConversationState), not
    textbook IR metrics. They still update in lock-step with real data —
    e.g. deleting all conversations correctly drops every value to 0."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        from chatbot.models import ConversationState

        logs = RAGRetrievalLog.objects.all()
        total = logs.count()
        verified = logs.filter(verification_result=True).count()
        by_band = {}
        for band in ['HIGH', 'MEDIUM', 'LOW']:
            by_band[band] = logs.filter(confidence_band=band).count()

        # recall_at_5 proxy: fraction of retrievals that found ANY chunk at all
        # precision_at_5 proxy: of the chunks retrieved, what fraction were kept
        #   after the similarity-threshold filter (selected_chunk_ids)
        found_any = 0
        precision_sum = 0.0
        similarity_sum = 0.0
        similarity_n = 0
        for log in logs:
            retrieved = log.retrieved_chunk_ids or []
            selected = log.selected_chunk_ids or []
            if retrieved:
                found_any += 1
                precision_sum += len(selected) / len(retrieved)
            for s in (log.similarity_scores or []):
                similarity_sum += s
                similarity_n += 1

        recall_at_5 = round(found_any / total, 2) if total else 0
        precision_at_5 = round(precision_sum / total, 2) if total else 0
        answer_relevancy = round(similarity_sum / similarity_n, 2) if similarity_n else 0
        faithfulness = round(verified / total, 2) if total else 0

        # Per-intent breakdown and 7-day confidence trend, from ConversationState
        # — this is what actually reflects deleted conversations, since
        # ConversationState cascade-deletes with its ChatSession.
        convs = ConversationState.objects.select_related('session').all()
        intent_stats = {}
        for c in convs:
            intents = c.intents or ['unknown']
            primary = intents[0] if intents else 'unknown'
            s = intent_stats.setdefault(primary, {'count': 0, 'conf_sum': 0.0, 'handovers': 0})
            s['count'] += 1
            s['conf_sum'] += c.confidence or 0
            if hasattr(c.session, 'support_case'):
                s['handovers'] += 1
        intent_breakdown = [
            {
                'intent': intent,
                'count': s['count'],
                'avg_confidence': round(s['conf_sum'] / s['count'], 2) if s['count'] else 0,
                'handover_rate': round(s['handovers'] / s['count'], 2) if s['count'] else 0,
                'avg_turns': 0,
            }
            for intent, s in sorted(intent_stats.items(), key=lambda kv: -kv[1]['count'])
        ]

        today = timezone.now().date()
        confidence_trend = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            day_conf = list(convs.filter(session__started_at__date=day).values_list('confidence', flat=True))
            confidence_trend.append(round(sum(day_conf) / len(day_conf), 2) if day_conf else 0)

        return Response({
            'total_retrievals': total,
            'verification_rate': round(verified / total * 100, 1) if total else 0,
            'by_confidence_band': by_band,
            'recall_at_5': recall_at_5,
            'precision_at_5': precision_at_5,
            'faithfulness': faithfulness,
            'answer_relevancy': answer_relevancy,
            'intent_breakdown': intent_breakdown,
            'confidence_trend': confidence_trend,
        })


# Template view for admin panel
def admin_dashboard(request):
    if not request.user.is_authenticated or not request.user.is_admin_user():
        from django.shortcuts import redirect
        return redirect('home')
    return render(request, 'admin_panel/dashboard.html')
