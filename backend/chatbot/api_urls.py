from django.urls import path

from rag import api_views

urlpatterns = [
    path("health/", api_views.health, name="api-health"),
    path("ingest/", api_views.ingest, name="api-ingest"),
    path("chat/", api_views.chat, name="api-chat"),
]
