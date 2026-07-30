import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from django.conf import settings

from .state import SupportState
from .prompts import (
    INTENT_DETECTION_PROMPT,
    RESPONSE_GENERATION_PROMPT, VERIFICATION_PROMPT,
)
from services.confidence import calculate_confidence, get_confidence_band
from services.sentiment import analyse_sentiment
from services.audit import log_agent_action

# Lazy singleton, same pattern as rag/embeddings.py and services/sentiment.py —
# call_llm() used to construct a brand-new client on every single invocation
# (2-3 times per turn); building it once and reusing it avoids paying that
# setup cost repeatedly. max_tokens still varies per call (see call_llm
# below) — it's passed at invoke() time, not baked into the client.
_llm = None
_llm_lock = threading.Lock()


def _get_llm():
    global _llm
    if _llm is None:
        with _llm_lock:
            if _llm is None:
                from langchain_ollama import ChatOllama
                _llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=0.1,
                    # 90s — generous enough for genuine local GPU compute
                    # time on a 6GB card, without the multi-minute hangs
                    # seen when a Colab+ngrok tunnel session degraded after
                    # a browser disconnect (that scenario wanted a SHORTER
                    # timeout, ~60s, to fail fast instead of hanging; local
                    # inference has no tunnel to degrade, so a bit more
                    # headroom here is for real compute time, not network
                    # uncertainty).
                    client_kwargs={'timeout': 90},
                )
    return _llm


def call_llm(prompt: str, session_id: str = '', max_tokens: int = 1024) -> str:
    """Call the configured Ollama LLM and return raw text response.

    max_tokens is a generation cap, not a fixed cost, but the LLM still spends
    time per token generated — the intent/plan/clarification calls only ever
    need a short JSON blob or a one-line question, so capping them tighter
    than the final customer-facing response noticeably cuts per-turn latency.
    """
    llm = _get_llm()
    # ChatOllama doesn't accept num_predict as an invoke()-time kwarg — the
    # underlying ollama client's chat() rejects it outright. It's a real
    # pydantic field on the client instance instead, so set it directly
    # before each call (confirmed working; invoke(**kwargs) raises
    # TypeError: Client.chat() got an unexpected keyword argument
    # 'num_predict').
    llm.num_predict = max_tokens
    try:
        result = llm.invoke(prompt)
    except Exception:
        # One retry — a remote/tunnelled backend can drop a connection
        # transiently (observed: one call failed after 82s, the exact same
        # call succeeded in 53s moments later with no other change). No
        # built-in max_retries on ChatOllama, so it's done by hand here.
        result = llm.invoke(prompt)
    return result.content


def parse_json(text: str) -> Dict:
    """Extract JSON from LLM response.

    Grabs only the FIRST complete, brace-balanced JSON object rather than
    naively slicing from the first '{' to the last '}' — the local model
    occasionally emits two back-to-back JSON blobs in one completion (a
    known small-model quirk), and a first-to-last slice spans across both,
    producing invalid JSON that fails to parse. That failure was silently
    swallowed by the except below and fell back to using the ENTIRE raw
    text (including the second blob) as the customer-facing response.
    Proper brace-depth tracking stops at the first object's closing brace,
    ignoring anything after it.
    """
    start = text.find('{')
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return {}
    return {}


# ─── Node: Validate Input ─────────────────────────────────────────────────────

# Guardrail: common prompt-injection phrasings. Matched messages get a canned
# reply and never reach the LLM or tools.
INJECTION_PATTERNS = [
    'ignore previous instructions', 'ignore all previous instructions',
    'ignore your instructions', 'disregard previous', 'disregard your instructions',
    'reveal your system prompt', 'show your system prompt', 'system prompt',
    'developer mode', 'jailbreak', 'you are no longer', 'new instructions:',
    'override your rules', 'forget your rules',
]


# Small talk handled deterministically — a plain "hi" must never reach RAG
# (no evidence would be found and the customer would be escalated to a human).
SMALLTALK_PHRASES = {
    'greeting': {
        'hi', 'hii', 'hiii', 'hey', 'heyy', 'heyyy', 'hello', 'helo', 'yo',
        'hola', 'greetings', 'sup', 'whats up', "what's up", 'hi there',
        'hey there', 'hello there', 'good morning', 'good afternoon',
        'good evening', 'good day', 'how are you', 'how are you doing',
        'hi jumpstart', 'hello jumpstart',
    },
    'thanks': {
        'thanks', 'thank you', 'thx', 'ty', 'tysm', 'thanks a lot',
        'thank you so much', 'thanks so much', 'ok thanks', 'okay thanks',
        'great thanks', 'perfect thanks', 'thank you very much',
    },
    'bye': {
        'bye', 'goodbye', 'bye bye', 'see you', 'see ya', 'cya',
        'good night', 'goodnight', 'have a nice day',
    },
}


# Plan rule: an explicit request for a person is handled by Django directly
# after validation — no RAG, Groq, or confidence routing involved.
HUMAN_REQUEST_PATTERNS = [
    'talk to a human', 'speak to a human', 'talk to a person', 'speak to a person',
    'talk to an agent', 'speak to an agent', 'human agent', 'real person',
    'live agent', 'human support', 'talk to staff', 'speak to staff',
    'connect me to a human', 'i want a human', 'transfer me to a human',
    'talk to human', 'speak with a human', 'speak with an agent',
]


# Deliberately NOT derived from SMALLTALK_PHRASES by splitting every phrase
# into words — several phrases there ("how are you doing", "whats up") are
# built from common English words ("are", "you", "up", "how") that would
# wrongly flag a genuine short question ("are you up?") as smalltalk if
# used for word-level matching. This list is only the atomic, unambiguous
# greeting/thanks/bye tokens — words that are NEVER part of a real question.
_SMALLTALK_ATOMS = {
    'greeting': {'hi', 'hii', 'hiii', 'hey', 'heyy', 'heyyy', 'hello', 'helo', 'yo', 'hola', 'greetings', 'sup'},
    'thanks': {'thanks', 'thank', 'thx', 'ty', 'tysm'},
    'bye': {'bye', 'goodbye', 'cya'},
}


def _detect_smalltalk(message: str) -> str:
    import re
    normalized = re.sub(r"[^a-z'\s]", '', message.lower())
    words = normalized.split()
    if not words or len(words) > 5:
        return ''
    normalized = ' '.join(words)
    for kind, phrases in SMALLTALK_PHRASES.items():
        if normalized in phrases:
            return kind
    # Fall back to word-level matching against ONLY the atomic tokens above —
    # catches combinations of known greeting/thanks/bye words that aren't a
    # literal phrase in the set above (e.g. "hi hello", "hey hi there")
    # without needing every possible combination spelled out explicitly,
    # while staying safe against false-positiving on real short questions.
    word_set = set(words)
    for kind, atoms in _SMALLTALK_ATOMS.items():
        if word_set <= atoms:
            return kind
    return ''


def validate_input(state: SupportState) -> SupportState:
    msg = state.get('customer_message', '').strip()
    if not msg:
        state['error'] = 'Empty message.'
        state['requires_handover'] = False
        return state
    if len(msg) > 2000:
        state['customer_message'] = msg[:2000]
        msg = state['customer_message']
    lower = msg.lower()
    state['_injection_detected'] = any(p in lower for p in INJECTION_PATTERNS)
    state['_smalltalk'] = _detect_smalltalk(msg)
    if any(p in lower for p in HUMAN_REQUEST_PATTERNS):
        state['requires_handover'] = True
        state['handover_reason'] = 'explicit_request'
        state['customer_goal'] = msg
        state['_smalltalk'] = ''  # a human request beats a greeting prefix
    state['error'] = ''
    return state


# ─── Node: Small Talk Reply ───────────────────────────────────────────────────

def smalltalk_reply(state: SupportState) -> SupportState:
    from django.contrib.auth import get_user_model
    name = ''
    try:
        user = get_user_model().objects.get(id=state['customer_id'])
        name = user.first_name or user.username
    except Exception:
        pass
    greeting_name = f' {name}' if name else ''

    kind = state.get('_smalltalk', 'greeting')
    if kind == 'thanks':
        state['response'] = (
            f"You're very welcome{greeting_name}! Is there anything else I can help you with?"
        )
        state['quick_replies'] = ['Track my order', 'Return a product', 'No, that\'s all']
    elif kind == 'bye':
        state['response'] = (
            f"Thanks for chatting with JumpStart{greeting_name} — have a great day! "
            "Feel free to come back any time. 👋"
        )
        state['quick_replies'] = []
    else:
        state['response'] = (
            f"Hello{greeting_name}! 👋 Welcome to JumpStart support. "
            "I can help you track orders, check our return and delivery policies, "
            "find products, and more. What can I do for you today?"
        )
        state['quick_replies'] = ['Track my order', 'Return a product', 'Talk to a human']

    state['intents'] = ['small_talk']
    state['confidence'] = 1.0
    state['confidence_band'] = 'HIGH'
    log_agent_action(state['session_id'], 'smalltalk_reply',
                     tool_output={'kind': kind}, message_id=state.get('message_id'))
    return state


# ─── Node: Injection Guard Reply ──────────────────────────────────────────────

def guard_reply(state: SupportState) -> SupportState:
    state['response'] = (
        'I can only help with JumpStart shopping and support questions — '
        'such as orders, deliveries, returns, payments, or products. '
        'How can I help you with one of those?'
    )
    state['quick_replies'] = ['Track my order', 'Return a product', 'Talk to a human']
    state['confidence'] = 0.0
    state['confidence_band'] = 'LOW'
    log_agent_action(state['session_id'], 'injection_guard',
                     tool_output={'blocked': True}, message_id=state.get('message_id'))
    return state
    

