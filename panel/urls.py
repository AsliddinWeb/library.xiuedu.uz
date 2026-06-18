from django.urls import path

from . import views

app_name = "panel"

# Hali qurilmagan bo'limlar — coming_soon (PART C-F da real view bilan almashtiriladi)
cs = views.coming_soon

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Katalog
    path('books/', cs, {'active': 'books', 'title': 'Kitoblar'}, name='books'),
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
