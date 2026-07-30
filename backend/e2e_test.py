# -*- coding: utf-8 -*-
"""End-to-end smoke test against the running dev server (throwaway script)."""
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8000'
ok_count = fail_count = 0


def check(name, cond, detail=''):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f'PASS  {name}')
    else:
        fail_count += 1
        print(f'FAIL  {name} — {detail}')


def login(username, password):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login/', json={'username': username, 'password': password})
    r.raise_for_status()
    data = r.json()
    s.headers['Authorization'] = f"Bearer {data['access']}"
    return s, data


# ── 1. Role-based page access ────────────────────────────────────────────────
staff, staff_login = login('staff_demo', 'demo1234!')
check('login response includes user+role', staff_login.get('user', {}).get('role') == 'staff')

r = staff.get(f'{BASE}/staff/', allow_redirects=False)
check('staff can open /staff/', r.status_code == 200, f'status {r.status_code}')
r = staff.get(f'{BASE}/admin-panel/', allow_redirects=False)
check('staff blocked from /admin-panel/', r.status_code == 302, f'status {r.status_code}')

admin, _ = login('admin_demo', 'demo1234!')
r = admin.get(f'{BASE}/admin-panel/', allow_redirects=False)
check('admin can open /admin-panel/', r.status_code == 200, f'status {r.status_code}')
r = admin.get(f'{BASE}/staff/', allow_redirects=False)
check('admin can open /staff/', r.status_code == 200, f'status {r.status_code}')

cust, _ = login('customer_demo', 'demo1234!')
r = cust.get(f'{BASE}/staff/', allow_redirects=False)
check('customer blocked from /staff/', r.status_code == 302, f'status {r.status_code}')

# Staff/admin are dashboard-only — storefront pages redirect them away
r = staff.get(f'{BASE}/', allow_redirects=False)
check('staff redirected from store home', r.status_code == 302 and '/staff/' in r.headers.get('Location', ''), f"{r.status_code} {r.headers.get('Location')}")
r = staff.get(f'{BASE}/products/', allow_redirects=False)
check('staff redirected from products', r.status_code == 302 and '/staff/' in r.headers.get('Location', ''), f"{r.status_code} {r.headers.get('Location')}")
r = admin.get(f'{BASE}/', allow_redirects=False)
check('admin redirected from store home', r.status_code == 302 and '/admin-panel/' in r.headers.get('Location', ''), f"{r.status_code} {r.headers.get('Location')}")
r = admin.get(f'{BASE}/account/', allow_redirects=False)
check('admin redirected from account page', r.status_code == 302 and '/admin-panel/' in r.headers.get('Location', ''), f"{r.status_code} {r.headers.get('Location')}")
r = cust.get(f'{BASE}/', allow_redirects=False)
check('customer still sees store home', r.status_code == 200, f'status {r.status_code}')

# ── 2. Customer chat: AI answers KB question ─────────────────────────────────
r = cust.post(f'{BASE}/api/chat/sessions/new/')
check('new chat session', r.status_code == 201, r.text[:200])
session_id = r.json()['session_id']

r = cust.post(f'{BASE}/api/chat/sessions/{session_id}/send/',
              json={'content': 'What is your return policy for electronics?'})
check('send message (HTTP fallback)', r.status_code == 200, r.text[:200])
data = r.json()
ai = data.get('ai_response')
check('AI produced a response', bool(ai and ai.get('content')), str(data)[:300])
if ai:
    print('       AI said:', ai['content'][:160].replace('\n', ' '))
check('session still AI_ACTIVE', data.get('session_state') == 'AI_ACTIVE', data.get('session_state'))

# ── 3. Handover: explicit human request ──────────────────────────────────────
r = cust.post(f'{BASE}/api/chat/sessions/{session_id}/send/',
              json={'content': 'I want to talk to a human agent'})
data = r.json()
check('handover switches state', data.get('session_state') == 'WAITING_FOR_STAFF', str(data)[:300])
sys_msgs = [m for m in data.get('new_messages', []) if m['sender'] == 'system']
check('customer sees handover system message', bool(sys_msgs), str(data.get('new_messages'))[:300])

def unwrap(resp):
    data = resp.json()
    return data.get('results', data) if isinstance(data, dict) else data


# ── 4. Staff queue → accept → reply → resolve ───────────────────────────────
r = staff.get(f'{BASE}/api/staff/queue/?status=waiting')
cases = unwrap(r)
case = next((c for c in cases if c.get('session_id') == session_id), None)
check('case appears in staff waiting queue', case is not None, str(cases)[:300])

if case:
    r = staff.post(f'{BASE}/api/staff/cases/{case["id"]}/accept/')
    check('staff accepts case', r.status_code == 200, r.text[:200])

    r = staff.post(f'{BASE}/api/staff/cases/{case["id"]}/messages/',
                   json={'content': 'Hello! A human agent here — how can I help?'})
    check('staff POST reply', r.status_code == 201, f'status {r.status_code} {r.text[:200]}')

    r = staff.post(f'{BASE}/api/staff/cases/{case["id"]}/messages/',
                   json={'content': 'internal: customer asked about returns', 'is_internal_note': True})
    check('staff POST internal note', r.status_code == 201, f'status {r.status_code}')

    # Customer sends a message while HUMAN_ACTIVE — AI must NOT reply
    r = cust.post(f'{BASE}/api/chat/sessions/{session_id}/send/', json={'content': 'Thanks, I need help with a return'})
    data = r.json()
    check('AI silent during HUMAN_ACTIVE', data.get('ai_response') is None, str(data)[:200])

    # Customer message list: sees staff reply, not the internal note
    r = cust.get(f'{BASE}/api/chat/sessions/{session_id}/messages/')
    msgs = r.json().get('results', r.json())
    contents = [m['content'] for m in msgs]
    check('customer sees staff reply', any('human agent here' in c for c in contents), str(contents)[-300:])
    check('internal note hidden from customer', not any('internal:' in c for c in contents), str(contents)[-300:])

    r = staff.post(f'{BASE}/api/staff/cases/{case["id"]}/resolve/')
    check('staff resolves case', r.status_code == 200, r.text[:200])
    r = cust.get(f'{BASE}/api/chat/sessions/{session_id}/')
    check('session RESOLVED for customer', r.json().get('state') == 'RESOLVED', r.text[:200])

    r = cust.post(f'{BASE}/api/chat/sessions/{session_id}/feedback/',
                  json={'rating': 'positive', 'reason': ''})
    check('customer submits feedback', r.status_code == 200, r.text[:200])

# ── 5. Admin panel APIs ──────────────────────────────────────────────────────
r = admin.get(f'{BASE}/api/staff/overview/')
check('admin overview API', r.status_code == 200, r.text[:200])
r = admin.get(f'{BASE}/api/knowledge/documents/' if True else '')
check('admin knowledge documents API', r.status_code in (200, 404), f'status {r.status_code}')
r = admin.get(f'{BASE}/api/knowledge/metrics/rag/')
check('admin RAG metrics API', r.status_code in (200, 404), f'status {r.status_code}')

print(f'\n{ok_count} passed, {fail_count} failed')
sys.exit(1 if fail_count else 0)
