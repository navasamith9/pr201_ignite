"""
URL configuration for ignite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('scheduler/', views.scheduler, name='scheduler'),
    path('scheduler/room-booking/', views.scheduler_room_booking, name='scheduler-room-booking'),
    path('scheduler/activity/', views.scheduler_activity, name='scheduler-activity'),
    path('scheduler/campus-schedule/', views.scheduler_campus_schedule, name='scheduler-campus-schedule'),
    path('scheduler/add-room/', views.scheduler_add_room, name='scheduler-add-room'),
    path('scheduler/timetable-entries/', views.scheduler_timetable_entries, name='scheduler-timetable-entries'),
    path('scheduler/grant-access/', views.scheduler_grant_access, name='scheduler-grant-access'),
    path('admin/', admin.site.urls),

    path('accounts/', include('allauth.urls')),
    path('accounts/', include('accounts.urls')),
    path('bus/', include('bus.urls')),
    path('canteen/', include('canteen.urls')),
    path('phc/', include('phc.urls')),
    path('payments/', include('payments.urls')),
    path('lost-and-found/', include('lost_and_found.urls')),
    path('chatbot/', include('chatbot.urls')),
    path('api/scheduler/', include('scheduler.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
