from django.urls import path

from . import views


urlpatterns = [
    path("chat", views.chat, name="chat"),
    path("sessions/<str:id>/messages", views.session_messages, name="session-messages"),
    path("feedback", views.feedback, name="feedback"),
    path("sources/<str:source_id>", views.source_by_id, name="source-by-id"),
    path("ingest", views.ingest, name="ingest"),
]
