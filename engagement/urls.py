from django.urls import path

from . import views

app_name = "engagement"

urlpatterns = [
    path('my-library/', views.my_library, name='my_library'),

    # Talaba amallari (HTMX)
    path('books/<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('books/<int:pk>/review/', views.submit_review, name='submit_review'),

    # Moderatsiya
    path('moderate/', views.moderate, name='moderate'),
    path('reviews/<int:pk>/approve/', views.approve_review, name='approve_review'),
    path('reviews/<int:pk>/reject/', views.reject_review, name='reject_review'),
]
