from django.urls import path

from . import views

app_name = "reading"

urlpatterns = [
    path('read/<int:pk>/', views.read_book, name='read'),
    path('listen/<int:pk>/', views.listen_book, name='listen'),

    # Himoyalangan stream (inline, Range)
    path('stream/ebook/<int:pk>/', views.stream_ebook, name='stream_ebook'),
    path('stream/audio/<int:pk>/', views.stream_audio, name='stream_audio'),

    # Jarayonni saqlash
    path('progress/<int:pk>/', views.save_progress, name='save_progress'),
]
