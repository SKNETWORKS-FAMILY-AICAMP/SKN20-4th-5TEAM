from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('map/', views.shelter_map, name='shelter_map'),
]