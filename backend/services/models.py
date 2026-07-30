from django.db import models
from django.conf import settings


class AgentAction(models.Model):
    session = models.ForeignKey('chatbot.ChatSession', on_delete=models.CASCADE, related_name='agent_actions')
    message_id = models.PositiveIntegerField(null=True, blank=True)
    action_type = models.CharField(max_length=50, choices=[
        ('validate_input', 'Validate Input'),
        ('detect_intent', 'Detect Intent'),
        ('check_missing_fields', 'Check Missing Fields'),
        ('create_plan', 'Create Plan'),
        ('select_tool', 'Select Tool'),
        ('execute_tool', 'Execute Tool'),
        ('verify_result', 'Verify Result'),
        ('generate_response', 'Generate Response'),
        ('safety_check', 'Safety Check'),
        ('route_handover', 'Route to Handover'),
        ('route_clarification', 'Route to Clarification'),
        ('route_answer', 'Route to Answer'),
    ])
    tool_name = models.CharField(max_length=50, blank=True)
    tool_input = models.JSONField(default=dict)
    tool_output = models.JSONField(default=dict)
    success = models.BooleanField(default=True)
    confidence_at_action = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_actions'
        ordering = ['created_at']


class ToolError(models.Model):
    session = models.ForeignKey('chatbot.ChatSession', on_delete=models.CASCADE, related_name='tool_errors')
    tool_name = models.CharField(max_length=50)
    error_type = models.CharField(max_length=50)
    error_message = models.TextField()
    retry_attempted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tool_errors'
