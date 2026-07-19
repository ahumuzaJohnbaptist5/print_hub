from django.urls import path
from . import views

urlpatterns = [
    path('api/', views.get_notifications, name='get_notifications'),
    path('mark-read/<int:notification_id>/', views.mark_read, name='mark_notification_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
]
