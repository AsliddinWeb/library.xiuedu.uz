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

    path('genres/', cs, {'active': 'genres', 'title': 'Kataloglar'}, name='genres'),
    path('authors/', cs, {'active': 'authors', 'title': 'Mualliflar'}, name='authors'),
    path('import/', cs, {'active': 'import', 'title': 'Import'}, name='import_books'),

    # Sirkulyatsiya
    path('requests/', cs, {'active': 'requests', 'title': "Ijara so'rovlari"}, name='requests'),
    path('rentals/', cs, {'active': 'rentals', 'title': 'Ijaralar'}, name='rentals'),
    path('reservations/', cs, {'active': 'reservations', 'title': 'Navbatlar'}, name='reservations'),
    path('fines/', cs, {'active': 'fines', 'title': 'Jarimalar'}, name='fines'),

    # Tizim
    path('reviews/', cs, {'active': 'reviews', 'title': 'Sharhlar'}, name='reviews'),
    path('members/', cs, {'active': 'members', 'title': 'Talabalar'}, name='members'),
    path('analytics/', cs, {'active': 'analytics', 'title': 'Analitika'}, name='analytics'),
    path('settings/', cs, {'active': 'settings', 'title': 'Sozlamalar'}, name='settings'),
]
