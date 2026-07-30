from typing import TypedDict, List, Dict, Any, Optional


class SupportState(TypedDict):
    # Input
    session_id: str
    customer_id: int
    message_id: int
    customer_message: str
    # Intent & entities
    intents: List[str]
    customer_goal: str
    entities: Dict[str, Any]
    missing_fields: List[str]
    clarification_attempts: int
    # Planning
    planned_steps: List[str]
    completed_steps: List[str]
    current_step: str
    tool_call_count: int
    suggested_action: str
    # RAG & tools
    retrieved_documents: List[Dict[str, Any]]
    tool_result: Dict[str, Any]
    tools_used: List[str]
    # Response
    response: str
    quick_replies: List[str]
    confidence: float
    confidence_band: str
    sentiment: str
    # Routing
    requires_handover: bool
    handover_reason: str
    requires_clarification: bool
    regeneration_attempts: int
    # Set when a turn OFFERS a handover instead of performing it immediately
    # (see offer_handover_reply) — persisted across the turn boundary so the
    # NEXT message can be interpreted as a yes/no answer to this offer rather
    # than a fresh question. Cleared once resolved either way.
    pending_handover_reason: str
    # Verification
    verification_passed: bool
    safety_passed: bool
    # Error
    error: str
    # Internal working fields — must be declared or LangGraph drops them
    # when merging node output back into the state
    _history: str
    _tool_category: str
    _force_knowledge: bool
    _injection_detected: bool
    _smalltalk: str
    _prior_missing_fields: List[str]
    # True when this turn's entity extraction added at least one genuinely
    # NEW key vs. what was already known — a concrete, objective progress
    # signal for check_missing_fields' stagnation detection, independent of
    # how the LLM itself judges "still missing" (see check_missing_fields'
    # comment for why that self-reported diff isn't reliable enough alone
    # on a smaller/local model).
    _gained_new_entity: bool
    _prior_customer_goal: str
    _prior_pending_handover_reason: str
    # A failed order/tracking lookup's own retry counter — deliberately
    # separate from clarification_attempts (see order_id_retry's docstring
    # comment for why). Persists across turns like clarification_attempts.
    order_lookup_attempts: int
