from django.urls import path
from . import views

app_name = 'referrals'

urlpatterns = [
    path('dashboard/', views.referral_dashboard, name='dashboard'),
    path('invite/', views.referral_invite, name='invite'),
    path('history/', views.referral_history, name='history'),
    path('api/stats/', views.referral_stats_api, name='api_stats'),
]
