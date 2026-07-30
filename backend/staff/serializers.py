from rest_framework import serializers
from django.utils import timezone
from .models import SupportCase
from chatbot.serializers import ChatSessionSerializer


class SupportCaseSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    session_id = serializers.CharField(source='session.id', read_only=True)
    session_state = serializers.CharField(source='session.state', read_only=True)
    wait_minutes = serializers.SerializerMethodField()
    sentiment = serializers.SerializerMethodField()
    intent_tags = serializers.ListField(source='detected_intents', read_only=True)

    class Meta:
        model = SupportCase
        fields = [
            'id', 'session_id', 'customer_name', 'customer_email', 'session_state',
            'handover_reason', 'ai_confidence', 'priority',
            'wait_minutes', 'sentiment', 'intent_tags',
            'created_at', 'accepted_at',
        ]

    def get_customer_name(self, obj):
        u = obj.session.customer
        return f"{u.first_name} {u.last_name}".strip() or u.username

    def get_customer_email(self, obj):
        return obj.session.customer.email

    def get_wait_minutes(self, obj):
        if obj.session.state == 'WAITING_FOR_STAFF':
            delta = timezone.now() - obj.created_at
            return int(delta.total_seconds() / 60)
        return None

    def get_sentiment(self, obj):
        try:
            return obj.session.conversation_state.sentiment
        except Exception:
            return 'neutral'


class SupportCaseDetailSerializer(SupportCaseSerializer):
    class Meta(SupportCaseSerializer.Meta):
        fields = SupportCaseSerializer.Meta.fields + [
            'ai_summary', 'customer_goal', 'detected_entities',
            'tools_used', 'rag_sources', 'suggested_action', 'resolved_at',
        ]
