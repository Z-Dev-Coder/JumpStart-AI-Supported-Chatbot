from django.db import models
from django.conf import settings


class SupportCase(models.Model):
    class HandoverReason(models.TextChoices):
        EXPLICIT_REQUEST = 'explicit_request', 'Customer Requested'
        LOW_CONFIDENCE = 'low_confidence', 'Low AI Confidence'
        NO_EVIDENCE = 'no_evidence', 'No Evidence Found'
        TOOL_FAILURE = 'tool_failure', 'Tool Failure'
        REPEATED_FAILURE = 'repeated_failure', 'Repeated Failure'
        SENSITIVE_ISSUE = 'sensitive_issue', 'Sensitive Issue'
        CLARIFICATION_FAILED = 'clarification_failed', 'Clarification Failed'
        FRUSTRATED_CUSTOMER = 'frustrated_customer', 'Frustrated Customer'

    session = models.OneToOneField('chatbot.ChatSession', on_delete=models.CASCADE, related_name='support_case')
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cases'
    )
    handover_reason = models.CharField(max_length=25, choices=HandoverReason.choices)
    ai_summary = models.TextField(blank=True)
    customer_goal = models.TextField(blank=True)
    detected_intents = models.JSONField(default=list)
    detected_entities = models.JSONField(default=dict)
    tools_used = models.JSONField(default=list)
    rag_sources = models.JSONField(default=list)
    ai_confidence = models.FloatField(default=0.0)
    suggested_action = models.TextField(blank=True)
    priority = models.CharField(max_length=10, default='normal', choices=[
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')
    ])
    accepted_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_cases'
        ordering = ['-created_at']

    def __str__(self):
        return f"Case #{self.id} — {self.handover_reason}"


class StaffNote(models.Model):
    case = models.ForeignKey(SupportCase, on_delete=models.CASCADE, related_name='notes')
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'staff_notes'
        ordering = ['created_at']