# ─── Node: Load Conversation History ─────────────────────────────────────────

def load_history(state: SupportState) -> SupportState:
    from chatbot.models import ChatMessage
    recent = ChatMessage.objects.filter(
        session_id=state['session_id']
    ).order_by('-created_at')[:10]
    history = '\n'.join(
        f"{m.sender.upper()}: {m.content}" for m in reversed(recent)
    )
    state['_history'] = history
    return state


# ─── Node: Detect Intent & Entities ──────────────────────────────────────────

def detect_intent(state: SupportState) -> SupportState:
    prompt = INTENT_DETECTION_PROMPT.format(
        message=state['customer_message'],
        history=state.get('_history', ''),
        prior_missing_fields=state.get('_prior_missing_fields', []),
        prior_customer_goal=state.get('_prior_customer_goal', ''),
    )
    # Local sentiment analysis doesn't depend on anything the LLM produces —
    # run it concurrently with the LLM call (a network round-trip) instead
    # of after it, so its time is hidden under the network latency rather
    # than adding to it.
    with ThreadPoolExecutor(max_workers=2) as executor:
        llm_future = executor.submit(
            # 300 was too tight for a genuinely complex message (multiple
            # simultaneous intents + a full entity dict) — measured at ~400
            # completion tokens needed; 500 leaves real headroom.
            call_llm, prompt, state['session_id'], 500
        )
        sentiment_future = executor.submit(analyse_sentiment, state['customer_message'])
        try:
            raw = llm_future.result()
            parsed = parse_json(raw)
            state['intents'] = parsed.get('intents', ['general_faq'])
            # Deterministic backstop: on noisy/misspelled input the LLM
            # sometimes emits a near-miss variant of a canonical intent name
            # instead of the exact string from the prompt's list (confirmed:
            # "promotion" instead of "promotions" for a price-drop question).
            # Exact-match set membership checks elsewhere (_KNOWLEDGE_INTENTS
            # etc.) then silently treat the intent as absent, which let
            # order_tracking win unconditionally and misroute the question to
            # an order lookup instead of the knowledge base. Normalize known
            # near-misses to the canonical name right after parsing so every
            # downstream check sees the same intent set the LLM meant.
            _INTENT_ALIASES = {'promotion': 'promotions'}
            state['intents'] = [_INTENT_ALIASES.get(i, i) for i in state['intents']]
            # Deterministic backstop: "how do I talk to a real person" is a
            # question ABOUT the process, not a request to escalate right
            # now — the LLM has repeatedly misclassified this as an
            # immediate human_request/explicit_human_request regardless of
            # the prompt instruction saying otherwise. A "how"/"can I"
            # question about reaching a human is informational (general_faq,
            # the KB has a direct answer) and should never itself trigger
            # escalation, independent of whether the model gets the
            # distinction right.
            lower_msg = state['customer_message'].lower()
            asks_how_to_reach_human = (
                any(p in lower_msg for p in ('how do i', 'how can i', 'how to', 'is there a way'))
                and any(w in lower_msg for w in ('human', 'agent', 'real person', 'someone', 'staff'))
            )
            if asks_how_to_reach_human:
                state['intents'] = [i for i in state['intents'] if i != 'human_request'] or ['general_faq']
                parsed['explicit_human_request'] = False
            state['customer_goal'] = parsed.get('customer_goal', state['customer_message'])
            # Deterministic backstop for the same hallucination the prompt's
            # "don't guess on uncertainty" rule already targets but doesn't
            # reliably prevent on a smaller model: if the customer's message
            # itself is a vague non-answer, discard whatever entities the
            # LLM extracted THIS turn entirely, rather than trusting it to
            # correctly recognize "sometime recently" isn't a real
            # days_since_purchase value. Confirmed reproducible — this exact
            # phrase reset the clarification-exhaustion counter and let a
            # customer stall past MAX_CLARIFICATION_ATTEMPTS indefinitely.
            _UNCERTAINTY_PHRASES = (
                'not sure', "don't know", 'dont know', "don't remember", 'dont remember',
                'no idea', 'not certain', 'unsure',
            )
            lower_msg_uncertain = state['customer_message'].lower()
            if any(p in lower_msg_uncertain for p in _UNCERTAINTY_PHRASES):
                parsed['entities'] = {}
            # Deterministic backstop: promo_code feeds an EXACT-match lookup
            # tool (check_promo_code) that routes straight past RAG entirely
            # once it's set (see _decide_tool_category) — so a hallucinated
            # value here is worse than most entities: it produces a fully
            # confident, fully wrong answer instead of a low-confidence one.
            # Confirmed bug: "Is there a discount code for students right
            # now?" (no code named at all) got promo_code='WELCOME15'
            # invented out of thin air, and since WELCOME15 happens to be a
            # real code, check_promo_code succeeded and confidently answered
            # about the wrong promotion entirely. Only trust this entity when
            # the exact code literally appears in the customer's own message.
            promo_code = (parsed.get('entities') or {}).get('promo_code')
            if promo_code and promo_code.upper() not in state['customer_message'].upper():
                parsed['entities'].pop('promo_code', None)
            # Merge over entities carried from earlier turns (clarification answers)
            # Only truthy values count as "gained" — the model sometimes emits
            # a key with an empty string ('') rather than omitting it, which
            # is functionally still "nothing given" and shouldn't read as
            # progress (same reasoning as the missing_fields filter below).
            prior_entities = state.get('entities') or {}
            # Confirmed bug: prior_entities carried forward UNCONDITIONALLY,
            # so a stale product_category/issue_type from an earlier, already-
            # answered question (e.g. "do laptops have a shorter return
            # period?") silently leaked into a later, unrelated question
            # ("can I swap a shirt for a bigger size?") — contaminating that
            # turn's KB retrieval query and tripping a false "sensitive issue"
            # classification. _prior_missing_fields tells us whether the LAST
            # turn left an open clarification request: if it did, this
            # message is likely answering it and the scoped fields should
            # carry over; if it didn't (the last question was already fully
            # resolved), this is a fresh question and stale scoped fields
            # from the OLD topic must not bleed into it. order_number/
            # tracking_number/promo_code are deliberately NOT scoped here —
            # those refer to a durable real-world entity (an actual order)
            # a customer may reasonably still be discussing turns later.
            if not state.get('_prior_missing_fields'):
                _TOPIC_SCOPED_ENTITY_KEYS = {
                    'product_category', 'purchase_channel', 'days_since_purchase',
                    'issue_type', 'product_name',
                }
                prior_entities = {k: v for k, v in prior_entities.items() if k not in _TOPIC_SCOPED_ENTITY_KEYS}
            prior_entity_keys = {k for k, v in prior_entities.items() if v}
            state['entities'] = {**prior_entities, **parsed.get('entities', {})}
            new_entity_keys = {k for k, v in state['entities'].items() if v}
            state['_gained_new_entity'] = bool(new_entity_keys - prior_entity_keys)
            state['missing_fields'] = [
                f for f in parsed.get('missing_fields', []) if not state['entities'].get(f)
            ]
            state['requires_handover'] = parsed.get('explicit_human_request', False)
            if state['requires_handover']:
                state['handover_reason'] = 'explicit_request'

            state['sentiment'] = sentiment_future.result()
            # A frustrated complaint no longer bypasses straight to a human here —
            # verify_result gives it one real attempt (with an extra confidence
            # penalty) before deciding whether to escalate, same as any other
            # sensitive intent. See verify_result's is_frustrated handling.
            # sentiment isn't part of the LLM's own JSON, and 'entities' in parsed is
            # only this turn's extraction (not merged with prior turns) — log the
            # actual merged state so the admin per-message log shows the full picture.
            log_agent_action(state['session_id'], 'detect_intent',
                              tool_output={**parsed, 'entities': state['entities'], 'sentiment': state['sentiment']},
                              message_id=state.get('message_id'))
        except Exception as e:
            state['intents'] = ['general_faq']
            state['customer_goal'] = state['customer_message']
            state['error'] = str(e)
            # Set the real reason HERE, in the node itself — route_after_intent
            # is a LangGraph conditional-edge function, and edge functions only
            # return a routing decision; any state mutation inside them is
            # silently discarded and never reaches downstream nodes. Setting
            # handover_reason there looked correct but never actually took
            # effect, so offer_handover_reply always saw handover_reason=''
            # and fell back to the generic default message instead of the
            # intended "technical issue" one whenever this LLM call failed
            # (e.g. a Groq rate limit) — exactly the case that needs the
            # clearest explanation, not the vaguest one.
            state['requires_handover'] = True
            state['handover_reason'] = 'tool_failure'
            log_agent_action(state['session_id'], 'detect_intent', success=False,
                              error_message=str(e), message_id=state.get('message_id'))
    return state


# ─── Node: Check Missing Fields ───────────────────────────────────────────────

# Deliberately stricter than rag/retriever.py's normal SIMILARITY_THRESHOLD
# (0.45) — this override skips a clarification question entirely, so it
# should only fire on a strong, near-unambiguous match. A borderline match
# here would silently answer a question no one actually asked instead of
# gathering the details the customer's message genuinely seemed to need.
_KB_OVERRIDE_THRESHOLD = 0.58


_RETURN_ELIGIBILITY_FIELDS = ['product_category', 'purchase_channel', 'days_since_purchase']


