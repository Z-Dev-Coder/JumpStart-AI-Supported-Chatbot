from rest_framework import serializers
from .models import KnowledgeDocument, KnowledgeChunk


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            'id', 'title', 'file_type', 'topic', 'policy_version',
            'status', 'active', 'upload_date', 'approval_date',
            'usage_count', 'uploaded_by_name', 'chunk_count',
        ]

    def get_chunk_count(self, obj):
        return obj.chunks.count()


class KnowledgeDocumentDetailSerializer(KnowledgeDocumentSerializer):
    class Meta(KnowledgeDocumentSerializer.Meta):
        fields = KnowledgeDocumentSerializer.Meta.fields + ['extracted_text']
