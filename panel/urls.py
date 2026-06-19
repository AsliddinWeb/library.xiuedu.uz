from django.urls import path

from . import views

app_name = "panel"

# Hali qurilmagan bo'limlar — coming_soon (PART C-F da real view bilan almashtiriladi)
cs = views.coming_soon

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Katalog — Kitoblar (to'liq CRUD)
    path('books/', views.book_list, name='books'),
    path('books/new/', views.book_create, name='book_create'),
    path('books/<int:pk>/', views.book_detail, name='book_detail'),
    path('books/<int:pk>/edit/', views.book_edit, name='book_edit'),
    path('books/<int:pk>/delete/', views.book_delete, name='book_delete'),
    path('books/<int:pk>/copies/add/', views.copy_add, name='copy_add'),
    path('copies/<int:pk>/toggle/', views.copy_toggle, name='copy_toggle'),
    path('copies/<int:pk>/delete/', views.copy_delete, name='copy_delete'),

    # Kataloglar (Genre)
    path('genres/', views.genre_list, name='genres'),
    path('genres/new/', views.genre_create, name='genre_create'),
    path('genres/<int:pk>/edit/', views.genre_edit, name='genre_edit'),
    path('genres/<int:pk>/toggle/', views.genre_toggle, name='genre_toggle'),
    path('genres/<int:pk>/delete/', views.genre_delete, name='genre_delete'),

    # Mualliflar (Author)
    path('authors/', views.author_list, name='authors'),
    path('authors/new/', views.author_create, name='author_create'),
    path('authors/<int:pk>/edit/', views.author_edit, name='author_edit'),
    path('authors/<int:pk>/delete/', views.author_delete, name='author_delete'),

    path('import/', cs, {'active': 'import', 'title': 'Import'}, name='import_books'),

    # Sirkulyatsiya
    path('requests/', views.requests_view, name='requests'),
    path('requests/<int:pk>/approve/', views.request_approve, name='request_approve'),
    path('requests/<int:pk>/reject/', views.request_reject, name='request_reject'),
    path('rentals/', views.rentals_view, name='rentals'),
    path('rentals/<int:pk>/return/', views.rental_return, name='rental_return'),
    path('reservations/', views.reservations_view, name='reservations'),
    path('reservations/<int:pk>/cancel/', views.reservation_cancel, name='reservation_cancel'),
    path('fines/', views.fines_view, name='fines'),
    path('fines/<int:pk>/paid/', views.fine_mark_paid, name='fine_mark_paid'),

    # Tizim
    path('reviews/', cs, {'active': 'reviews', 'title': 'Sharhlar'}, name='reviews'),
    path('members/', cs, {'active': 'members', 'title': 'Talabalar'}, name='members'),
    path('analytics/', cs, {'active': 'analytics', 'title': 'Analitika'}, name='analytics'),
    path('settings/', cs, {'active': 'settings', 'title': 'Sozlamalar'}, name='settings'),
]
