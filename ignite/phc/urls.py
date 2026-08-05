from django.urls import path
from . import views
app_name = 'phc'
urlpatterns = [
    path('', views.home, name='home'), path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'), path('queue/', views.queue, name='queue'), path('notifications/', views.notifications, name='notifications'),
    path('doctors/<int:doctor_id>/subscribe/', views.subscribe, name='subscribe'), path('doctors/<int:doctor_id>/unsubscribe/', views.unsubscribe, name='unsubscribe'), path('doctors/<int:doctor_id>/join/', views.join_queue, name='join_queue'), path('queue/<int:entry_id>/leave/', views.leave_queue, name='leave_queue'),
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'), path('doctor/status/', views.update_status, name='update_status'), path('doctor/appointments/<int:entry_id>/', views.queue_action, name='queue_action'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'), path('admin/doctors/', views.admin_doctors, name='admin_doctors'), path('admin/doctors/add/', views.admin_doctor_edit, name='admin_doctor_add'), path('admin/doctors/<int:doctor_id>/edit/', views.admin_doctor_edit, name='admin_doctor_edit'), path('admin/schedules/', views.admin_schedules, name='admin_schedules'), path('admin/announcements/', views.admin_announcements, name='admin_announcements'), path('admin/settings/', views.admin_settings, name='admin_settings'), path('admin/queue/', views.admin_queue, name='admin_queue'), path('admin/queue/<int:entry_id>/remove/', views.admin_queue_remove, name='admin_queue_remove'),
]
