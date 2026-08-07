from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.chatbot_home, name='index'),
    path('api/query/', views.query_api, name='query_api'),
    path('api/suggestions/', views.suggestions_api, name='suggestions_api'),
]