_EXCHANGE_SIGNAL_WORDS = ('swap', 'exchange', 'different size', 'different colour', 'different color',
                          'bigger size', 'smaller size')

# Same problem, different shape: "Do laptops and headphones have a shorter
# return period?" names a product category but is asking about the general
# category-level return WINDOW LENGTH (answered unconditionally by the KB's
# per-category return-window rows), not checking eligibility on something the
# customer actually owns. This phrasing scores ~0.57 against the KB — just
# under _KB_OVERRIDE_THRESHOLD (0.58) — so it needs the same narrow keyword
# backstop the exchange case got rather than loosening the shared threshold.
_RETURN_WINDOW_QUERY_WORDS = ('return period', 'return window', 'shorter return', 'longer return',
                              'return policy')


def check_missing_fields(state: SupportState) -> SupportState:
    missing = state.get('missing_fields') or []
    max_attempts = getattr(settings, 'MAX_CLARIFICATION_ATTEMPTS', 2)

    lower_msg = state.get('customer_message', '').lower()

    # Deterministic backstop: on the local model, the LLM's own missing_fields
    # judgment is sometimes just wrong — it reports [] even though the
    # customer's message plainly hasn't given what a return-eligibility check
    # needs (observed non-deterministically on the SAME input across runs,
    # not something more prompt-tuning reliably fixes). Independently
    # re-derive what category this would resolve to; if it's 'return' with
    # no order to fall back on, verify the three required fields are
    # actually present (truthy) before trusting an empty missing list —
    # this doesn't depend on the LLM getting missing_fields right at all.
    #
    # NOTE: this can also introduce a non-empty `missing` where the incoming
    # value was empty — e.g. mid-session, stale entities carried over from an
    # EARLIER unrelated question (like a leftover product_category from a
    # previous turn) can make the LLM's fresh missing_fields look emptier
    # than it should. The keyword overrides below must run AFTER this block,
    # not before, so they see the final `missing` this node settles on rather
    # than a since-superseded snapshot from the top of the function.
    if not missing:
        entities = state.get('entities') or {}
        has_order_id = bool(entities.get('order_number') or entities.get('tracking_number'))
        preview_category = _decide_tool_category(state.get('intents', []), entities)
        if preview_category == 'return' and not has_order_id:
            # A cancellation request needs the actual order record (status,
            # can_cancel) — asking about product_category/purchase_channel/
            # days_since_purchase is meaningless for it and just re-asks
            # questions a real order lookup would answer directly. Only the
            # order number is genuinely required here.
            if 'cancellation' in (state.get('intents') or []):
                missing = ['order_number']
            else:
                missing = [f for f in _RETURN_ELIGIBILITY_FIELDS if not entities.get(f)]
            if missing:
                state['missing_fields'] = missing
    else:
        # Reverse direction of the same problem: the LLM sometimes demands
        # product_category/purchase_channel/days_since_purchase even though
        # NO item or order was named at all — contradicting its own
        # instructed bright-line rule (a genuine eligibility check requires
        # a named item/order; without one, "how long does a refund take if
        # I paid with a gift card" is a GENERAL policy question, not an
        # eligibility check, and needs no clarification). If nothing was
        # actually named to check eligibility FOR, the LLM's own demand is
        # self-contradictory regardless of which exact field names it
        # invented — clear it rather than ask a question the customer's
        # message gives no reason to need answered.
        #
        # Originally this only fired when missing_fields was an exact subset
        # of the three canonical eligibility fields, but confirmed bug: on
        # noisy input ("ret item after hw many days can i") the LLM sometimes
        # invents DIFFERENT eligibility-shaped field names (order_status,
        # order_number) not in that fixed set, which slipped past the subset
        # check entirely and still triggered clarification. The real signal
        # is has_item_or_order, not which specific field names came back —
        # any demand for purchase-specific details is equally contradictory
        # when nothing was named to check eligibility for.
        entities = state.get('entities') or {}
        has_item_or_order = bool(
            entities.get('product_name') or entities.get('order_number') or entities.get('tracking_number')
        )
        if not has_item_or_order:
            missing = []
            state['missing_fields'] = []

    # Exchange-for-size/colour is a general, UNCONDITIONAL policy fact (see
    # jumpstart_kb.csv's exchange row) — never dependent on purchase channel/
    # date/category the way return-for-refund eligibility genuinely is. But
    # its similarity score against a phrasing like "swap a shirt for a
    # bigger size" only reaches ~0.50, below the generic _KB_OVERRIDE_THRESHOLD
    # (0.58) used elsewhere — a keyword check catches this narrow, well-
    # defined pattern without loosening that threshold generally (which would
    # risk wrongly overriding cases that DO need real eligibility details).
    if missing and any(w in lower_msg for w in _EXCHANGE_SIGNAL_WORDS):
        missing = []
        state['missing_fields'] = []
        state['_force_knowledge'] = True
        log_agent_action(state['session_id'], 'check_missing_fields',
                          tool_output={'exchange_keyword_override': True},
                          message_id=state.get('message_id'))

    if missing and any(w in lower_msg for w in _RETURN_WINDOW_QUERY_WORDS):
        missing = []
        state['missing_fields'] = []
        state['_force_knowledge'] = True
        log_agent_action(state['session_id'], 'check_missing_fields',
                          tool_output={'return_window_query_override': True},
                          message_id=state.get('message_id'))

    # Final check before committing to a clarification question: even with a
    # named item, the question can still be a general policy one the KB
    # already answers directly (e.g. "Can I swap a shirt for a bigger size
    # instead of returning it?" — a named item, but a general exchange-policy
    # question, not a check against a specific owned purchase). This mirrors
    # create_plan's KB-override, but has to be duplicated here rather than
    # relying on create_plan alone: when the LLM's OWN missing_fields comes
    # back non-empty (as it did for the shirt example), this node routes
    # straight to the clarification node and create_plan never runs at all.
    #
    # Exempt a cancellation's order_number requirement: "I want to cancel my
    # order" scores 0.81 against the general "How do I cancel or change my
    # order?" KB row — comfortably over threshold — so this override used to
    # answer with the general policy instead of ever asking for the order
    # number needed to actually act on the request. Unlike the exchange/
    # return-window cases, a real cancellation ALWAYS needs the order on
    # hand — no amount of KB similarity substitutes for it.
    if missing and missing != ['order_number']:
        from rag.retriever import retrieve_knowledge
        kb_hits = retrieve_knowledge(state.get('customer_message', ''), top_k=1)
        if kb_hits and kb_hits[0]['similarity'] >= _KB_OVERRIDE_THRESHOLD:
            missing = []
            state['missing_fields'] = []
            state['_force_knowledge'] = True
            log_agent_action(
                state['session_id'], 'check_missing_fields',
                tool_output={'kb_override': True, 'similarity': kb_hits[0]['similarity']},
                message_id=state.get('message_id'),
            )

    if not missing:
        # Info gap closed — reset the counter for future clarifications
        state['requires_clarification'] = False
        state['clarification_attempts'] = 0
        return state

    # The clarification prompt only ever asks about ONE field per turn, so a
    # request needing 3+ fields legitimately takes 3+ turns to resolve. Counting
    # every turn against the cap — regardless of whether the gap is shrinking —
    # would escalate that customer before the bot ever asked about the last
    # field. Instead: only count a turn against the cap if it made NO progress.
    #
    # "Progress" is judged by _gained_new_entity (set in detect_intent) — did
    # this turn's extraction add a genuinely NEW entity key — rather than by
    # diffing the LLM's own self-reported missing_fields list turn-to-turn.
    # The old diff-based check trusted the model's judgment of "still
    # missing" twice (once to extract it, once to compare it), and on a
    # smaller/local model (Phi3.5) a vague non-answer like "I don't remember
    # exactly" could get inconsistently parsed between turns — sometimes
    # reporting fewer missing fields than before even though the customer
    # gave no real new information — which reads as false "progress" and
    # resets the counter, so the cap never actually triggers. Tying progress
    # to concrete extracted data instead removes that indirection.
    made_progress = bool(state.get('_gained_new_entity'))
    attempts = 0 if made_progress else state.get('clarification_attempts', 0)

    if attempts < max_attempts:
        state['requires_clarification'] = True
        state['clarification_attempts'] = attempts
    else:
        # Planned rule: repeated clarification failure (no progress across
        # max_attempts turns) escalates to a human
        state['requires_clarification'] = False
        state['requires_handover'] = True
        state['handover_reason'] = 'clarification_failed'
    return state


# ─── Node: Generate Clarification ─────────────────────────────────────────────

# Rule-based port of CLARIFICATION_PROMPT's phrasing guidance — the prompt
# was already just a fixed question template per missing field, so asking an
# LLM to "rephrase" it added a full Groq call for zero real variation. Picking
# missing[0] (not the whole list) preserves the original "ask ONE focused
# question, don't interrogate" rule.
_CLARIFICATION_TEMPLATES = {
    'order_number': ('Could you share your order number? It usually looks like '
                      '"JS-2026-001" and is in your confirmation email.', []),
    'purchase_channel': ('Did you buy this online or in one of our physical stores?',
                         ['Online', 'In-store']),
    'product_category': ('What type of item is this — for example fashion, '
                         'electronics, accessories, or books?', []),
    'product_name': ('Which product are you referring to?', []),
    'days_since_purchase': ('Roughly when did you buy or receive it?', []),
    'issue_type': ('Could you tell me a bit more about what went wrong?', []),
}
_DEFAULT_CLARIFICATION = ('Could you please provide a bit more detail so I can help you better?', [])

