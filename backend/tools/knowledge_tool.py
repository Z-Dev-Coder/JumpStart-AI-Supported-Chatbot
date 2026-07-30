from typing import Dict, Any
from rag.retriever import retrieve_knowledge, check_retrieval_quality


def search_knowledge_base(query: str) -> Dict[str, Any]:
    results = retrieve_knowledge(query=query)
    quality = check_retrieval_quality(results)

    return {
        'tool': 'search_knowledge_base',
        'success': quality['sufficient'],
        'chunks': results,
        'chunk_count': len(results),
        'top_similarity': quality['top_score'],
        'quality_reason': quality['reason'],
    }
