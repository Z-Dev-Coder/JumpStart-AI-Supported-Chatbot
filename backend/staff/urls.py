from django.urls import path
from . import views

urlpatterns = [
    path('queue/', views.QueueView.as_view(), name='staff-queue'),
    path('cases/<int:case_id>/accept/', views.AcceptCaseView.as_view(), name='accept-case'),
    path('cases/<int:case_id>/resolve/', views.ResolveCaseView.as_view(), name='resolve-case'),
    path('cases/<int:case_id>/return-to-ai/', views.ReturnToAIView.as_view(), name='return-to-ai'),
    path('cases/<int:case_id>/messages/', views.CaseMessagesView.as_view(), name='case-messages'),
    path('overview/', views.AdminOverviewView.as_view(), name='admin-overview'),
    path('sessions/<uuid:session_id>/agent-log/', views.SessionAgentLogView.as_view(), name='session-agent-log'),
]
