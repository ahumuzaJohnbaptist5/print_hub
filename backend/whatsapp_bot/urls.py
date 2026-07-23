from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.webhook_view, name='whatsapp_webhook'),
    path('health/', views.health_check, name='whatsapp_health'),
]
