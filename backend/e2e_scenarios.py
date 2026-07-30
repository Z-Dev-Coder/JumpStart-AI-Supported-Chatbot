# -*- coding: utf-8 -*-
"""Scenario test suite: AI workflow per plan, admin KB pipeline, staff features."""
import sys
import time
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
        print(f'FAIL  {name} — {str(detail)[:250]}')


def unwrap(resp):
    data = resp.json()
    return data.get('results', data) if isinstance(data, dict) else data


def login(username, password):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login/', json={'username': username, 'password': password})
    r.raise_for_status()
    s.headers['Authorization'] = f"Bearer {r.json()['access']}"
    return s


def new_session(cust):
    return cust.post(f'{BASE}/api/chat/sessions/new/').json()['session_id']


def send(cust, sid, text):
    r = cust.post(f'{BASE}/api/chat/sessions/{sid}/send/', json={'content': text})
    return r.json()


cust = login('customer_demo', 'demo1234!')
staff = login('staff_demo', 'demo1234!')
admin = login('admin_demo', 'demo1234!')

print('\n=== AI WORKFLOW SCENARIOS ===')

# S1: RAG grounded answer
sid = new_session(cust)
d = send(cust, sid, 'What payment methods do you accept?')
resp = (d.get('ai_response') or {}).get('content', '')
check('S1 RAG: payment answer grounded', 'visa' in resp.lower() or 'paypal' in resp.lower(), resp[:200])
check('S1 RAG: stays AI_ACTIVE', d.get('session_state') == 'AI_ACTIVE', d.get('session_state'))
print('      >', resp[:140].replace('\n', ' '))

# S2: Order-status tool
sid = new_session(cust)
d = send(cust, sid, 'Where is my order JS-2024-002?')
resp = (d.get('ai_response') or {}).get('content', '')
check('S2 order tool: mentions status/tracking', any(w in resp.lower() for w in ['dispatch', 'shipped', 'on its way', 'tracking', 'transit']), resp[:250])
print('      >', resp[:140].replace('\n', ' '))

# S3: Clarification for missing order number
sid = new_session(cust)
d = send(cust, sid, 'Can you check the status of my order?')
resp = (d.get('ai_response') or {}).get('content', '')
check('S3 clarification: asks a question, no handover',
      d.get('session_state') == 'AI_ACTIVE' and '?' in resp, f"state={d.get('session_state')} resp={resp[:200]}")
print('      >', resp[:140].replace('\n', ' '))

# S4: Product search tool
sid = new_session(cust)
d = send(cust, sid, 'Do you sell Sony noise cancelling headphones?')
resp = (d.get('ai_response') or {}).get('content', '')
check('S4 product tool: mentions the product', 'sony' in resp.lower() or 'wh-1000' in resp.lower(), resp[:250])
print('      >', resp[:140].replace('\n', ' '))

# S5: Sensitive issue (refund approval) → handover
sid_refund = new_session(cust)
d = send(cust, sid_refund, 'I demand a refund for my headphones right now, please approve it')
check('S5 sensitive refund: escalates to human', d.get('session_state') == 'WAITING_FOR_STAFF', str(d)[:250])

# S6: No approved evidence → handover
sid = new_session(cust)
d = send(cust, sid, 'Do you offer pet grooming services at your stores?')
check('S6 out-of-scope: escalates (no evidence)', d.get('session_state') == 'WAITING_FOR_STAFF', str(d)[:250])

# S7: Frustrated complaint → handover with HIGH priority at top of queue
sid_angry = new_session(cust)
d = send(cust, sid_angry, 'This is absolutely terrible! My order arrived broken and I am furious with your useless service!')
check('S7 frustrated: escalates to human', d.get('session_state') == 'WAITING_FOR_STAFF', str(d)[:250])

r = staff.get(f'{BASE}/api/staff/queue/?status=waiting')
queue = unwrap(r)
angry_case = next((c for c in queue if c['session_id'] == sid_angry), None)
check('S7 frustrated case exists in queue', angry_case is not None, str(queue)[:200])
if angry_case:
    check('S7 frustrated case priority=high', angry_case['priority'] == 'high', angry_case)
    top_high = [c for c in queue if c['priority'] == 'high']
    check('S7 high-priority cases sorted to top', queue.index(angry_case) < len(top_high), [(c['id'], c['priority']) for c in queue])

# S8: Explicit human request (no RAG needed)
sid = new_session(cust)
d = send(cust, sid, 'I want to talk to a human agent')
check('S8 explicit request: escalates', d.get('session_state') == 'WAITING_FOR_STAFF', str(d)[:250])

# S9: Conversation state + audit trail recorded
r = cust.get(f'{BASE}/api/chat/sessions/{sid_angry}/')
check('S9 session retrievable with state', r.status_code == 200 and r.json().get('state') == 'WAITING_FOR_STAFF', r.text[:200])

