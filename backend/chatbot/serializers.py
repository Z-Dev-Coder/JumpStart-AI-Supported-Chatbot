from rest_framework import serializers
from .models import ChatSession, ChatMessage, CustomerFeedback


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ['id', 'sender', 'sender_name', 'content', 'quick_replies',
                  'is_internal_note', 'message_status', 'created_at']

    def get_sender_name(self, obj):
        if obj.sender_user:
            return f"{obj.sender_user.first_name} {obj.sender_user.last_name}".strip() or obj.sender_user.username
        return 'AI Assistant' if obj.sender == 'ai' else 'Support'


class ChatSessionSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ['id', 'state', 'started_at', 'resolved_at', 'feedback_given', 'last_message',
                  'unread_count', 'customer_username', 'customer_name']

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        return ChatMessageSerializer(msg).data if msg else None

    def get_unread_count(self, obj):
        return obj.messages.filter(sender__in=['ai', 'staff'], message_status__in=['sent', 'delivered']).count()

    def get_customer_name(self, obj):
        full_name = f"{obj.customer.first_name} {obj.customer.last_name}".strip()
        return full_name or obj.customer.username


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerFeedback
        fields = ['id', 'rating', 'reason', 'comment', 'support_type', 'reviewed', 'submitted_at']
        read_only_fields = ['id', 'reviewed', 'submitted_at']
