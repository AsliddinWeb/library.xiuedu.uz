from django.urls import path

from .views import analytics, dashboard, home

urlpatterns = [
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('analytics/', analytics, name='analytics'),
]
