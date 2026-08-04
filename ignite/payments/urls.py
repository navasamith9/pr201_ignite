from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/', views.razorpay_checkout, name='checkout'),
    path('confirm/', views.razorpay_confirm, name='confirm'),
]