# S10: Small talk must never escalate — greeting is answered with the customer's name
sid = new_session(cust)
d = send(cust, sid, 'hi')
resp = (d.get('ai_response') or {}).get('content', '')
check('S10 "hi" gets greeting, no handover',
      d.get('session_state') == 'AI_ACTIVE' and 'Alex' in resp, f"state={d.get('session_state')} resp={resp[:200]}")
print('      >', resp[:140].replace('\n', ' '))
d = send(cust, sid, 'hey')
resp = (d.get('ai_response') or {}).get('content', '')
check('S10 "hey" gets greeting, no handover', d.get('session_state') == 'AI_ACTIVE' and 'Hello' in resp, f"state={d.get('session_state')} resp={resp[:150]}")
d = send(cust, sid, 'thanks')
resp = (d.get('ai_response') or {}).get('content', '')
check('S10 "thanks" acknowledged, no handover', d.get('session_state') == 'AI_ACTIVE' and 'welcome' in resp.lower(), f"state={d.get('session_state')} resp={resp[:150]}")

# S11: Chatbot is customer-only
r = staff.post(f'{BASE}/api/chat/sessions/new/')
check('S11 staff blocked from starting chat', r.status_code == 403, f'status {r.status_code} {r.text[:150]}')
r = admin.post(f'{BASE}/api/chat/sessions/new/')
check('S11 admin blocked from starting chat', r.status_code == 403, f'status {r.status_code} {r.text[:150]}')

print('\n=== ADMIN: KNOWLEDGE BASE UPLOAD PIPELINE ===')

# A1: Upload a new policy document (multipart, like the dashboard does)
content = (
    'JumpStart Student Discount Policy (Version 1.0)\n\n'
    'JumpStart offers a student discount of 12 percent on all fashion and books purchases. '
    'Students must verify their status with a valid student ID or university email at checkout using the code STUDENT12. '
    'The student discount cannot be combined with other promotional codes. '
    'It applies to both online and in-store purchases. '
    'The discount is available all year round, including sale periods, but excludes gift cards and electronics.'
)
files = {'file': ('student_discount_policy.txt', content.encode('utf-8'), 'text/plain')}
r = admin.post(f'{BASE}/api/knowledge/documents/upload/',
               files=files, data={'title': 'JumpStart Student Discount Policy', 'topic': 'promotions'})
check('A1 admin uploads document', r.status_code == 201, r.text[:250])
doc = r.json()
doc_id = doc.get('id')
check('A1 uploaded doc is pending', doc.get('status') == 'pending', doc)
check('A1 text extracted on upload', 'STUDENT12' in (doc.get('extracted_text') or ''), str(doc)[:250])

# A2: Pending doc must NOT be used by the AI
sid = new_session(cust)
d = send(cust, sid, 'Do you offer a student discount?')
resp = ((d.get('ai_response') or {}).get('content', '')).lower()
check('A2 pending doc not used by AI', 'student12' not in resp and '12 percent' not in resp and '12%' not in resp,
      f"state={d.get('session_state')} resp={resp[:200]}")

# A3: Approve → background embedding generates chunks
r = admin.patch(f'{BASE}/api/knowledge/documents/{doc_id}/approve/')
check('A3 admin approves document', r.status_code == 200, r.text[:200])
chunks = 0
for _ in range(30):
    time.sleep(2)
    r = admin.get(f'{BASE}/api/knowledge/documents/{doc_id}/')
    dd = r.json()
    chunks = dd.get('chunk_count', dd.get('chunks', 0)) or 0
    if isinstance(chunks, list):
        chunks = len(chunks)
    if chunks:
        break
check('A3 embeddings generated after approval', chunks and int(chunks) > 0, f'chunk_count={chunks} doc={str(dd)[:200]}')

# A4: AI now answers from the new document
sid = new_session(cust)
d = send(cust, sid, 'Do you offer a student discount?')
resp = ((d.get('ai_response') or {}).get('content', ''))
check('A4 AI uses newly approved doc', 'student12' in resp.lower() or '12' in resp,
      f"state={d.get('session_state')} resp={resp[:250]}")
print('      >', resp[:160].replace('\n', ' '))

# A5: Disable → AI stops using it
r = admin.patch(f'{BASE}/api/knowledge/documents/{doc_id}/disable/')
check('A5 admin disables document', r.status_code == 200, r.text[:200])
sid = new_session(cust)
d = send(cust, sid, 'Do you offer a student discount?')
resp = ((d.get('ai_response') or {}).get('content', '')).lower()
check('A5 disabled doc no longer used', 'student12' not in resp and '12 percent' not in resp and '12%' not in resp,
      f"state={d.get('session_state')} resp={resp[:200]}")

