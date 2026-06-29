from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email_view, name='verify_email'),
]
