# -*- coding: utf-8 -*-
"""Batch evaluation runner — feeds a question dataset through the real agent
graph and exports per-question results to CSV for manual scoring.

Usage (from backend/):
    venv\\Scripts\\python.exe evaluation_runner.py dataset.csv results.csv
    venv\\Scripts\\python.exe evaluation_runner.py dataset.csv results.csv --keep

Dataset CSV columns (header row required):
    id        — your question ID (e.g. K01, R14, U03, A07)
    category  — known | rephrased | unknown | ambiguous  (free text, echoed out)
    question  — the customer message. For MULTI-TURN cases (ambiguous category),
                separate turns with ` || ` — e.g.
                "Can I return my headphones? || about a week ago"
    expected  — expected behaviour/answer (echoed to the results for scoring)

Each dataset row runs in a FRESH chat session (so history never contaminates
across questions), but turns within one row share the session (so
clarification memory works exactly as in production).

Results CSV adds, per row: the final response, detected intents, tool
category, confidence + band, handover flag & reason, whether a clarification
was asked, retrieved KB documents with the top similarity score, and elapsed
seconds per turn — everything Sections 3 and 4 of the Evaluation Guide need.

Sessions created by the run are deleted afterwards unless --keep is passed
(keep them when you want to inspect turns in the admin Audit Log).
"""
import csv
import os
import sys
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django  # noqa: E402
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from chatbot.models import ChatSession, ChatMessage  # noqa: E402
from knowledge.models import RAGRetrievalLog, KnowledgeChunk  # noqa: E402
from agents.graph import get_graph  # noqa: E402
from agents.runner import _build_initial_state  # noqa: E402


def run_dataset(dataset_path: str, results_path: str, keep_sessions: bool = False):
    User = get_user_model()
    customer = User.objects.filter(username='customer_demo').first() \
        or User.objects.filter(role='customer').first()
    if not customer:
        sys.exit('No customer account found — run `manage.py seed_data` first.')

    graph = get_graph()
    created_session_ids = []
    results = []

    with open(dataset_path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f'No rows found in {dataset_path}')

    print(f'Running {len(rows)} questions as {customer.username}...\n')

    for i, row in enumerate(rows, 1):
        qid = (row.get('id') or f'Q{i}').strip()
        category = (row.get('category') or '').strip()
        turns = [t.strip() for t in (row.get('question') or '').split('||') if t.strip()]
        if not turns:
            continue

        session = ChatSession.objects.create(customer=customer)
        created_session_ids.append(session.id)

        final_state, elapsed_total = {}, 0.0
        for turn_text in turns:
            msg = ChatMessage.objects.create(
                session=session, sender=ChatMessage.Sender.CUSTOMER,
                sender_user=customer, content=turn_text,
            )
            initial = _build_initial_state(str(session.id), turn_text, msg.id, customer.id)
            t0 = time.monotonic()
            final_state = graph.invoke(initial)
            elapsed_total += time.monotonic() - t0
            # Persist the AI reply so the next turn's history/memory is realistic
            if final_state.get('response'):
                ChatMessage.objects.create(
                    session=session, sender=ChatMessage.Sender.AI,
                    content=final_state['response'],
                    quick_replies=final_state.get('quick_replies', []),
                )

        # RAG evidence for this session (for Recall@5 / Precision@5 scoring)
        retrieved_docs, top_similarity = [], ''
        log = RAGRetrievalLog.objects.filter(session_id=session.id).order_by('-created_at').first()
        if log:
            chunk_ids = log.retrieved_chunk_ids or []
            titles = list(
                KnowledgeChunk.objects.filter(id__in=chunk_ids)
                .values_list('document__title', flat=True)
            )
            # preserve order, dedupe
            seen = set()
            retrieved_docs = [t for t in titles if not (t in seen or seen.add(t))]
            scores = log.similarity_scores or []
            if scores:
                top_similarity = round(max(scores), 4)

        results.append({
            'id': qid,
            'category': category,
            'question': ' || '.join(turns),
            'expected': (row.get('expected') or '').strip(),
            'response': (final_state.get('response') or '').replace('\n', ' '),
            'intents': ', '.join(final_state.get('intents') or []),
            'tool_category': final_state.get('_tool_category') or '',
            'confidence': round(final_state.get('confidence') or 0.0, 3),
            'confidence_band': final_state.get('confidence_band') or '',
            'asked_clarification': bool(final_state.get('requires_clarification')),
            'handover': bool(final_state.get('requires_handover')),
            'handover_reason': final_state.get('handover_reason') or '',
            'retrieved_docs': ' | '.join(retrieved_docs),
            'top_similarity': top_similarity,
            'elapsed_seconds': round(elapsed_total, 2),
            'outcome_TP_FP_FN_TN': '',   # ← fill in manually while scoring
            'notes': '',
        })
        print(f'  [{i}/{len(rows)}] {qid}  band={results[-1]["confidence_band"] or "-":6s} '
              f'handover={"Y" if results[-1]["handover"] else "n"} '
              f'clarify={"Y" if results[-1]["asked_clarification"] else "n"} '
              f'({results[-1]["elapsed_seconds"]}s)')

    with open(results_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f'\nWrote {len(results)} results to {results_path}')

    if keep_sessions:
        print(f'Kept {len(created_session_ids)} sessions for Audit Log inspection.')
    else:
        deleted = ChatSession.objects.filter(id__in=created_session_ids).delete()
        print(f'Cleaned up {len(created_session_ids)} evaluation sessions: {deleted[0]} rows.')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        sys.exit('Usage: python evaluation_runner.py <dataset.csv> <results.csv> [--keep]')
    run_dataset(args[0], args[1], keep_sessions='--keep' in sys.argv)
