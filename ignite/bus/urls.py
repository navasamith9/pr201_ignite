from django.urls import path
from . import views

app_name = 'bus'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add/', views.add_bus, name='add_bus'),
    path('book/', views.book_ticket, name='book_ticket'),
    path('checkout/', views.checkout, name='checkout'),
    path('previous/', views.previous_bookings, name='previous_bookings'),
    path('ticket/<uuid:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('ticket/<uuid:ticket_id>/download/', views.download_ticket, name='download_ticket'),
    path('verify/', views.verify_ticket, name='verify_ticket'),
]
