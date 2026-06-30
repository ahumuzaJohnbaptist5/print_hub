from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verify/<uuid:token>/', views.verify_email_view, name='verify_email'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Add this line for the Profile page
    path('profile/', views.profile_view, name='profile'), 
]
