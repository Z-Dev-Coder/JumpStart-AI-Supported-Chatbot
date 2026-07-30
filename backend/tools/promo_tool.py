from typing import Dict, Any

# Mirrors the "JumpStart Active Promotions & Discount Codes" KB document
# (knowledge/management/commands/seed_knowledge.py) as a queryable dataset.
# A promo CODE lookup should be an exact match, not a fuzzy RAG similarity
# search — relying on search_knowledge_base for "does WELCOME15 still work?"
# means the answer depends on embedding similarity clearing a threshold,
# which is the wrong kind of uncertainty for something that's either valid
# or it isn't. Real codes/discount-engine integration aren't wired up for
# this prototype — this stands in for that, the same way order_tool.py's
# DELIVERY_DATA stands in for a real carrier tracking API.
PROMO_CODES = {
    "WELCOME15": {
        "discount": "15% off first order",
        "conditions": "New accounts only, minimum spend $20",
        "valid_until": "Ongoing",
    },
    "STUDENT12": {
        "discount": "12% off fashion & books",
        "conditions": "Valid student ID or university email required at checkout",
        "valid_until": "Ongoing",
    },
    "FLASH25": {
        "discount": "25% off selected electronics",
        "conditions": "While stocks last, cannot combine with other codes",
        "valid_until": "Seasonal flash sales only",
    },
    "FREESHIP50": {
        "discount": "Free standard shipping",
        "conditions": "Automatically applied on orders over $50",
        "valid_until": "Ongoing",
    },
    "LOYALTY5": {
        "discount": "$5 reward voucher",
        "conditions": "Redeemed with 100 JumpStart Rewards points",
        "valid_until": "Ongoing, redeemable any time",
    },
    "BIRTHDAY15": {
        "discount": "15% birthday discount",
        "conditions": "JumpStart Rewards members only, valid during birthday month",
        "valid_until": "Ongoing",
    },
}


def check_promo_code(code: str) -> Dict[str, Any]:
    """Tool — category: 'promo'.

    When the agent should call this: the customer names a SPECIFIC promo/
    discount code (e.g. "does WELCOME15 still work?", "can I use FLASH25?").
    Do NOT use this for a general "what discounts do you have" question with
    no specific code named — that's 'knowledge' + topic=promotions instead,
    since there's no single code to look up.

    Params:
        code — the code as given, case/whitespace-insensitive
               (e.g. "welcome15" and " WELCOME15 " both match).

    Returns on success: code, discount, conditions, valid_until.
    Returns on failure: success=False, error — deliberately the same generic
        message whether the code never existed or was simply mistyped, since
        there's nothing sensitive to distinguish (unlike order lookups, this
        never needs to hide "does this exist" from anyone).
    """
    normalized = (code or '').strip().upper()
    entry = PROMO_CODES.get(normalized)
    if not entry:
        return {
            'tool': 'check_promo_code',
            'success': False,
            'error': f'"{code}" is not a recognised promo code.' if code else 'No promo code was given.',
        }
    return {
        'tool': 'check_promo_code',
        'success': True,
        'code': normalized,
        **entry,
    }
