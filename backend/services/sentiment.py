import threading
from typing import Literal

_pipeline = None
_lock = threading.Lock()
SentimentLabel = Literal['positive', 'neutral', 'negative']


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        with _lock:
            if _pipeline is None:
                try:
                    from transformers import pipeline
                    _pipeline = pipeline(
                        'text-classification',
                        model='cardiffnlp/twitter-roberta-base-sentiment-latest',
                        top_k=1,
                    )
                except Exception as e:
                    print(f'[Sentiment] Failed to load model: {e}. Using keyword fallback.')
                    _pipeline = 'fallback'
    return _pipeline


def analyse_sentiment(text: str) -> SentimentLabel:
    pipe = get_pipeline()

    if pipe == 'fallback':
        return _keyword_fallback(text)

    try:
        result = pipe(text[:512], truncation=True)
        label = result[0][0]['label'].lower()
        if 'negative' in label or label == 'label_0':
            return 'negative'
        if 'positive' in label or label == 'label_2':
            return 'positive'
        return 'neutral'
    except Exception:
        return _keyword_fallback(text)


NEGATIVE_KEYWORDS = [
    'angry', 'frustrated', 'terrible', 'awful', 'horrible', 'useless',
    'disgusting', 'ridiculous', 'unacceptable', 'outraged', 'furious',
    'worst', 'disaster', 'scam', 'cheated', 'lied', 'broken', 'damaged',
]


def _keyword_fallback(text: str) -> SentimentLabel:
    lower = text.lower()
    if any(kw in lower for kw in NEGATIVE_KEYWORDS):
        return 'negative'
    return 'neutral'
