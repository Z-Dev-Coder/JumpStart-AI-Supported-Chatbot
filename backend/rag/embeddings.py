from __future__ import annotations
import threading
from typing import List

_model = None
_lock = threading.Lock()

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    return embed_texts([query])[0]


def embed_document_async(doc_id: int):
    """Trigger embedding generation in a background thread."""
    thread = threading.Thread(target=_embed_document, args=(doc_id,), daemon=True)
    thread.start()


def _embed_document(doc_id: int):
    """Generate and store embeddings for all chunks of a document."""
    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    from knowledge.models import KnowledgeDocument, KnowledgeChunk
    from rag.loader import extract_text_from_file, clean_text
    from rag.splitter import split_into_chunks

    try:
        doc = KnowledgeDocument.objects.get(id=doc_id)
        text = clean_text(doc.extracted_text or extract_text_from_file(doc.file.path, doc.file_type))
        chunks = split_into_chunks(text)

        # Delete existing chunks before re-embedding
        KnowledgeChunk.objects.filter(document=doc).delete()

        metadata = {
            'topic': doc.topic,
            'source': doc.title,
            'policy_version': doc.policy_version,
            'approval_status': doc.status,
        }

        embeddings = embed_texts(chunks)

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            KnowledgeChunk.objects.create(
                document=doc,
                chunk_text=chunk_text,
                chunk_index=idx,
                metadata=metadata,
                embedding=embedding,
            )
    except Exception as e:
        print(f'[Embedding error for doc {doc_id}]: {e}')
