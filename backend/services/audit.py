from typing import Dict, Any


def log_agent_action(
    session_id: str,
    action_type: str,
    tool_name: str = '',
    tool_input: Dict = None,
    tool_output: Dict = None,
    success: bool = True,
    confidence: float = None,
    error_message: str = '',
    message_id: int = None,
):
    """Write one agent action to the audit trail.

    Also notifies any admin currently viewing this session's live audit log
    (see AdminAuditConsumer in staff/consumers.py). Broadcasting here — the
    one function every graph node already funnels through — means every
    action_type streams live automatically, with no risk of a future node
    forgetting to wire up its own broadcast call.
    """
    from services.models import AgentAction
    AgentAction.objects.create(
        session_id=session_id,
        action_type=action_type,
        tool_name=tool_name,
        tool_input=tool_input or {},
        tool_output=tool_output or {},
        success=success,
        confidence_at_action=confidence,
        error_message=error_message,
        message_id=message_id,
    )
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(f'agent_audit_{session_id}', {
                'type': 'agent_action_update',
            })
    except Exception:
        # A broadcast failure must never break the agent pipeline itself —
        # the audit row above is already safely written either way.
        pass


def log_tool_error(session_id: str, tool_name: str, error_type: str, error_message: str, retry: bool = False):
    from services.models import ToolError
    ToolError.objects.create(
        session_id=session_id,
        tool_name=tool_name,
        error_type=error_type,
        error_message=error_message,
        retry_attempted=retry,
    )
