from typing import Dict, Any

# Return rules: (purchase_channel, product_category) → max_days.
# Numbers match the Return & Refund Policy KB doc exactly — that doc states
# a single 30-day window for "most items" with electronics called out as the
# one exception (14 days), and never mentions purchase channel affecting the
# window at all. This used to have shorter, unstated in-store windows here
# that didn't exist anywhere in the actual policy text — a customer asking
# generally ("what's your return policy for electronics?") got a different
# answer via RAG than one asking about a specific in-store order got from
# this tool, for the exact same policy. Channel is kept as a dict dimension
# (rather than dropped) only so purchase_channel stays a meaningful, tracked
# input if a real channel-based rule is ever introduced.
RETURN_RULES = {
    ('online', 'fashion'): 30,
    ('online', 'electronics'): 14,
    ('online', 'accessories'): 30,
    ('online', 'books'): 30,
    ('online', 'default'): 30,
    ('in_store', 'fashion'): 30,
    ('in_store', 'electronics'): 14,
    ('in_store', 'accessories'): 30,
    ('in_store', 'books'): 30,
    ('in_store', 'default'): 30,
}

# 'clothing' is accepted as a synonym for the real store.Category 'fashion' —
# the LLM sometimes describes items that way regardless of the exact category name.
CATEGORY_ALIASES = {'clothing': 'fashion'}

NON_RETURNABLE_CATEGORIES = ['hygiene', 'customised', 'digital', 'food']
REQUIRE_STAFF_REVIEW_STATUSES = ['dispatched', 'out_for_delivery']
# An order that hasn't shipped yet (cancellation intent, not a real "return")
# should never be judged against the day-window return rules below.
NOT_YET_SHIPPED_STATUSES = ['processing', 'confirmed']


_ALREADY_SHIPPED_CANCEL_STATUSES = ['dispatched', 'out_for_delivery']
_TERMINAL_STATUSES = ['cancelled', 'returned']


def check_cancellation_eligibility(order_number: str, customer_id: int) -> Dict[str, Any]:
    """Tool — category: 'return', cancellation-specific path.

    A cancellation question ("can I cancel my order?") is about whether the
    order has SHIPPED yet, not about a day-since-purchase return window —
    those only matter once the customer already has the item in hand. Using
    check_return_eligibility's day-window math for a not-yet-shipped order
    was answering a different question than the one asked (and, worse, using
    a guessed/defaulted days_since_purchase when the real order record was
    right there). This looks the real order up and reads its actual status
    and precomputed can_cancel flag instead of re-deriving anything.
    """
    from store.models import MockOrder

    order_number = (order_number or '').strip().lstrip('#').strip()
    if not order_number:
        return {
            'tool': 'check_cancellation_eligibility',
            'success': False,
            'error': 'No order number given.',
        }

    try:
        order = MockOrder.objects.get(order_number__iexact=order_number, customer_id=customer_id)
    except MockOrder.DoesNotExist:
        return {
            'tool': 'check_cancellation_eligibility',
            'success': False,
            'error': 'Order not found or does not belong to this customer.',
        }

    if order.status in _TERMINAL_STATUSES:
        return {
            'tool': 'check_cancellation_eligibility',
            'success': True,
            'eligible': False,
            'order_status': order.status,
            'reason': f'This order is already {order.status} — there\'s nothing left to cancel.',
            'requires_staff_review': False,
        }

    if order.status in _ALREADY_SHIPPED_CANCEL_STATUSES:
        return {
            'tool': 'check_cancellation_eligibility',
            'success': True,
            'eligible': False,
            'order_status': order.status,
            'reason': f'This order has already {order.status.replace("_", " ")}, so it can no longer be cancelled — it would need to be returned once delivered instead.',
            'requires_staff_review': False,
        }

    if order.status == MockOrder.Status.DELIVERED:
        return {
            'tool': 'check_cancellation_eligibility',
            'success': True,
            'eligible': False,
            'order_status': order.status,
            'reason': 'This order has already been delivered, so it can\'t be cancelled — it can only be returned instead.',
            'requires_staff_review': False,
        }

    # processing / confirmed — hasn't shipped yet, matches can_cancel on the record.
    return {
        'tool': 'check_cancellation_eligibility',
        'success': True,
        'eligible': order.can_cancel,
        'order_status': order.status,
        'reason': (
            'Order hasn\'t shipped yet, so it can be cancelled.' if order.can_cancel
            else 'This order can\'t be cancelled at this stage — please contact support for details.'
        ),
        'requires_staff_review': False,
    }


