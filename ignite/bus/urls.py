from django.urls import path
from . import views

app_name = 'bus'
urlpatterns = [
    path('', views.book_ticket, name='book_ticket'),
]