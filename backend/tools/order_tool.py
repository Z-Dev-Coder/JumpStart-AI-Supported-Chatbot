from typing import Dict, Any


# Mock carrier tracking detail, keyed by MockOrder.tracking_number.
# Real carrier APIs aren't wired up for this prototype — this stands in for
# the richer status/location/delay info a live tracking API would return.
DELIVERY_DATA = {
    "BD99281733": {
        "status": "In Transit",
        "last_location": "Chicago Sorting Hub",
        "last_update": "2 days ago",
        "estimated_delivery": "Tomorrow",
        "delay_reason": "High volume at sorting facility",
    },
    "DL44729103": {
        "status": "Delivered",
        "last_location": "Delivered to door",
        "last_update": "On time",
        "estimated_delivery": "Delivered",
        "delay_reason": None,
    },
    "EK556612309": {
        "status": "In Transit",
        "last_location": "Dallas Distribution Center",
        "last_update": "1 day ago",
        "estimated_delivery": "2 days",
        "delay_reason": "Weather delay at distribution center",
    },
    "BD10293847": {
        "status": "Out for Delivery",
        "last_location": "Denver Hub",
        "last_update": "3 hours ago",
        "estimated_delivery": "Today",
        "delay_reason": None,
    },
    "DL88103742": {
        "status": "Delivered",
        "last_location": "Delivered to door",
        "last_update": "On time",
        "estimated_delivery": "Delivered",
        "delay_reason": None,
    },
    "BD77412390": {
        "status": "Return In Transit",
        "last_location": "Dallas Return Hub",
        "last_update": "6 hours ago",
        "estimated_delivery": "Refund after inspection",
        "delay_reason": None,
    },
}


def _order_status_payload(order) -> Dict[str, Any]:
    items = [
        {
            'product_name': item.product_name,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'purchase_channel': item.purchase_channel,
            'days_since_purchase': item.days_since_purchase,
        }
        for item in order.items.all()
    ]
    return {
        'tool': 'check_order_status',
        'success': True,
        'order_number': order.order_number,
        'status': order.status,
        'estimated_delivery': str(order.estimated_delivery) if order.estimated_delivery else None,
        'tracking_number': order.tracking_number,
        'can_cancel': order.can_cancel,
        'can_return': order.can_return,
        'items': items,
        'total_amount': str(order.total_amount),
        'delivery_tracking': DELIVERY_DATA.get(order.tracking_number),
    }


_NOT_FOUND = {
    'tool': 'check_order_status',
    'success': False,
    'error': 'Order not found or does not belong to this customer.',
}


def check_order_status(order_number: str = '', customer_id: int = None, tracking_number: str = '') -> Dict[str, Any]:
    """Tool 2 — category: 'order'.

    Looks the order up by order_number OR tracking_number (whichever the
    customer actually has to hand — a shipping-confirmation email carries a
    courier tracking number, not the JS-XXXX order number, and previously
    there was no way in with only that). Both are matched, customer-scoped —
    a tracking number belonging to someone else's order still returns the
    same generic "not found" message as a nonexistent one.
    """
    from store.models import MockOrder
    from django.db.models import Q

    # The LLM's extraction is inconsistent about whether it keeps a leading
    # "#" the customer typed (e.g. "#JS-2024-011") — sometimes it strips it,
    # sometimes it doesn't. order_number is stored WITHOUT the "#", so an
    # extraction that kept it would silently never match and report a false
    # "not found", even for a real order the customer owns. Normalize here
    # rather than trust the model to be consistent about formatting.
    order_number = (order_number or '').strip().lstrip('#').strip()
    tracking_number = (tracking_number or '').strip().lstrip('#').strip()

    if not order_number and not tracking_number:
        return dict(_NOT_FOUND)

    lookup = Q()
    if order_number:
        lookup |= Q(order_number__iexact=order_number)
    if tracking_number:
        lookup |= Q(tracking_number__iexact=tracking_number)

    try:
        order = MockOrder.objects.select_related('customer').prefetch_related('items').get(
            lookup, customer_id=customer_id,
        )
        return _order_status_payload(order)
    except MockOrder.DoesNotExist:
        return dict(_NOT_FOUND)
    except MockOrder.MultipleObjectsReturned:
        # tracking_number has no unique constraint at the DB level (unlike
        # order_number) — fail safe to the most recent match rather than
        # crashing if seed/demo data ever collides.
        order = MockOrder.objects.filter(lookup, customer_id=customer_id).order_by('-created_at').first()
        return _order_status_payload(order)