# Used instead of the generic "what's your order number" template when
# order_id_retry set this field after a lookup that found no match — this is
# a RE-ask following a wrong ID, not a first-time missing field, so it should
# say so rather than sound like the customer never gave one at all.
_ORDER_LOOKUP_FAILED_MESSAGE = (
    "I couldn't find an order matching that — it may have been entered incorrectly. "
    "Could you double-check your order number (e.g. \"JS-2026-001\") or tracking number and try again?",
    [],
)


def generate_clarification(state: SupportState) -> SupportState:
    missing = state.get('missing_fields') or []
    field = missing[0] if missing else None
    question, quick_replies = _CLARIFICATION_TEMPLATES.get(field, _DEFAULT_CLARIFICATION)

    state['response'] = question
    state['quick_replies'] = quick_replies
    state['clarification_attempts'] = state.get('clarification_attempts', 0) + 1

    # No tool is ever called on this path (create_plan/execute_tool are
    # skipped entirely) — without this log row, the admin audit log shows a
    # turn with an intent but no tool and no confidence, which looks
    # unexplained/broken rather than "correctly asked for more info."
    log_agent_action(state['session_id'], 'generate_clarification',
                      tool_output={'missing_fields': missing,
                                   'attempt': state['clarification_attempts'],
                                   'rule_based': True},
                      message_id=state.get('message_id'))
    return state


# ─── Node: Create Plan ────────────────────────────────────────────────────────

# Rule-based port of PLAN_PROMPT's decision table — intents/entities are
# already known by the time this node runs (detect_intent already extracted
# them), so applying the SAME ordered table the prompt described is just as
# correct as asking an LLM to apply it, and removes one full Groq call from
# every turn that reaches planning. (Note: 'complaint' no longer routes
# straight to handover here — that early-escalation behaviour was deliberately
# moved to verify_result's confidence penalty, giving a genuine attempt first.)
_KNOWLEDGE_INTENTS = {'return_policy', 'delivery_info', 'payment_info', 'warranty',
                      'promotions', 'general_faq', 'product_info', 'refund', 'store_info'}

_PLANNED_STEPS_BY_CATEGORY = {
    'knowledge': ['Search approved knowledge base'],
    'order': ['Look up order status'],
    'return': ['Check return/cancellation eligibility'],
    'product': ['Search product/store catalog'],
    'promo': ['Look up promo code'],
    'account': ['Access account profile'],
    'ticket': ['Log a support ticket for follow-up'],
    'handover': ['Escalate directly to human support'],
    'none': ['Respond conversationally — no tool needed'],
}


def _decide_tool_category(intents, entities):
    intents_set = set(intents or [])
    has_product = bool((entities or {}).get('product_name'))
    has_order = bool((entities or {}).get('order_number'))
    has_promo_code = bool((entities or {}).get('promo_code'))

    if 'human_request' in intents_set:
        return 'handover'
    # Same failure shape as the account_info PII-leak fix below: order_tracking
    # used to win unconditionally, so "Will you cover shipping if my order
    # shows up broken?" (tagged ['order_tracking', 'return_policy'], no order
    # number given) routed straight to the order-lookup tool and failed with
    # "couldn't find an order matching that" instead of answering the general
    # damaged-item policy question. Only trust order_tracking outright when
    # there's an actual order/tracking number to look up, or when no knowledge
    # intent is competing for the same message — otherwise the mixed tagging
    # itself signals order_tracking isn't the real ask.
    if 'order_tracking' in intents_set and (has_order or not (intents_set & _KNOWLEDGE_INTENTS)):
        return 'order'
    if (intents_set & {'return_policy', 'cancellation', 'refund'}) and (has_product or has_order):
        return 'return'
    # 'cancellation' is different from 'return_policy'/'refund': those two
    # are routinely GENERAL policy questions ("how long do refunds take?")
    # answerable from the KB with no order in hand, but "I want to cancel my
    # order" is inherently an action request on a SPECIFIC real order — there
    # is no meaningful "general cancellation" to answer without one. Confirmed
    # bug: with no product/order named, this fell through this function
    # entirely to 'none', and create_plan's KB-fallback then answered from
    # the general "How do I cancel or change my order?" KB row instead of
    # ever asking for the order number needed to actually act on the request.
    if 'cancellation' in intents_set:
        return 'return'
    if 'product_info' in intents_set and has_product:
        return 'product'
    # store_info now falls through to 'knowledge' below — the KB's Store Info
    # category (flagship/Westside Mall/Airport hours+addresses) already
    # covers this, so a dedicated DB-lookup tool was redundant with data
    # that's already accurate and maintained in one place (jumpstart_kb.csv).
    # A SPECIFIC named code ("does WELCOME15 still work?") gets an exact,
    # deterministic lookup — a general "what discounts do you have" question
    # (no code named) still falls through to knowledge/RAG below.
    if 'promotions' in intents_set and has_promo_code:
        return 'promo'
    # Only routes to the PII-exposing account-profile tool when account_info
    # is the SOLE relevant intent — observed bug: a gift-card question got
    # tagged ['account_info', 'general_faq'] (a mixed/uncertain
    # classification) and account_info won unconditionally, exposing the
    # customer's real email/phone/name in response to an unrelated question.
    # When a knowledge intent is ALSO present, that mix itself signals the
    # account_info tag is unreliable here — prefer the safer non-PII path.
    if 'account_info' in intents_set and not (intents_set & _KNOWLEDGE_INTENTS):
        return 'account'
    if intents_set & _KNOWLEDGE_INTENTS:
        return 'knowledge'
    if 'complaint' in intents_set:
        return 'ticket'
    return 'none'


def create_plan(state: SupportState) -> SupportState:
    intents = state.get('intents', [])
    entities = state.get('entities', {})
    # check_missing_fields may have already resolved this to 'knowledge' via
    # its own KB-override check (needed there because a non-empty LLM
    # missing_fields routes straight to clarification, bypassing this node
    # entirely) — skip re-deciding and re-querying pgvector a second time.
    if state.get('_force_knowledge'):
        category = 'knowledge'
    else:
        category = _decide_tool_category(intents, entities)

    # Before committing to a category that needs more specifics from the
    # customer (an order lookup with no ID/tracking number given) or one
    # that just escalates (a complaint routed to a ticket), check whether
    # the knowledge base already directly answers what was actually asked.
    # E.g. "my order stuck on processing 4 days what do I do" reads like it
    # needs an order lookup, but is really a general policy question already
    # covered by a KB row ("What if my order seems stuck...") — demanding an
    # order number there ignores a question the system can already answer.
    # Skipped when a real order/tracking number IS given — that signals a
    # genuine specific lookup, which a generic KB answer would be wrong for.
    #
    # 'return' WAS excluded from this on the theory that a named item always
    # means a real eligibility check — evaluation testing disproved that:
    # "Can I swap a shirt for a bigger size instead of returning it?" names
    # an item ("shirt") but is genuinely a general exchange-policy question
    # (the KB has a direct answer), not a request to check eligibility for a
    # specific owned purchase. A generic/indefinite item reference ("a
    # shirt") in an otherwise general question shouldn't force a 3-question
    # clarification the customer's message never actually needed. Included
    # here now, still guarded by no order number given.
    #
    # 'account' is included unconditionally (regardless of order/product) —
    # tools/account_tool.py can only read/update a phone number, so ANY
    # account_info classification that isn't actually that (e.g. "forgot my
    # password", which the KB already answers) is guaranteed to be a wrong
    # tool call, not just a suboptimal one.
    has_order_id = bool(entities.get('order_number') or entities.get('tracking_number'))
    # 'order' category is ambiguous between two shapes that produce the exact
    # SAME pre-override category/intents (['order_tracking'], no order id):
    # "Track my order" — a literal request for THIS order's status, which
    # only a real lookup can answer — and "my order stuck on processing 4
    # days what do I do" — a troubleshooting question the KB genuinely
    # answers better than an order lookup ever could. Confirmed bug: "Track
    # my order" scored 0.74 against the KB's own "How do I track my order?"
    # row (near-identical wording to the question itself) and got answered
    # with the generic tracking-mechanism explanation instead of ever asking
    # for the order number. Since intent/category can't tell these apart,
    # use the presence of a problem-description word as the signal — its
    # absence means a plain, literal tracking request.
    _ORDER_PROBLEM_SIGNAL_WORDS = ('stuck', 'delay', 'lost', 'missing', 'still', 'days',
                                   "hasn't", 'hasnt', 'not arrived', 'no update', 'no tracking')
    lower_msg_order = state.get('customer_message', '').lower()
    is_literal_order_request = (
        category == 'order' and not has_order_id
        and not any(w in lower_msg_order for w in _ORDER_PROBLEM_SIGNAL_WORDS)
    )
    could_use_kb_override = (
        (category in ('order', 'return') and not has_order_id and not is_literal_order_request)
        or category in ('ticket', 'account')
    )
    if could_use_kb_override:
        from rag.retriever import retrieve_knowledge
        kb_hits = retrieve_knowledge(state.get('customer_message', ''), top_k=1)
        if kb_hits and kb_hits[0]['similarity'] >= _KB_OVERRIDE_THRESHOLD:
            category = 'knowledge'
            log_agent_action(
                state['session_id'], 'create_plan',
                tool_output={'kb_override': True, 'from_category': _decide_tool_category(intents, entities),
                             'similarity': kb_hits[0]['similarity']},
                message_id=state.get('message_id'),
            )

    # 'none' means the LLM tagged no intent at all — that's a DIFFERENT,
    # weaker signal than "demanding clarification fields it shouldn't" (the
    # other overrides above), so it shouldn't need the same strict 0.58 bar
    # skip-clarification bar clears. Confirmed real bug: "Do you accept
    # Afterpay?" (0.473) and "is gift card have expirey date" (0.547) are
    # genuinely on-topic questions that scored under 0.58 and got declared
    # OUT-OF-SCOPE entirely — a worse failure than just running them through
    # the SAME standard-threshold RAG path 'knowledge' category already uses,
    # and letting verify_result's normal confidence machinery decide from
    # there (answer, low-confidence handover, etc.) instead of a hard cutoff.
    if category == 'none':
        from rag.retriever import retrieve_knowledge
        kb_hits = retrieve_knowledge(state.get('customer_message', ''))
        if kb_hits:
            category = 'knowledge'
            log_agent_action(
                state['session_id'], 'create_plan',
                tool_output={'none_category_kb_fallback': True, 'similarity': kb_hits[0]['similarity']},
                message_id=state.get('message_id'),
            )

    state['_tool_category'] = category
    state['planned_steps'] = _PLANNED_STEPS_BY_CATEGORY.get(category, ['Respond conversationally'])
    state['suggested_action'] = f"Assist with: {state.get('customer_goal', '')}" if category == 'handover' else ''

    log_agent_action(state['session_id'], 'create_plan',
                      tool_output={'tool_category': category, 'planned_steps': state['planned_steps'],
                                   'rule_based': True},
                      message_id=state.get('message_id'))

    # category='handover' is now only reachable via an explicit human_request
    # intent (see _decide_tool_category) — it has no execute_tool branch, so
    # set the handover flag/reason here rather than falling through with an
    # empty tool result.
    if category == 'handover' and not state.get('requires_handover'):
        state['requires_handover'] = True
        state['handover_reason'] = 'explicit_request'
    return state


