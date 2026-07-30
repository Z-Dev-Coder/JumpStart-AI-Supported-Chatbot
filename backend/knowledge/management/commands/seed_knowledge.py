"""
Management command: python manage.py seed_knowledge

Loads the knowledge base from a single Question/Answer/Category CSV
(knowledge/jumpstart_kb.csv) instead of the previous set of 10 separate
policy documents (txt/docx/csv/pdf, one per topic). Each CSV row becomes
its own KnowledgeChunk — a Q&A pair is the natural retrieval unit for this
content, so rows are embedded directly rather than run through the
word-count splitter, which existed to break up long prose documents that
no longer exist here.

Destructive and idempotent: every run wipes all existing KnowledgeDocument/
KnowledgeChunk rows first, then rebuilds from the CSV — this is a full
replace, not a merge, so re-running after editing the CSV always reflects
exactly what's in the file.
"""
import csv

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.utils import timezone
from pathlib import Path

from knowledge.models import KnowledgeDocument, KnowledgeChunk
from rag.embeddings import embed_texts

User = get_user_model()

CSV_PATH = Path(__file__).resolve().parent.parent.parent / 'jumpstart_kb.csv'
DOCUMENT_TITLE = 'JumpStart Knowledge Base (Q&A)'


class Command(BaseCommand):
    help = 'Wipe and reseed the knowledge base from the single Q&A CSV (knowledge/jumpstart_kb.csv).'

    def handle(self, *args, **options):
        admin = User.objects.filter(role='admin').first()

        with open(CSV_PATH, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        if not rows:
            self.stdout.write(self.style.ERROR(f'No rows found in {CSV_PATH}'))
            return

        # Full replace: any document/chunk from a prior seeding scheme (or a
        # prior run of this one) is deleted first, not merged with — see
        # module docstring. Queryset .delete() only removes DB rows, not the
        # underlying files in storage (Django doesn't cascade that), so the
        # actual files are removed explicitly here too — otherwise every
        # re-run orphans another copy under media/knowledge_docs/.
        old_docs = list(KnowledgeDocument.objects.all())
        for old_doc in old_docs:
            if old_doc.file:
                old_doc.file.delete(save=False)
        deleted_docs, _ = KnowledgeDocument.objects.all().delete()
        self.stdout.write(f'Cleared existing knowledge base ({deleted_docs} rows across documents/chunks, '
                           f'{len(old_docs)} file(s) removed from storage).')

        csv_bytes = CSV_PATH.read_bytes()
        doc = KnowledgeDocument.objects.create(
            title=DOCUMENT_TITLE,
            file_type='csv',
            topic=KnowledgeDocument.Topic.GENERAL,
            policy_version='v2.0',
            status=KnowledgeDocument.Status.APPROVED,
            active=True,
            uploaded_by=admin,
            approved_by=admin,
            approval_date=timezone.now(),
        )
        doc.file.save('jumpstart_kb.csv', ContentFile(csv_bytes), save=False)
        doc.extracted_text = '\n'.join(f"Q: {r['Question']} A: {r['Answer']}" for r in rows)
        doc.save()

        embeddings = embed_texts([f"{r['Question']} {r['Answer']}" for r in rows])
        for idx, (row, embedding) in enumerate(zip(rows, embeddings)):
            KnowledgeChunk.objects.create(
                document=doc,
                chunk_text=f"Q: {row['Question']} A: {row['Answer']}",
                chunk_index=idx,
                metadata={
                    'category': row.get('Category', ''),
                    'source': doc.title,
                    'policy_version': doc.policy_version,
                    'approval_status': doc.status,
                },
                embedding=embedding,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(rows)} Q&A chunks from {CSV_PATH.name} into "{DOCUMENT_TITLE}".'
        ))
