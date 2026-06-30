from django.urls import path
from . import views

urlpatterns = [
    path('order/<int:order_id>/', views.payment_page, name='payment_page'),
    path('status/<int:payment_id>/', views.payment_status, name='payment_status'),
    path('extract-transaction/', views.extract_transaction_id, name='extract_transaction_id'),
    path('admin/approve/', views.admin_approve_payments, name='admin_approve_payments'),
]