# ─── Node: Execute Tool ───────────────────────────────────────────────────────

def execute_tool(state: SupportState) -> SupportState:
    category = state.get('_tool_category', 'knowledge')
    entities = state.get('entities', {})
    result = {}
    tool_name = ''

    try:
        if category == 'knowledge':
            from tools.knowledge_tool import search_knowledge_base
            # The knowledge base is a single Q&A document now (see
            # seed_knowledge.py) rather than one document per topic, so a
            # document-level topic filter has nothing left to narrow —
            # similarity search alone does the work; topic used to matter
            # when each policy topic was its own separate document.
            #
            # Query with the raw customer_message, not customer_goal.
            # customer_goal is an LLM-generated paraphrase, and on this local
            # model it's sometimes just echoed unchanged from a PRIOR turn's
            # prompt context instead of regenerated for the current one
            # (confirmed: a turn about a damaged order got customer_goal
            # verbatim from the previous turn's laptop-return question),
            # silently sending a stale/wrong query into retrieval. The raw
            # message is always accurate for what THIS turn actually asked.
            result = search_knowledge_base(state['customer_message'])
            tool_name = 'search_knowledge_base'
            if result.get('success'):
                state['retrieved_documents'] = result.get('chunks', [])

        elif category == 'order':
            from tools.order_tool import check_order_status
            result = check_order_status(
                order_number=entities.get('order_number', ''),
                customer_id=state['customer_id'],
                tracking_number=entities.get('tracking_number', ''),
            )
            tool_name = 'check_order_status'
            if result.get('success'):
                # A future, unrelated order question shouldn't inherit a
                # stale retry count from a past resolved lookup.
                state['order_lookup_attempts'] = 0

        elif category == 'return':
            intents_set = set(state.get('intents', []))
            order_number = entities.get('order_number', '')
            if 'cancellation' in intents_set and order_number:
                # A cancellation question is about whether the order has
                # SHIPPED, not a day-since-purchase return window — and the
                # real order record (status, can_cancel) is right there, so
                # there's no reason to guess at it via LLM-extracted entities.
                from tools.return_tool import check_cancellation_eligibility
                result = check_cancellation_eligibility(
                    order_number=order_number,
                    customer_id=state['customer_id'],
                )
                tool_name = 'check_cancellation_eligibility'
            elif order_number:
                # A return/refund question about a KNOWN order — read the real
                # purchase_channel/days_since_purchase/category off that order
                # instead of asking the customer to re-supply what's already
                # on record (and instead of re-asking for the order number a
                # second time after check_missing_fields already required it).
                from tools.return_tool import check_return_eligibility_for_order
                result = check_return_eligibility_for_order(
                    order_number=order_number,
                    customer_id=state['customer_id'],
                    product_name=entities.get('product_name', ''),
                )
                tool_name = 'check_return_eligibility_for_order'
            else:
                # No order on hand — general policy question, has to rely on
                # whatever the customer described (category/channel/days).
                from tools.return_tool import check_return_eligibility
                try:
                    # Guards against the LLM emitting an empty string rather
                    # than omitting the key entirely (observed on the local
                    # Ollama model) — int('') raises ValueError, which would
                    # otherwise silently fail this whole tool call instead of
                    # falling back to the "unknown" default.
                    days_since_purchase = int(entities.get('days_since_purchase') or 0)
                except (TypeError, ValueError):
                    days_since_purchase = 0
                result = check_return_eligibility(
                    purchase_channel=entities.get('purchase_channel') or 'online',
                    product_category=entities.get('product_category') or 'general',
                    days_since_purchase=days_since_purchase,
                    order_status=entities.get('order_status') or 'delivered',
                    product_name=entities.get('product_name', ''),
                )
                tool_name = 'check_return_eligibility'

        elif category == 'product':
            from tools.product_tool import search_products
            result = search_products(
                query=entities.get('product_name') or state['customer_goal'],
            )
            tool_name = 'search_products'

        elif category == 'promo':
            from tools.promo_tool import check_promo_code
            result = check_promo_code(entities.get('promo_code', ''))
            tool_name = 'check_promo_code'

        elif category == 'account':
            # customer_id comes from the authenticated session, never from
            # extracted entities — see tools/account_tool.py's module note.
            new_phone = entities.get('new_phone', '')
            if new_phone:
                from tools.account_tool import update_account_phone
                result = update_account_phone(customer_id=state['customer_id'], new_phone=new_phone)
                tool_name = 'update_account_phone'
            else:
                from tools.account_tool import get_account_profile
                result = get_account_profile(customer_id=state['customer_id'])
                tool_name = 'get_account_profile'

        elif category == 'ticket':
            from tools.ticket_tool import create_support_ticket
            result = create_support_ticket(
                session_id=state['session_id'],
                issue_type=state.get('customer_goal', ''),
                description=state['customer_message'],
            )
            tool_name = 'create_support_ticket'

        elif category == 'none':
            result = {'success': True, 'no_tool': True}
            tool_name = 'none'

    except Exception as e:
        result = {'success': False, 'error': str(e)}
        tool_name = category

    state['tool_result'] = result
    state['tools_used'] = state.get('tools_used', []) + [tool_name]
    state['tool_call_count'] = state.get('tool_call_count', 0) + 1
    log_agent_action(
        state['session_id'], 'execute_tool',
        tool_name=tool_name, tool_input=entities, tool_output=result,
        success=result.get('success', False),
        message_id=state.get('message_id'),
    )
    return state


# ─── Node: Order ID Retry ──────────────────────────────────────────────────────

# A failed order/tracking lookup is very often just a typo (wrong digit, a
# stray "#", the wrong year) rather than a genuine "nothing I can do" case —
# jumping straight to "connect you with a human?" for that is a bad
# experience when simply re-asking for the ID usually fixes it.
#
# This uses its OWN counter (order_lookup_attempts), deliberately separate
# from clarification_attempts/check_missing_fields — reusing that machinery
# was tempting, but check_missing_fields resets its counter to 0 the moment
# detect_intent successfully EXTRACTS an order_number, even if it's still the
# WRONG one, since "extracted" and "correct" aren't the same thing. Routing
# through it would let a customer resubmit the same wrong ID forever without
# ever reaching the cap. A dedicated counter avoids that interference.
def order_id_retry(state: SupportState) -> SupportState:
    max_attempts = getattr(settings, 'MAX_CLARIFICATION_ATTEMPTS', 2)
    attempts = state.get('order_lookup_attempts', 0) + 1
    state['order_lookup_attempts'] = attempts

    if attempts <= max_attempts:
        message, quick_replies = _ORDER_LOOKUP_FAILED_MESSAGE
        state['response'] = message
        state['quick_replies'] = quick_replies
        log_agent_action(state['session_id'], 'order_id_retry',
                          tool_output={'attempt': attempts}, message_id=state.get('message_id'))
    else:
        # Repeated genuine failure, not just one typo — stop asking and offer
        # a human instead (goes through the same offer-first flow as any
        # other non-immediate reason).
        state['requires_handover'] = True
        state['handover_reason'] = 'no_evidence'
        log_agent_action(state['session_id'], 'order_id_retry',
                          tool_output={'attempt': attempts, 'giving_up': True},
                          message_id=state.get('message_id'))
    return state


def route_after_execute_tool(state: SupportState) -> str:
    result = state.get('tool_result') or {}
    if (state.get('_tool_category') == 'order' and not result.get('success')
            and 'not found' in (result.get('error') or '').lower()):
        return 'order_id_retry'
    return 'verify'


