from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),

    # API routes
    path('api/auth/', include('accounts.urls')),
    path('api/store/', include('store.urls')),
    path('api/chat/', include('chatbot.urls')),
    path('api/staff/', include('staff.urls')),
    path('api/knowledge/', include('knowledge.urls')),

    # Template (frontend) routes — served by Django templates + HTMX
    path('', include('store.template_urls')),
    path('staff/', include('staff.template_urls')),
    path('admin-panel/', include('knowledge.template_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
