import re
from typing import Dict, Any

# customer_id here must ALWAYS come from the authenticated session
# (state['customer_id'] in agents/graph.py), never from LLM-extracted
# entities — unlike order_number, there is no "did this account own this
# order" check to fall back on; trusting an extracted value would let one
# customer read or edit another account.

PHONE_RE = re.compile(r'^\+?[0-9][0-9\-\s]{6,19}$')


def get_account_profile(customer_id: int) -> Dict[str, Any]:
    """Tool — category: 'account', read-only.

    Returns the caller's OWN profile only — no email/username/password
    fields beyond what's already visible to the customer in their own
    account settings page.
    """
    from accounts.models import User
    try:
        user = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        return {'tool': 'get_account_profile', 'success': False, 'error': 'Account not found.'}

    return {
        'tool': 'get_account_profile',
        'success': True,
        'username': user.username,
        'full_name': user.get_full_name() or user.username,
        'email': user.email,
        'phone': user.phone or '(not set)',
        'member_since': user.created_at.strftime('%B %Y'),
    }


def update_account_phone(customer_id: int, new_phone: str) -> Dict[str, Any]:
    """Tool — category: 'account', the only self-service EDIT this chatbot
    exposes. Deliberately limited to phone number — email/username changes
    affect login/identity and are left to the account settings page or
    staff, not a chat message, since a compromised or spoofed chat session
    changing those would be a much bigger blast radius than a phone number.
    """
    new_phone = (new_phone or '').strip()
    if not PHONE_RE.match(new_phone):
        return {
            'tool': 'update_account_phone',
            'success': False,
            'error': 'That doesn\'t look like a valid phone number.',
        }

    from accounts.models import User
    try:
        user = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        return {'tool': 'update_account_phone', 'success': False, 'error': 'Account not found.'}

    user.phone = new_phone
    user.save(update_fields=['phone'])
    return {
        'tool': 'update_account_phone',
        'success': True,
        'phone': new_phone,
    }
