from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.ChatSessionListCreateView.as_view(), name='chat-sessions'),
    path('sessions/active/', views.ActiveChatSessionView.as_view(), name='active-chat-session'),
    path('sessions/new/', views.NewChatSessionView.as_view(), name='new-chat-session'),
    path('sessions/<uuid:pk>/', views.ChatSessionDetailView.as_view(), name='chat-session-detail'),
    path('sessions/<uuid:session_id>/messages/', views.ChatMessageListView.as_view(), name='chat-messages'),
    path('sessions/<uuid:session_id>/send/', views.SendMessageView.as_view(), name='send-message'),
    path('sessions/<uuid:session_id>/feedback/', views.SubmitFeedbackView.as_view(), name='submit-feedback'),
    path('sessions/<uuid:session_id>/end/', views.EndChatSessionView.as_view(), name='end-chat-session'),
]
