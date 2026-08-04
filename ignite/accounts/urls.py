from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('redirect/', views.post_login_redirect, name='post_login_redirect'),
]