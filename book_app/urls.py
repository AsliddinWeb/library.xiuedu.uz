from django.urls import path

from .views import (
    author_create,
    author_delete,
    author_edit,
    authors_list,
    course_add_book,
    course_book_search,
    course_create,
    course_delete,
    course_detail,
    course_edit,
    course_list,
    course_remove_book,
    course_update_item,
    save_books,
    student_book_detail,
    student_book_list,
)

app_name = "book_app"

urlpatterns = [
    # Student
    path('', student_book_list, name='student_book_list'),
    path('<int:pk>/', student_book_detail, name='student_book_detail'),

    # Fan adabiyoti
    path('courses/', course_list, name='course_list'),
    path('courses/new/', course_create, name='course_create'),
    path('courses/<int:pk>/', course_detail, name='course_detail'),
    path('courses/<int:pk>/edit/', course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', course_delete, name='course_delete'),
    path('courses/<int:pk>/search/', course_book_search, name='course_book_search'),
    path('courses/<int:pk>/books/<int:book_pk>/add/', course_add_book, name='course_add_book'),
    path('courses/<int:pk>/books/<int:book_pk>/remove/', course_remove_book,
         name='course_remove_book'),
    path('courses/<int:pk>/books/<int:book_pk>/update/', course_update_item,
         name='course_update_item'),

    # Library Admin
    path('authors/list/', authors_list, name='authors_list'),

    path('authors/create/', author_create, name='author_create'),
    path('authors/edit/<int:author_id>/', author_edit, name='author_edit'),
    path('authors/delete/<int:author_id>/', author_delete, name='author_delete'),

    path('save-books/', save_books, name='save_books'),
]
