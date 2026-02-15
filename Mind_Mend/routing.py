from django.urls import re_path

from .consumers import CounsellorChatConsumer, DoctorNotificationConsumer


websocket_urlpatterns = [
    re_path(r'^ws/booking/(?P<booking_id>\d+)/chat/$', CounsellorChatConsumer.as_asgi()),
    re_path(r'^ws/doctor/notifications/$', DoctorNotificationConsumer.as_asgi()),
]
