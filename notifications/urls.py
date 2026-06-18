from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('dropdown/', views.dropdown, name='dropdown'),
    path('<int:pk>/read/', views.mark_read, name='read'),
    path('read-all/', views.read_all, name='read_all'),
]
