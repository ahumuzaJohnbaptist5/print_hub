from django.urls import path
from . import views

urlpatterns = [
    path('order/<int:order_id>/', views.initiate_payment, name='initiate_payment'),
    path('confirm/<uuid:transaction_id>/', views.payment_confirmation, name='payment_confirmation'),
    path('check/<uuid:transaction_id>/', views.check_payment_status, name='check_payment_status'),
    path('success/<uuid:transaction_id>/', views.payment_success, name='payment_success'),
]
