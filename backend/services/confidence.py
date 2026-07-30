from django.conf import settings


def calculate_confidence(
    rag_relevance: float = 0.0,
    has_approved_evidence: bool = False,
    metadata_match: bool = False,
    tool_success: bool = False,
    entity_completeness: float = 0.0,
    verification_passed: bool = False,
    safety_check_passed: bool = True,
) -> float:
    """
    Deterministic confidence formula (not LLM self-confidence):
    Confidence = (RAG relevance × 0.30) + (Approved evidence × 0.15) +
                 (Metadata match × 0.10) + (Tool success × 0.15) +
                 (Entity completeness × 0.10) + (Verification × 0.15) +
                 (Safety check × 0.05)
    """
    score = (
        rag_relevance * 0.30
        + (0.15 if has_approved_evidence else 0.0)
        + (0.10 if metadata_match else 0.0)
        + (0.15 if tool_success else 0.0)
        + entity_completeness * 0.10
        + (0.15 if verification_passed else 0.0)
        + (0.05 if safety_check_passed else 0.0)
    )
    return round(min(max(score, 0.0), 1.0), 3)


def get_confidence_band(confidence: float) -> str:
    HIGH = getattr(settings, 'CONFIDENCE_HIGH', 0.80)
    MEDIUM = getattr(settings, 'CONFIDENCE_MEDIUM', 0.65)
    if confidence >= HIGH:
        return 'HIGH'
    if confidence >= MEDIUM:
        return 'MEDIUM'
    return 'LOW'
