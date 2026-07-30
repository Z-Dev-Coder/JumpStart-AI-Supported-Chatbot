from django.urls import path
from . import views

urlpatterns = [
    path('documents/', views.KnowledgeDocumentListView.as_view(), name='knowledge-list'),
    path('documents/upload/', views.KnowledgeDocumentUploadView.as_view(), name='knowledge-upload'),
    path('documents/<int:doc_id>/', views.KnowledgeDocumentDetailView.as_view(), name='knowledge-detail'),
    path('documents/<int:doc_id>/approve/', views.ApproveDocumentView.as_view(), name='knowledge-approve'),
    path('documents/<int:doc_id>/disable/', views.DisableDocumentView.as_view(), name='knowledge-disable'),
    path('feedback/', views.FeedbackListView.as_view(), name='admin-feedback'),
    path('feedback/<int:feedback_id>/reviewed/', views.MarkFeedbackReviewedView.as_view(), name='feedback-reviewed'),
    path('rag-metrics/', views.RAGMetricsView.as_view(), name='rag-metrics'),
]
