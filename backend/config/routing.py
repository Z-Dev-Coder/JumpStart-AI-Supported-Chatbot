from django.urls import re_path
from chatbot.consumers import ChatConsumer
from staff.consumers import StaffConsumer, StaffQueueConsumer, AdminAuditConsumer

websocket_urlpatterns = [
    re_path(r'^ws/chat/(?P<session_id>[^/]+)/$', ChatConsumer.as_asgi()),
    # Queue route must precede the generic case route
    re_path(r'^ws/staff/queue/$', StaffQueueConsumer.as_asgi()),
    re_path(r'^ws/staff/(?P<case_id>[^/]+)/$', StaffConsumer.as_asgi()),
    re_path(r'^ws/admin/audit/(?P<session_id>[^/]+)/$', AdminAuditConsumer.as_asgi()),
]
