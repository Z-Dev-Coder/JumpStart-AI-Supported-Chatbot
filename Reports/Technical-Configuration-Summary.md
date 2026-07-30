# Technical Configuration Summary (for Findings & Analysis report)

## Final configuration (as of Evaluation 3)

| Parameter | Final value | File |
|---|---|---|
| LLM | Qwen2.5:3b-instruct-q4_K_M (local, Ollama) | `backend/.env` |
| Embedding model | Sentence Transformers `all-MiniLM-L6-v2` (384-dim) | `backend/rag/embeddings.py` |
| `TOP_K` (chunks retrieved) | 5 | `backend/rag/retriever.py` |
| `SIMILARITY_THRESHOLD` | 0.40 | `backend/rag/retriever.py` |
| `_KB_OVERRIDE_THRESHOLD` (skip-clarification bar) | 0.58 | `backend/agents/graph.py` |
| Knowledge base size | 80 Q&A rows | `backend/knowledge/jumpstart_kb.csv` |
| `MAX_CLARIFICATION_ATTEMPTS` | 2 | `backend/config/settings.py` |
| `CONFIDENCE_MEDIUM` (handover threshold) | 0.65 | `backend/config/settings.py` |

## What changed across the 3 evaluation rounds, and why

| Parameter | Eval 1 | Eval 2 | Eval 3 | Reason for change |
|---|---|---|---|---|
| LLM provider | Groq (cloud) | Ollama (local, cycled models) | Ollama, Qwen2.5:3b | Groq's 200k token/day quota was repeatedly exhausted during iterative testing |
| `SIMILARITY_THRESHOLD` | 0.45 | 0.40 | 0.40 | 26-question run showed correct chunks sometimes retrieved but ranked below the old top-5 cutoff |
| `TOP_K` | 5 | 8 | 5 | Raised to 8 to compensate for the old, redundant 102-row KB; brought back to 5 after dedup since denser, non-redundant chunks need fewer candidates |
| KB row count | ~100 (many duplicated/overlapping facts) | ~102 | 80 (deduplicated, then re-split for 2 dense multi-fact rows) | Removed rows that just restated another row's facts; later split delivery-options and promo-codes rows back apart after finding the model couldn't reliably synthesize/cherry-pick from a dense multi-fact chunk |
| `safety_check` graph node | Present | Removed | Removed | Redundant routing logic; removed to speed up iteration during evaluation |
| Deterministic backstops in `agents/graph.py` | 0 | ~6 (out-of-scope guard, account_info PII fix, exchange-question override, human-request pattern fix, etc.) | ~12 more (see below) | Prompt-only fixes proved unreliable on a 3B local model; deterministic checks held reliably where prompt wording did not |

## Deterministic backstops added in Evaluation 3 (the precision-focused round)

1. `order_tracking` intent no longer wins unconditional routing priority without an order number (same fix class as Eval 2's `account_info` PII bug).
2. Keyword-based overrides (exchange/return-window questions) now check the final recomputed `missing_fields`, not a stale snapshot.
3. `_force_knowledge` state key was declared in `SupportState` (a LangGraph gotcha — undeclared keys are silently dropped between graph nodes).
4. Entities no longer carry across an unrelated topic change mid-session unless the prior turn left an open clarification request.
5. Knowledge search now queries with the raw `customer_message`, not the LLM-paraphrased `customer_goal` (which sometimes echoed stale from a prior turn).
6. `'complaint'` intent only counts as "sensitive" (triggering a stricter confidence bar) when paired with negative sentiment — previously any complaint tag escalated regardless of sentiment.
7. Cancellation requests always route to a real order lookup requiring `order_number`, rather than falling through to a general KB policy answer.
8. Literal "track my order" requests are distinguished from "my order is stuck, what do I do" troubleshooting questions via a problem-description-word heuristic, since both produce identical intent/category classifications.
9. A hallucinated `promo_code` entity (invented by the LLM from a question that never named a code) is discarded unless it literally appears in the customer's message.
10. A deterministic contradiction-override: when the top retrieved KB chunk is affirmative but the generated response opens with a false negation ("We don't carry..."), the response is replaced with the chunk's own text. This was the single highest-impact fix for precision.

## Live system evidence (see `Reports/Screenshots/`)

- `Screenshots/01-04`: customer-facing chat flow (homepage, panel open, RAG Q&A, human handover).
- `Screenshots/Usability-Task-Walkthrough/`: technical verification of all 5 usability-script tasks (general question, clarification, out-of-scope, handover).
- `Screenshots/Admin-and-Staff-Dashboards/`: staff support queue + AI handover package (confidence, handover reason, detected intents), admin overview (resolution rate, avg confidence, sentiment breakdown), AI Performance page (Recall@5, Precision@5, Faithfulness, Answer Relevancy, per-intent confidence breakdown), and the full per-message audit log (detected intent, sentiment, extracted entities, tool called, retrieved chunks with similarity scores).
