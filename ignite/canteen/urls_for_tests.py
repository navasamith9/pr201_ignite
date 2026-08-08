from django.urls import include, path


urlpatterns = [
    path('', include(('canteen.urls', 'canteen'), namespace='canteen')),
]
