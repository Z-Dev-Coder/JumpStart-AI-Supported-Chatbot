import os
from django.apps import AppConfig


class ServicesConfig(AppConfig):
    name = 'services'

    def ready(self):
        # Under `runserver`, Django imports every app twice (once in the
        # autoreloader's watcher process). Only warm models in the actual
        # worker process, or a chat message during the first ~25s after
        # boot pays the full model-load cost synchronously and looks frozen.
        if 'RUN_MAIN' in os.environ and os.environ.get('RUN_MAIN') != 'true':
            return

        import threading

        def _warm():
            from services.sentiment import get_pipeline
            get_pipeline()
            from rag.embeddings import get_model
            get_model()

        threading.Thread(target=_warm, daemon=True).start()
