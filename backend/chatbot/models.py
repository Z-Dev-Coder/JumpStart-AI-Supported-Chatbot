import uuid
from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    class State(models.TextChoices):
        AI_ACTIVE = 'AI_ACTIVE', 'AI Active'
        WAITING_FOR_STAFF = 'WAITING_FOR_STAFF', 'Waiting for Staff'
        HUMAN_ACTIVE = 'HUMAN_ACTIVE', 'Human Active'
        RESOLVED = 'RESOLVED', 'Resolved'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    state = models.CharField(max_length=20, choices=State.choices, default=State.AI_ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    feedback_given = models.BooleanField(default=False)

    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-started_at']

    def __str__(self):
        return f"Session {self.id} — {self.customer.username} [{self.state}]"


class ChatMessage(models.Model):
    class Sender(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        AI = 'ai', 'AI'
        STAFF = 'staff', 'Staff'
        SYSTEM = 'system', 'System'

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=Sender.choices)
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages'
    )
    content = models.TextField()
    quick_replies = models.JSONField(default=list, blank=True)
    is_internal_note = models.BooleanField(default=False)
    message_status = models.CharField(max_length=10, default='sent', choices=[
        ('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read')
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.sender}] {self.content[:60]}"


class ConversationState(models.Model):
    session = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='conversation_state')
    intents = models.JSONField(default=list)
    customer_goal = models.TextField(blank=True)
    entities = models.JSONField(default=dict)
    missing_fields = models.JSONField(default=list)
    clarification_attempts = models.PositiveIntegerField(default=0)
    # A failed order/tracking lookup's own retry counter — deliberately kept
    # separate from clarification_attempts, see agents/graph.py's
    # order_id_retry docstring comment for why.
    order_lookup_attempts = models.PositiveIntegerField(default=0)
    planned_steps = models.JSONField(default=list)
    completed_steps = models.JSONField(default=list)
    tool_call_count = models.PositiveIntegerField(default=0)
    confidence = models.FloatField(default=0.0)
    sentiment = models.CharField(max_length=10, default='neutral', choices=[
        ('positive', 'Positive'), ('neutral', 'Neutral'), ('negative', 'Negative')
    ])
    # Non-empty while the AI has OFFERED (not yet performed) a handover and is
    # waiting for the customer's yes/no — see agents/graph.py's
    # offer_handover_reply / check_pending_handover_offer.
    pending_handover_reason = models.CharField(max_length=25, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversation_states'


class CustomerFeedback(models.Model):
    class Rating(models.TextChoices):
        POSITIVE = 'positive', 'Thumbs Up'
        NEGATIVE = 'negative', 'Thumbs Down'

    class SupportType(models.TextChoices):
        AI_ONLY = 'AI_ONLY', 'AI Only'
        AI_AND_HUMAN = 'AI_AND_HUMAN', 'AI + Human'
        HUMAN_ONLY = 'HUMAN_ONLY', 'Human Only'

    session = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='feedback')
    rating = models.CharField(max_length=10, choices=Rating.choices)
    reason = models.CharField(max_length=100, blank=True)
    comment = models.TextField(blank=True)
    support_type = models.CharField(max_length=15, choices=SupportType.choices)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        db_table = 'customer_feedback'
