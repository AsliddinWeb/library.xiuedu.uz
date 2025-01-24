from django.urls import path

from .views import authors_list, author_edit, author_create, author_delete, student_book_detail, save_books

app_name = "book_app"

urlpatterns = [
    # Student
    path('<int:pk>/', student_book_detail, name='student_book_detail'),

    # Library Admin
    path('authors/list/', authors_list, name='authors_list'),

    path('authors/create/', author_create, name='author_create'),
    path('authors/edit/<int:author_id>/', author_edit, name='author_edit'),
    path('authors/delete/<int:author_id>/', author_delete, name='author_delete'),

    path('save-books/', save_books, name='save_books'),
]
