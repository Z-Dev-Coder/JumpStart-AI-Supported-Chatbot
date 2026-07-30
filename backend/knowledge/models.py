from django.db import models
from django.conf import settings
from pgvector.django import VectorField


class KnowledgeDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        DISABLED = 'disabled', 'Disabled'
        REJECTED = 'rejected', 'Rejected'

    class Topic(models.TextChoices):
        RETURNS = 'returns', 'Returns & Refunds'
        DELIVERY = 'delivery', 'Delivery & Shipping'
        PAYMENTS = 'payments', 'Payments'
        WARRANTY = 'warranty', 'Warranty'
        PRODUCTS = 'products', 'Products'
        ORDERS = 'orders', 'Orders'
        STORE_INFO = 'store_info', 'Store Information'
        PROMOTIONS = 'promotions', 'Promotions'
        SUPPORT = 'support', 'Support Scripts'
        GENERAL = 'general', 'General FAQ'

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='knowledge_docs/')
    file_type = models.CharField(max_length=10, choices=[
        ('pdf', 'PDF'), ('docx', 'DOCX'), ('txt', 'TXT'), ('csv', 'CSV')
    ])
    topic = models.CharField(max_length=20, choices=Topic.choices, default=Topic.GENERAL)
    policy_version = models.CharField(max_length=20, blank=True)
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    active = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_docs'
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'knowledge_documents'
        ordering = ['-upload_date']

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name='chunks')
    chunk_text = models.TextField()
    chunk_index = models.PositiveIntegerField()
    # all-MiniLM-L6-v2 produces 384-dimensional embeddings
    embedding = VectorField(dimensions=384, null=True, blank=True)
    metadata = models.JSONField(default=dict)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'knowledge_chunks'
        ordering = ['document', 'chunk_index']

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"


class RAGRetrievalLog(models.Model):
    session = models.ForeignKey('chatbot.ChatSession', on_delete=models.CASCADE, related_name='rag_logs')
    message_id = models.PositiveIntegerField(null=True, blank=True)
    query_text = models.TextField()
    filters_used = models.JSONField(default=dict)
    retrieved_chunk_ids = models.JSONField(default=list)
    similarity_scores = models.JSONField(default=list)
    selected_chunk_ids = models.JSONField(default=list)
    verification_result = models.BooleanField(default=False)
    confidence_band = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rag_retrieval_logs'
