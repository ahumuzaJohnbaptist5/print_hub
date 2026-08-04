# backend/employees/urls.py
from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    # Public
    path('apply/', views.application_form_view, name='apply'),
    path('apply/success/', views.application_success_view, name='application_success'),
    
    # Admin
    path('admin/applications/', views.application_list_view, name='application_list'),
    path('admin/applications/<int:application_id>/', views.application_detail_view, name='application_detail'),
]
