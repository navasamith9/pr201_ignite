from django.urls import path
from . import views
app_name = 'phc'
urlpatterns = [
    path('', views.home, name='home'), path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'), path('queue/', views.queue, name='queue'), path('notifications/', views.notifications, name='notifications'),
    path('doctors/<int:doctor_id>/subscribe/', views.subscribe, name='subscribe'), path('doctors/<int:doctor_id>/unsubscribe/', views.unsubscribe, name='unsubscribe'), path('doctors/<int:doctor_id>/join/', views.join_queue, name='join_queue'), path('queue/<int:entry_id>/leave/', views.leave_queue, name='leave_queue'),
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'), path('doctor/status/', views.update_status, name='update_status'), path('doctor/queue/<int:entry_id>/', views.queue_action, name='queue_action'), path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
]
