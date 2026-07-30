import os
import sys
import threading

from django.apps import AppConfig


def _warm_up_models():
    """Load the sentiment and embedding models so the first customer message
    doesn't pay the multi-minute cold start (which can starve the CPU and
    time out the Groq call)."""
    try:
        from services.sentiment import get_pipeline
        get_pipeline()
        from rag.embeddings import get_model
        get_model()
        print('[warmup] sentiment + embedding models ready')
    except Exception as e:
        print(f'[warmup] model preload failed (will lazy-load instead): {e}')


class AgentsConfig(AppConfig):
    name = 'agents'

    def ready(self):
        argv = ' '.join(sys.argv).lower()
        # Warm up only in a serving process — not for migrate/shell/tests.
        if 'runserver' not in argv and 'daphne' not in argv:
            return
        # Under the runserver autoreloader only the child (RUN_MAIN=true)
        # serves requests; the parent is just the file watcher.
        if 'runserver' in argv and '--noreload' not in argv \
                and os.environ.get('RUN_MAIN') != 'true':
            return
        threading.Thread(target=_warm_up_models, daemon=True).start()