def route_after_order_retry(state: SupportState) -> str:
    if state.get('requires_handover'):
        return _handover_or_offer(state)
    return 'save'


# ─── Node: Verify Tool Result ─────────────────────────────────────────────────

def verify_result(state: SupportState) -> SupportState:
    result = state.get('tool_result', {})
    docs = state.get('retrieved_documents', [])
    entities = state.get('entities', {})

    rag_relevance = 0.0
    has_evidence = False
    metadata_match = False

    if docs:
        rag_relevance = docs[0].get('similarity', 0.0) if docs else 0.0
        has_evidence = True
        metadata_match = True

    tool_success = result.get('success', False)

    # Successful business tools (order/return/product lookups) return data from
    # JumpStart's own database — that IS approved evidence, even without RAG docs.
    if tool_success and state.get('_tool_category') in ('order', 'return', 'product', 'ticket', 'promo', 'account'):
        has_evidence = True
        metadata_match = True
        rag_relevance = max(rag_relevance, 0.75)
    entity_completeness = min(len(entities) / max(len(state.get('missing_fields', [])) + len(entities), 1), 1.0)

    # Sensitive business ACTIONS require HIGH confidence (refund/cancel/complaint) —
    # this exists because those answers used to rely on LLM-guessed inputs
    # (category/channel/days), where a wrong guess could give a customer bad
    # information about their money. check_cancellation_eligibility and
    # check_return_eligibility_for_order removed that guessing for orders the
    # AI can actually look up — when one of those returns a definitive,
    # deterministic "no" (eligible=False, no staff review needed), there is
    # nothing left uncertain for a human to confirm, so treat it like any
    # other confidently-answered question instead of offering a handover
    # nobody asked for and that wouldn't change the answer anyway.
    last_tool = state.get('tools_used', [])[-1] if state.get('tools_used') else ''
    is_resolved_ineligible = (
        state.get('_tool_category') == 'return'
        and last_tool in ('check_cancellation_eligibility', 'check_return_eligibility_for_order')
        and result.get('eligible') in (False, None)
        and not result.get('requires_staff_review')
    )
    # refund/cancellation are only genuinely "sensitive" when they resolve to
    # an actual eligibility/action check (_tool_category == 'return') — the
    # LLM tags intent purely from keywords, so "how long do refunds take?"
    # (an informational question that resolves to 'knowledge', no real order
    # or action involved) also gets the 'refund' intent tag, but there is no
    # pending action there for a human to need to confirm. Penalising its
    # confidence and offering a handover for it was answering a risk that
    # doesn't exist. 'complaint' stays sensitive regardless of category,
    # since it's about customer distress, not a specific tool's action risk —
    # but ONLY when there's actual distress to go with it. Confirmed bug: a
    # plain "can I swap a shirt for a bigger size?" policy question got
    # spuriously tagged with 'complaint' (classification noise, same shape as
    # the account_info/order_tracking co-occurrence bugs) alongside NEUTRAL
    # sentiment, and this unconditional check sent a fully-answerable,
    # confidently-retrieved question to a handover offer anyway. A genuine
    # complaint reads as customer distress, which shows up as negative
    # sentiment (see is_frustrated below, which already assumes this
    # correlation) — a 'complaint' tag with neutral/positive sentiment is
    # noise, not a real complaint.
    matched_sensitive = {'refund', 'cancellation', 'complaint'}.intersection(set(state.get('intents', [])))
    is_action_sensitive = bool(matched_sensitive & {'refund', 'cancellation'}) and state.get('_tool_category') == 'return'
    is_complaint_sensitive = 'complaint' in matched_sensitive and state.get('sentiment') == 'negative'
    is_sensitive = (is_action_sensitive or is_complaint_sensitive) and not is_resolved_ineligible
    # A complaint made with visibly negative sentiment gets one real attempt
    # (unlike the old behaviour, which skipped straight to a human) but is
    # held to a stricter bar than an ordinary complaint — stacked on top of
    # the is_sensitive penalty below.
    is_frustrated = is_sensitive and state.get('sentiment') == 'negative' and 'complaint' in state.get('intents', [])

    from services.confidence import calculate_confidence, get_confidence_band
    confidence = calculate_confidence(
        rag_relevance=rag_relevance,
        has_approved_evidence=has_evidence,
        metadata_match=metadata_match,
        tool_success=tool_success,
        entity_completeness=entity_completeness,
        verification_passed=True,
        safety_check_passed=True,
    )

    # Penalise for sensitive issues
    if is_sensitive:
        confidence = confidence * 0.80
    # Extra penalty on top — a visibly frustrated customer needs a notably
    # more confident answer than a neutral complaint before the AI proceeds alone.
    if is_frustrated:
        confidence = confidence * 0.70

    # Conversational turns that need no tool have nothing to verify — answer
    # honestly instead of escalating on a formula that assumes evidence.
    if state.get('_tool_category') == 'none' and not is_sensitive:
        confidence = max(confidence, 0.70)

    state['confidence'] = confidence
    state['confidence_band'] = get_confidence_band(confidence)
    state['verification_passed'] = bool(docs or tool_success)

    # Trigger handover if LOW confidence or sensitive + not HIGH
    LOW = getattr(settings, 'CONFIDENCE_MEDIUM', 0.65)
    if confidence < LOW or (is_sensitive and state['confidence_band'] != 'HIGH'):
        if not state.get('requires_handover'):
            state['requires_handover'] = True
            if is_frustrated:
                state['handover_reason'] = 'frustrated_customer'
            elif confidence < LOW:
                state['handover_reason'] = 'low_confidence'
            else:
                state['handover_reason'] = 'sensitive_issue'

    # Also trigger if no evidence at all
    if not docs and not tool_success and state.get('_tool_category') != 'none':
        state['requires_handover'] = True
        state['handover_reason'] = 'no_evidence'

    # A CONFIRMED-eligible refund/cancellation always goes to a human,
    # regardless of confidence — the AI has no capability to actually execute
    # a refund/cancellation itself, so once eligibility is confirmed there's
    # a real financial action pending, not just a question to answer. This
    # is also exempt from the "offer first" flow (see _handover_or_offer) —
    # a human must review it either way, asking doesn't change that.
    if state.get('_tool_category') == 'return' and result.get('eligible') is True:
        state['requires_handover'] = True
        state['handover_reason'] = 'sensitive_issue'

    # Evidence collection: log every RAG retrieval for admin metrics
    if state.get('_tool_category') == 'knowledge':
        try:
            from knowledge.models import RAGRetrievalLog
            RAGRetrievalLog.objects.create(
                session_id=state['session_id'],
                message_id=state.get('message_id'),
                query_text=state.get('customer_goal', ''),
                filters_used={'topic': state.get('intents', [])},
                retrieved_chunk_ids=[d.get('id') for d in docs],
                similarity_scores=[round(d.get('similarity', 0.0), 4) for d in docs],
                selected_chunk_ids=[d.get('id') for d in docs],
                verification_result=state['verification_passed'],
                confidence_band=state['confidence_band'],
            )
        except Exception:
            pass

    # This is the row the admin dashboard's per-message insight reads confidence,
    # confidence_band, and the handover decision from.
    log_agent_action(
        state['session_id'], 'verify_result',
        tool_output={
            'confidence_band': state['confidence_band'],
            'requires_handover': state.get('requires_handover', False),
            'handover_reason': state.get('handover_reason', ''),
            'rag_relevance': round(rag_relevance, 4),
            'has_evidence': has_evidence,
        },
        success=state['verification_passed'],
        confidence=state['confidence'],
        message_id=state.get('message_id'),
    )

    return state


# ─── Node: Generate Response ──────────────────────────────────────────────────

# category='none' means no intent matched anything the system recognizes —
# in practice this is reached almost exclusively by genuinely out-of-scope
# questions (capital of France, weather, restaurant recommendations, resume
# writing), NOT smalltalk (that's caught earlier by validate_input's own
# dedicated smalltalk path and never reaches here). Repeatedly confirmed via
# testing: letting the LLM free-associate an answer here (with zero evidence
# and zero tool result to ground it) reliably produces fabricated content —
# invented restaurant names, false "I can look that up" capability claims,
# or just directly answering general-knowledge trivia the bot has no
# business answering. A deterministic decline removes that failure mode
# entirely rather than relying on prompt discipline the model doesn't
# reliably follow.
OUT_OF_SCOPE_MESSAGE = (
    "I can't help with that - I can only assist with JumpStart orders, returns, "
    "delivery, products, and support questions."
)