# A6: Admin dashboard data endpoints
r = admin.get(f'{BASE}/api/staff/queue/?state=RESOLVED')
cases = unwrap(r)
check('A6 cases tab: ?state=RESOLVED returns resolved cases',
      r.status_code == 200 and all(c['session_state'] == 'RESOLVED' for c in cases), str(cases)[:200])

r = admin.get(f'{BASE}/api/chat/sessions/')
sessions = unwrap(r)
check('A6 audit tab: admin sees all sessions', r.status_code == 200 and len(sessions) > 0, r.text[:200])
r = admin.get(f'{BASE}/api/chat/sessions/?q=customer_demo')
filtered = unwrap(r)
check('A6 audit tab: q filter works', r.status_code == 200 and len(filtered) > 0, r.text[:200])
if sessions:
    r = admin.get(f"{BASE}/api/chat/sessions/{sessions[0]['id']}/messages/")
    check('A6 audit tab: admin reads session messages', r.status_code == 200, r.text[:200])

r = admin.get(f'{BASE}/api/staff/overview/')
ov = r.json()
check('A6 overview: sentiment + trend included',
      'sentiment_negative' in ov and len(ov.get('handover_trend_7d', [])) == 7, str(ov)[:300])

r = admin.get(f'{BASE}/api/knowledge/rag-metrics/')
check('A6 RAG metrics: retrievals now logged', r.json().get('total_retrievals', 0) > 0, r.text[:200])

# A7: Feedback reviewed flow
r = admin.get(f'{BASE}/api/knowledge/feedback/')
fbs = r.json()
check('A7 feedback list loads', r.status_code == 200, r.text[:200])
if fbs:
    fid = fbs[0]['id']
    r = admin.patch(f'{BASE}/api/knowledge/feedback/{fid}/reviewed/')
    check('A7 mark feedback reviewed', r.status_code == 200, r.text[:200])

# A8: Staff cannot access admin knowledge APIs
r = staff.get(f'{BASE}/api/knowledge/documents/')
check('A8 staff blocked from knowledge admin API', r.status_code == 403, f'status {r.status_code}')

print('\n=== STAFF FEATURES ===')

# F1: accept up to 3 cases, 4th rejected
r = staff.get(f'{BASE}/api/staff/queue/?status=waiting')
waiting = unwrap(r)
accepted = []
for c in waiting:
    if len(accepted) >= 3:
        break
    rr = staff.post(f"{BASE}/api/staff/cases/{c['id']}/accept/")
    if rr.status_code == 200:
        accepted.append(c)
check('F1 staff accepted 3 cases', len(accepted) == 3, f'accepted={len(accepted)} waiting={len(waiting)}')
r = staff.get(f'{BASE}/api/staff/queue/?status=waiting')
still_waiting = unwrap(r)
if still_waiting:
    rr = staff.post(f"{BASE}/api/staff/cases/{still_waiting[0]['id']}/accept/")
    check('F1 4th accept rejected (3-case limit)', rr.status_code == 400, f'{rr.status_code} {rr.text[:150]}')
else:
    check('F1 4th accept rejected (3-case limit)', False, 'no waiting case left to test with')

# F2: staff sees internal notes in case messages, customer does not (covered earlier)
case = accepted[0]
r = staff.post(f"{BASE}/api/staff/cases/{case['id']}/messages/", json={'content': 'note to team', 'is_internal_note': True})
r = staff.get(f"{BASE}/api/staff/cases/{case['id']}/messages/")
msgs = unwrap(r)
check('F2 staff view includes internal notes', any(m.get('is_internal_note') for m in msgs), str(msgs)[-200:])

# F3: return-to-AI resumes the agent
r = staff.post(f"{BASE}/api/staff/cases/{case['id']}/return-to-ai/")
check('F3 return-to-AI succeeds', r.status_code == 200, r.text[:200])
r = cust.get(f"{BASE}/api/chat/sessions/{case['session_id']}/")
check('F3 session back to AI_ACTIVE', r.json().get('state') == 'AI_ACTIVE', r.text[:200])
d = send(cust, case['session_id'], 'What are your store opening hours?')
resp = (d.get('ai_response') or {}).get('content', '')
check('F3 AI responds again after return', bool(resp), str(d)[:250])
print('      >', resp[:140].replace('\n', ' '))

# F4: resolve remaining accepted cases → resolved tab
for c in accepted[1:]:
    staff.post(f"{BASE}/api/staff/cases/{c['id']}/resolve/")
r = staff.get(f'{BASE}/api/staff/queue/?status=resolved')
resolved = unwrap(r)
check('F4 resolved tab lists resolved cases', len(resolved) >= 2, str(resolved)[:200])

print(f'\n{ok_count} passed, {fail_count} failed')
sys.exit(1 if fail_count else 0)
