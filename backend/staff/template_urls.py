from django.urls import path
from . import views

urlpatterns = [
    path('', views.staff_dashboard, name='staff-dashboard'),
    path('account/', views.staff_account, name='staff-account'),
    path('<int:case_id>/', views.staff_case_view, name='staff-case'),
]
