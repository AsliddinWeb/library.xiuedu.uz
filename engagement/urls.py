from django.urls import path

from . import views

app_name = "engagement"

urlpatterns = [
    path('my-library/', views.my_library, name='my_library'),

    # Talaba amallari (HTMX)
    path('books/<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('books/<int:pk>/review/', views.submit_review, name='submit_review'),

    # Ro'yxatlar
    path('lists/', views.shelf_list, name='shelf_list'),
    path('lists/new/', views.shelf_create, name='shelf_create'),
    path('lists/<slug:slug>/', views.shelf_detail, name='shelf_detail'),
    path('lists/<slug:slug>/edit/', views.shelf_edit, name='shelf_edit'),
    path('lists/<slug:slug>/delete/', views.shelf_delete, name='shelf_delete'),
    path('lists/<slug:slug>/items/<int:book_pk>/remove/', views.shelf_remove_item,
         name='shelf_remove_item'),
    path('lists/<slug:slug>/items/<int:book_pk>/note/', views.shelf_item_note,
         name='shelf_item_note'),
    path('books/<int:pk>/lists/', views.shelf_picker, name='shelf_picker'),
    path('books/<int:pk>/lists/new/', views.shelf_quick_add, name='shelf_quick_add'),
    path('books/<int:pk>/lists/<slug:slug>/toggle/', views.shelf_toggle, name='shelf_toggle'),

    # Moderatsiya
    path('moderate/', views.moderate, name='moderate'),
    path('reviews/<int:pk>/approve/', views.approve_review, name='approve_review'),
    path('reviews/<int:pk>/reject/', views.reject_review, name='reject_review'),
]