def _evaluate_return(
    purchase_channel: str,
    product_category: str,
    days_since_purchase: int,
    order_status: str,
    tool_name: str,
) -> Dict[str, Any]:
    product_category_lower = (product_category or '').lower()

    # Not yet shipped — this is a cancellation, not a "return": the item hasn't
    # left the warehouse, so neither the day-window rules nor the
    # non-returnable-category rule (which exist to govern items already in the
    # customer's hands) apply.
    if order_status in NOT_YET_SHIPPED_STATUSES:
        return {
            'tool': tool_name,
            'success': True,
            'eligible': True,
            'reason': "Order hasn't shipped yet, so it can be cancelled without a return.",
            'requires_staff_review': False,
        }

    # Non-returnable
    if any(cat in product_category_lower for cat in NON_RETURNABLE_CATEGORIES):
        return {
            'tool': tool_name,
            'success': True,
            'eligible': False,
            'reason': f'{product_category} items are non-returnable.',
            'requires_staff_review': False,
        }

    channel = purchase_channel.lower() if purchase_channel else 'online'
    normalized_category = CATEGORY_ALIASES.get(product_category_lower, product_category_lower)
    category_key = normalized_category if normalized_category in ['fashion', 'electronics', 'accessories', 'books'] else 'default'
    max_days = RETURN_RULES.get((channel, category_key), RETURN_RULES.get((channel, 'default'), 14))

    # Dispatched / out for delivery — can't confirm eligibility for RIGHT NOW
    # (the item hasn't arrived, so there's nothing to inspect yet), but the
    # policy window that WILL apply once it's delivered is fully known and
    # not something staff need to weigh in on — answering "will I be able to
    # return it once it arrives?" doesn't require a human at all, only "is my
    # in-hand item eligible right now?" would. Surfacing max_days here lets
    # generate_response give a real, forward-looking policy answer instead of
    # a placeholder "staff will review" line that overpromises an escalation
    # that isn't actually happening.
    if order_status in REQUIRE_STAFF_REVIEW_STATUSES:
        return {
            'tool': tool_name,
            'success': True,
            'eligible': None,
            'max_return_days': max_days,
            'reason': (
                f"Order hasn't arrived yet, so eligibility can't be confirmed until then — but once it's "
                f"delivered, our standard {max_days}-day return window applies from the delivery date."
            ),
            'requires_staff_review': False,
        }

    eligible = days_since_purchase <= max_days
    return {
        'tool': tool_name,
        'success': True,
        'eligible': eligible,
        'days_since_purchase': days_since_purchase,
        'max_return_days': max_days,
        'reason': (
            f'Within {max_days}-day return window.' if eligible
            else f'Outside {max_days}-day return window ({days_since_purchase} days elapsed).'
        ),
        'requires_staff_review': False,
    }


def check_return_eligibility(
    purchase_channel: str,
    product_category: str,
    days_since_purchase: int,
    order_status: str = 'delivered',
    product_name: str = '',
) -> Dict[str, Any]:
    """Tool — category: 'return', general-policy path (no specific order on
    hand, or the order lookup failed) — relies on LLM-extracted/guessed
    entities. Prefer check_return_eligibility_for_order whenever an order
    number is available; see its docstring for why.
    """
    return _evaluate_return(purchase_channel, product_category, days_since_purchase,
                             order_status, 'check_return_eligibility')


def check_return_eligibility_for_order(order_number: str, customer_id: int, product_name: str = '') -> Dict[str, Any]:
    """Tool — category: 'return', order-grounded path.

    Once the customer has given (or already gave, earlier in the
    conversation) an order number, there's a real MockOrder/MockOrderItem
    record with the actual purchase_channel, days_since_purchase, category,
    and status already on it — asking the customer to re-supply those by
    hand (and re-ask for the order number a second time) was both redundant
    and strictly less accurate than just reading the record, exactly the
    same problem check_cancellation_eligibility already solved for
    cancellations specifically. This is the return/refund equivalent.
    """
    from store.models import MockOrder

    order_number = (order_number or '').strip().lstrip('#').strip()
    if not order_number:
        return {
            'tool': 'check_return_eligibility_for_order',
            'success': False,
            'error': 'No order number given.',
        }

    try:
        order = MockOrder.objects.prefetch_related('items__product__category').get(
            order_number__iexact=order_number, customer_id=customer_id,
        )
    except MockOrder.DoesNotExist:
        return {
            'tool': 'check_return_eligibility_for_order',
            'success': False,
            'error': 'Order not found or does not belong to this customer.',
        }

    items = list(order.items.all())
    item = None
    if product_name:
        product_name_lower = product_name.lower()
        item = next((i for i in items if product_name_lower in i.product_name.lower()), None)
    if item is None:
        item = items[0] if items else None

    if item is None:
        return {
            'tool': 'check_return_eligibility_for_order',
            'success': False,
            'error': 'No items found on this order.',
        }

    category = item.product.category.slug if (item.product and item.product.category) else 'default'
    result = _evaluate_return(
        purchase_channel=item.purchase_channel,
        product_category=category,
        days_since_purchase=item.days_since_purchase,
        order_status=order.status,
        tool_name='check_return_eligibility_for_order',
    )
    result['order_number'] = order.order_number
    result['order_status'] = order.status
    result['product_name'] = item.product_name
    return result