def generate_response(state: SupportState) -> SupportState:
    if state.get('_tool_category') == 'none' and not state.get('retrieved_documents'):
        state['response'] = OUT_OF_SCOPE_MESSAGE
        state['quick_replies'] = []
        log_agent_action(state['session_id'], 'generate_response',
                          tool_output={'out_of_scope_deterministic': True},
                          message_id=state.get('message_id'))
        return state

    evidence = '\n\n'.join(
        f"[{d.get('source_title', 'KB')}] {d.get('chunk_text', '')}"
        for d in state.get('retrieved_documents', [])
    ) or 'No knowledge base evidence retrieved.'

    tool_result = dict(state.get('tool_result') or {})
    # check_order_status's payload carries can_cancel/can_return for other
    # consumers (e.g. the order detail page) — a plain "where's my order"
    # question has no business getting an unsolicited "by the way, this
    # can't be cancelled" tacked on. Only keep those fields in the prompt
    # when the customer actually asked about cancelling/returning; relying
    # on prompt instructions alone wasn't reliable enough on its own.
    if state.get('_tool_category') == 'order':
        asked_about_eligibility = bool(
            set(state.get('intents', [])) & {'cancellation', 'refund', 'return_policy'}
        )
        if not asked_about_eligibility:
            tool_result.pop('can_cancel', None)
            tool_result.pop('can_return', None)

    tool_str = json.dumps(tool_result, default=str)
    prompt = RESPONSE_GENERATION_PROMPT.format(
        customer_message=state['customer_message'],
        customer_goal=state.get('customer_goal', ''),
        history=state.get('_history', '') or 'No prior messages this session.',
        evidence=evidence,
        tool_result=tool_str,
        confidence_band=state.get('confidence_band', 'MEDIUM'),
    )
    try:
        raw = call_llm(prompt, state['session_id'])
        parsed = parse_json(raw)
        state['response'] = parsed.get('response', raw)
        state['quick_replies'] = parsed.get('quick_replies', [
            'Track my order', 'Start a return', 'Talk to a human'
        ])

        # Deterministic backstop for a confirmed recurring generation error:
        # the model sometimes opens with a false negation ("We don't carry
        # student discount codes...") and then immediately contradicts
        # itself with the correct affirmative fact ("...however, STUDENT12
        # gives 12% off"). Retrieval was independently confirmed correct in
        # every instance this showed up — this is purely a generation-side
        # self-contradiction, not a routing/evidence gap, so prompt wording
        # alone isn't reliable enough on this model size (same lesson as
        # every other deterministic backstop in this file). When the TOP
        # retrieved chunk is unambiguously affirmative ("A: Yes, ..."), a
        # response opening with a negation is a GUARANTEED contradiction —
        # safe to override with the chunk's own ground-truth answer text
        # rather than trust the model's contradictory phrasing.
        #
        # The exclusion (rather than requiring an explicit "A: Yes,") is what
        # keeps this safe: a chunk that is ITSELF a "No, ..." answer (e.g.
        # "No international shipping — JumpStart delivers nationwide only")
        # means the model's own negation opener may be legitimate — the
        # negated thing and the follow-on fact can be two different,
        # compatible things ("no X, but Y works"), which must NOT be
        # touched by this check. But when the ground-truth chunk is NOT
        # itself a negative answer (e.g. a straightforward category listing
        # like "JumpStart stocks six categories: ..."), the model opening
        # with a negation about the very thing that chunk affirms is never
        # legitimate — confirmed on the "what categories do you sell"
        # case, where the chunk doesn't start with "Yes" but is still an
        # unconditional affirmative listing, so the stricter "Yes"-only
        # version of this check missed it.
        docs = state.get('retrieved_documents') or []
        if docs and state.get('_tool_category') == 'knowledge':
            top_chunk = docs[0].get('chunk_text', '')
            answer_match = top_chunk.split('A:', 1)
            top_answer = answer_match[1].strip() if len(answer_match) > 1 else ''
            _NEGATION_OPENERS = ("we don't", "we do not", "we dont", "no,", "not offer", "don't carry",
                                 "do not carry", "dont carry", "not carry")
            response_opening = state['response'].strip().lower()[:40]
            if top_answer and not top_answer.lower().startswith('no') and any(
                response_opening.startswith(p) for p in _NEGATION_OPENERS
            ):
                state['response'] = top_answer
                log_agent_action(
                    state['session_id'], 'generate_response',
                    tool_output={'contradiction_override': True, 'original_response': parsed.get('response', raw)},
                    message_id=state.get('message_id'),
                )

        log_agent_action(state['session_id'], 'generate_response', tool_output=parsed,
                          message_id=state.get('message_id'))
    except Exception as e:
        state['response'] = 'I\'m sorry, I\'m having trouble generating a response right now. Let me connect you with a human agent.'
        state['requires_handover'] = True
        state['handover_reason'] = 'tool_failure'
        state['error'] = str(e)
    return state


# ─── Node: Safety Check ───────────────────────────────────────────────────────

def safety_check(state: SupportState) -> SupportState:
    response = state.get('response', '')
    evidence_texts = ' '.join(d.get('chunk_text', '') for d in state.get('retrieved_documents', []))
    max_regen = getattr(settings, 'MAX_REGENERATION_ATTEMPTS', 1)

    # Layer 1: cheap deterministic pre-filter for the most flagrant overreach.
    FORBIDDEN_PROMISES = ['I will refund', 'I can cancel', 'I promise', 'guaranteed refund', 'will definitely']
    issues = [p for p in FORBIDDEN_PROMISES if p.lower() in response.lower()]

    if issues and state.get('regeneration_attempts', 0) < max_regen:
        state['regeneration_attempts'] = state.get('regeneration_attempts', 0) + 1
        state['safety_passed'] = False
        log_agent_action(state['session_id'], 'safety_check_keyword', tool_output={'issues': issues},
                          success=False, message_id=state.get('message_id'))
        return generate_response(state)

    # Layer 2: an LLM groundedness check catches unsupported claims the keyword
    # list can't (e.g. an invented policy detail that isn't one of the exact
    # forbidden phrases). Skipped for 'none'-category turns, which have no
    # evidence to check against by design (see verify_result's own comment) —
    # and skipped at HIGH confidence, since that band already means strong
    # evidence + a clean keyword pass; the semantic check earns its keep on
    # MEDIUM/LOW turns, where the risk of an ungrounded claim is real.
    #
    # Also skipped entirely when SKIP_LLM_SAFETY_CHECK is set — a second full
    # LLM call (plus a possible regeneration, itself another call) roughly
    # doubles per-turn latency, which matters a lot when each call already
    # takes 60-120s on a local/tunnelled model. Layer 1's free keyword check
    # still runs regardless, so this doesn't remove safety entirely — it
    # drops the semantic layer for faster iteration during manual evaluation.
    if (
        not getattr(settings, 'SKIP_LLM_SAFETY_CHECK', False)
        and state.get('_tool_category') != 'none'
        and state.get('confidence_band') != 'HIGH'
    ):
        combined_evidence = (evidence_texts or 'No knowledge base evidence retrieved.')
        tool_str = json.dumps(state.get('tool_result', {}), default=str)
        prompt = VERIFICATION_PROMPT.format(
            evidence=f'{combined_evidence}\n\nTool result (also valid grounding): {tool_str}',
            response=response,
        )
        try:
            raw = call_llm(prompt, state['session_id'], max_tokens=250)
            parsed = parse_json(raw)
            llm_verification_passed = parsed.get('verification_passed', True)
            llm_safety_passed = parsed.get('safety_passed', True)
            if (not llm_verification_passed or not llm_safety_passed) and state.get('regeneration_attempts', 0) < max_regen:
                state['regeneration_attempts'] = state.get('regeneration_attempts', 0) + 1
                state['safety_passed'] = False
                log_agent_action(state['session_id'], 'safety_check_llm', tool_output=parsed,
                                  success=False, message_id=state.get('message_id'))
                return generate_response(state)
            state['verification_passed'] = bool(llm_verification_passed) and state.get('verification_passed', True)
            log_agent_action(state['session_id'], 'safety_check_llm', tool_output=parsed,
                              success=True, message_id=state.get('message_id'))
        except Exception:
            # Fail open — a broken verification call must not block a response
            # that already cleared the deterministic keyword check.
            pass

    state['safety_passed'] = True
    return state


# ─── Node: Execute Handover ───────────────────────────────────────────────────

def execute_handover(state: SupportState) -> SupportState:
    from tools.handover_tool import handover_to_human
    tool_result = state.get('tool_result') or {}
    policy_reason = tool_result.get('reason', '') if state.get('_tool_category') == 'return' else ''
    result = handover_to_human(
        session_id=state['session_id'],
        reason=state.get('handover_reason', 'low_confidence'),
        ai_summary=state.get('customer_goal', ''),
        customer_goal=state.get('customer_goal', ''),
        detected_intents=state.get('intents', []),
        detected_entities=state.get('entities', {}),
        tools_used=state.get('tools_used', []),
        rag_sources=[d.get('source_title', '') for d in state.get('retrieved_documents', [])],
        confidence=state.get('confidence', 0.0),
        suggested_action=state.get('suggested_action', ''),
        policy_reason=policy_reason,
    )
    state['tool_result'] = result
    log_agent_action(state['session_id'], 'route_handover', tool_output=result,
                      message_id=state.get('message_id'))
    return state


# ─── Node: Offer Handover (ask first, don't escalate immediately) ─────────────

# Customer-facing question shown INSTEAD OF an immediate handover — the
# customer decides whether to actually escalate. Distinct from
# tools/handover_tool.py's HANDOVER_MESSAGES, which explain a handover that's
# already happening; these ask permission first.
OFFER_HANDOVER_MESSAGES = {
    'low_confidence': "I'm not fully confident I can answer that correctly. Would you like me to connect you with a human agent for certainty?",
    'no_evidence': "I couldn't find enough information to help with that confidently. Would you like me to connect you with a human agent?",
    'sensitive_issue': "This looks like something our support team should confirm directly. Would you like me to connect you with a human agent?",
    'clarification_failed': "I'm having trouble gathering the details I need to help with this. Would you like me to connect you with a human agent instead?",
    'frustrated_customer': "I'm sorry this hasn't gone smoothly. Would you like me to connect you with a human agent right away?",
    'tool_failure': "I ran into a technical issue on my end. Would you like me to connect you with a human agent who can help?",
}
DEFAULT_OFFER_MESSAGE = "I'm not able to fully help with this myself. Would you like me to connect you with a human agent?"


