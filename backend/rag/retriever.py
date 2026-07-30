from typing import List, Dict, Any
from .embeddings import embed_query

# Cosine similarity floor for all-MiniLM-L6-v2 — question-vs-policy-paragraph
# pairs for a correct match typically score 0.45-0.70 with this model.
# Widened from 0.45/5 after the 26-question evaluation run showed the correct
# chunk was sometimes retrieved but ranked below the top-5, or excluded by
# the threshold — e.g. general vs. category-specific return-window rows
# scoring close to each other. Lower threshold + more candidates trades some
# precision for recall; re-check Precision@5 after this change, not just
# whether the previously-missed chunks now show up.
# TOP_K brought back down to 5 after the KB dedup pass (102 -> 80 rows):
# each chunk is now denser and non-redundant, so fewer chunks are needed to
# cover an answer, and the LLM has less to reason over per generation call.
SIMILARITY_THRESHOLD = 0.40
TOP_K = 5


def retrieve_knowledge(query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant knowledge chunks via pgvector cosine similarity.

    No topic filter: the knowledge base is a single Q&A document (see
    seed_knowledge.py) rather than one document per topic, so document-level
    topic filtering has nothing left to narrow — similarity search alone
    does the work now.
    """
    from django.db import connection

    query_embedding = embed_query(query)
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    base_sql = """
        SELECT
            kc.id,
            kc.chunk_text,
            kc.metadata,
            kd.title as source_title,
            kd.topic,
            kd.policy_version,
            1 - (kc.embedding <=> %s::vector) AS similarity
        FROM knowledge_chunks kc
        JOIN knowledge_documents kd ON kc.document_id = kd.id
        WHERE kc.active = TRUE
          AND kd.active = TRUE
          AND kd.status = 'approved'
        ORDER BY kc.embedding <=> %s::vector
        LIMIT %s
    """
    params = [embedding_str, embedding_str, top_k]

    with connection.cursor() as cursor:
        cursor.execute(base_sql, params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    results = []
    for row in rows:
        item = dict(zip(columns, row))
        if item['similarity'] >= SIMILARITY_THRESHOLD:
            results.append(item)

    return results


def check_retrieval_quality(results: List[Dict]) -> Dict[str, Any]:
    """Assess whether retrieved chunks are sufficient for a grounded answer."""
    if not results:
        return {'sufficient': False, 'reason': 'no_results', 'top_score': 0.0}

    top_score = results[0]['similarity']
    if top_score < SIMILARITY_THRESHOLD:
        return {'sufficient': False, 'reason': 'low_similarity', 'top_score': top_score}

    return {'sufficient': True, 'reason': 'ok', 'top_score': top_score}
