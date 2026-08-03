from django.urls import path
from .views import AssistantChatView, AssistantUploadView

urlpatterns = [
    path('chat/', AssistantChatView.as_view(), name='assistant-chat'),
    path('upload/', AssistantUploadView.as_view(), name='assistant-upload'),
]