def offer_handover_reply(state: SupportState) -> SupportState:
    reason = state.get('handover_reason', '')
    message = OFFER_HANDOVER_MESSAGES.get(reason, DEFAULT_OFFER_MESSAGE)

    # If a return/cancellation eligibility check actually ran, it already
    # produced a factual, policy-grounded answer (check_return_eligibility's
    # 'reason') — lead with that instead of a content-free canned line. The
    # customer asked a policy question and deserves the real answer, even
    # though a human still has to confirm/execute the action itself.
    tool_result = state.get('tool_result') or {}
    if state.get('_tool_category') == 'return' and tool_result.get('reason'):
        message = f"{tool_result['reason']} {message}"

    state['response'] = message
    state['quick_replies'] = ['Yes, connect me', 'No, keep trying']
    # Not escalating yet — waiting for the customer's answer. save_state
    # persists this so the NEXT message can be interpreted as a reply to
    # this offer instead of a fresh question (see check_pending_handover_offer).
    state['pending_handover_reason'] = reason
    state['requires_handover'] = False
    log_agent_action(state['session_id'], 'offer_handover', tool_output={'reason': reason},
                      message_id=state.get('message_id'))
    return state


# ─── Node: Check Pending Handover Offer ───────────────────────────────────────

# Runs FIRST, before validate_input — if the previous turn asked "want a
# human?", this turn's message is very likely a yes/no answer to that, not a
# new support question, and should be interpreted as such rather than run
# through intent detection from scratch.
AFFIRMATIVE_HANDOVER_REPLIES = {
    'yes', 'yes please', 'yes connect me', 'yes, connect me', 'yeah', 'yea',
    'yep', 'sure', 'ok', 'okay', 'please', 'connect me', 'human please',
}


def check_pending_handover_offer(state: SupportState) -> SupportState:
    pending = state.get('_prior_pending_handover_reason', '')
    if not pending:
        return state
    msg = state.get('customer_message', '').strip().lower().rstrip('.!')
    if msg in AFFIRMATIVE_HANDOVER_REPLIES or 'connect me' in msg:
        state['requires_handover'] = True
        state['handover_reason'] = pending
    else:
        # Declining (or ignoring the buttons and typing something new) falls
        # through to the normal pipeline below and gets a genuine fresh
        # attempt — reset the clarification counter so a stale "already at
        # the cap" count doesn't immediately re-trigger the SAME offer again
        # on this very message, before the bot has even tried once more.
        state['clarification_attempts'] = 0
    # Either way the pending offer is now resolved: state['pending_handover_reason']
    # stays at its default '' (set in _build_initial_state) unless
    # offer_handover_reply sets it again this turn, so save_state naturally clears it.
    return state


# ─── Node: Save State & Audit ─────────────────────────────────────────────────

def save_state(state: SupportState) -> SupportState:
    from chatbot.models import ConversationState, ChatSession
    try:
        session = ChatSession.objects.get(id=state['session_id'])
        conv_state, _ = ConversationState.objects.get_or_create(session=session)
        conv_state.intents = state.get('intents', [])
        conv_state.customer_goal = state.get('customer_goal', '')
        conv_state.entities = state.get('entities', {})
        conv_state.missing_fields = state.get('missing_fields', [])
        conv_state.clarification_attempts = state.get('clarification_attempts', 0)
        conv_state.order_lookup_attempts = state.get('order_lookup_attempts', 0)
        conv_state.planned_steps = state.get('planned_steps', [])
        conv_state.completed_steps = state.get('completed_steps', [])
        conv_state.tool_call_count = state.get('tool_call_count', 0)
        conv_state.confidence = state.get('confidence', 0.0)
        conv_state.sentiment = state.get('sentiment', 'neutral')
        conv_state.pending_handover_reason = state.get('pending_handover_reason', '')
        conv_state.save()
    except Exception as e:
        print(f'[save_state error]: {e}')
    return state


# ─── Routing Functions ────────────────────────────────────────────────────────

# Reasons that escalate IMMEDIATELY, no confirmation question — the customer
# already asked (explicit_request), or a real financial action was just
# confirmed eligible (see verify_result — checked directly on tool_result
# here rather than via a dedicated reason, since both share 'sensitive_issue').
# Everything else that wants to escalate ASKS FIRST via offer_handover_reply.
IMMEDIATE_HANDOVER_REASONS = {'explicit_request'}


def _handover_or_offer(state: SupportState) -> str:
    if state.get('handover_reason') in IMMEDIATE_HANDOVER_REASONS:
        return 'handover'
    if state.get('_tool_category') == 'return' and (state.get('tool_result') or {}).get('eligible') is True:
        return 'handover'
    return 'offer_handover'


def route_after_pending_offer(state: SupportState) -> str:
    # Only an affirmative reply to a just-offered handover skips straight to
    # execute_handover — everything else (decline, or an unrelated new
    # message) continues into the normal pipeline via validate_input.
    if state.get('requires_handover'):
        return 'handover'
    return 'validate'


def route_after_validate(state: SupportState) -> str:
    if state.get('_injection_detected'):
        return 'guard'
    if state.get('requires_handover'):
        return 'handover'  # explicit human request — no LLM needed
    if state.get('_smalltalk'):
        return 'smalltalk'
    return 'continue'


def route_after_intent(state: SupportState) -> str:
    # requires_handover/handover_reason are set inside detect_intent's own
    # except block now (see its comment) — conditional-edge functions like
    # this one can only READ state, any mutation here would be silently
    # discarded and never reach offer_handover_reply.
    if state.get('requires_handover'):
        return _handover_or_offer(state)
    return 'check_missing'


def route_after_missing(state: SupportState) -> str:
    if state.get('requires_clarification'):
        return 'clarify'
    if state.get('requires_handover'):
        return _handover_or_offer(state)
    return 'plan'


def route_after_plan(state: SupportState) -> str:
    if state.get('requires_handover'):
        return _handover_or_offer(state)
    return 'execute_tool'


def route_after_verify(state: SupportState) -> str:
    if state.get('requires_handover'):
        return _handover_or_offer(state)
    return 'respond'


def route_after_safety(state: SupportState) -> str:
    if state.get('requires_handover'):
        return _handover_or_offer(state)
    return 'save'


# ─── Build LangGraph ──────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(SupportState)

    graph.add_node('check_pending_offer', check_pending_handover_offer)
    graph.add_node('validate', validate_input)
    graph.add_node('guard_reply', guard_reply)
    graph.add_node('smalltalk_reply', smalltalk_reply)
    graph.add_node('load_history', load_history)
    graph.add_node('detect_intent', detect_intent)
    graph.add_node('check_missing', check_missing_fields)
    graph.add_node('clarify', generate_clarification)
    graph.add_node('plan', create_plan)
    graph.add_node('execute_tool', execute_tool)
    graph.add_node('verify', verify_result)
    graph.add_node('respond', generate_response)
    graph.add_node('handover', execute_handover)
    graph.add_node('offer_handover', offer_handover_reply)
    graph.add_node('order_id_retry', order_id_retry)
    graph.add_node('save_state', save_state)

    # New entry point: check whether this message is a yes/no reply to a
    # handover offered last turn BEFORE running any of the normal guardrails/
    # intent detection on it.
    graph.set_entry_point('check_pending_offer')
    graph.add_conditional_edges('check_pending_offer', route_after_pending_offer, {
        'handover': 'handover',
        'validate': 'validate',
    })
    graph.add_conditional_edges('validate', route_after_validate, {
        'guard': 'guard_reply',
        'handover': 'handover',
        'smalltalk': 'smalltalk_reply',
        'continue': 'load_history',
    })
    graph.add_edge('guard_reply', 'save_state')
    graph.add_edge('smalltalk_reply', 'save_state')
    graph.add_edge('load_history', 'detect_intent')
    graph.add_conditional_edges('detect_intent', route_after_intent, {
        'handover': 'handover',
        'offer_handover': 'offer_handover',
        'check_missing': 'check_missing',
    })
    graph.add_conditional_edges('check_missing', route_after_missing, {
        'clarify': 'clarify',
        'plan': 'plan',
        'handover': 'handover',
        'offer_handover': 'offer_handover',
    })
    graph.add_edge('clarify', 'save_state')
    graph.add_conditional_edges('plan', route_after_plan, {
        'handover': 'handover',
        'offer_handover': 'offer_handover',
        'execute_tool': 'execute_tool',
    })
    graph.add_conditional_edges('execute_tool', route_after_execute_tool, {
        'order_id_retry': 'order_id_retry',
        'verify': 'verify',
    })
    graph.add_conditional_edges('order_id_retry', route_after_order_retry, {
        'handover': 'handover',
        'offer_handover': 'offer_handover',
        'save': 'save_state',
    })
    graph.add_conditional_edges('verify', route_after_verify, {
        'handover': 'handover',
        'offer_handover': 'offer_handover',
        'respond': 'respond',
    })
    # safety_check node removed for evaluation — it never itself set
    # requires_handover (route_after_verify already diverts away from
    # 'respond' whenever requires_handover is set before this point), so
    # 'respond' -> 'save_state' directly loses no real handover routing,
    # only the keyword pre-filter + LLM groundedness/regeneration layers.
    graph.add_edge('respond', 'save_state')
    graph.add_edge('handover', 'save_state')
    graph.add_edge('offer_handover', 'save_state')
    graph.add_edge('save_state', END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
