from django.urls import path
from . import views

urlpatterns = [
    path('api/process-file/', views.process_file, name='process_file'),
    path('api/file-preview/<int:order_id>/', views.file_preview, name='file_preview'),
    path('api/file-info/<int:order_id>/', views.file_info, name='file_info'),
]
