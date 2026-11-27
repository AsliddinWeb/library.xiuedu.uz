from django.urls import path

from . import views

app_name = "panel"

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

    # Nusxalar (fond)
    path('items/', views.item_list, name='items'),
    path('items/<int:pk>/', views.item_detail, name='item_detail'),
    path('items/<int:pk>/status/', views.item_status, name='item_status'),
    path('books/<int:pk>/items/bulk/', views.item_bulk, name='item_bulk'),

    # Fond tuzilmasi (filial / tur / javon)
    path('holdings/', views.holdings_overview, name='holdings'),
    path('holdings/<str:kind>/<int:pk>/edit/', views.holdings_edit, name='holdings_edit'),
    path('holdings/<str:kind>/<int:pk>/toggle/', views.holdings_toggle, name='holdings_toggle'),

    # Skaner uchun tezkor qidiruv
    path('search/', views.quick_search, name='quick_search'),

    path('import/', views.import_books, name='import_books'),

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
    path('reviews/', views.reviews_view, name='reviews'),
    path('reviews/<int:pk>/approve/', views.review_approve, name='review_approve'),
    path('reviews/<int:pk>/reject/', views.review_reject, name='review_reject'),
    path('members/', views.members, name='members'),
    path('members/new/', views.member_create, name='member_create'),
    path('members/<int:pk>/', views.member_detail, name='member_detail'),
    path('members/<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('members/<int:pk>/block/', views.member_block, name='member_block'),
    path('members/<int:pk>/unblock/', views.member_unblock, name='member_unblock'),
    path('members/<int:pk>/renew/', views.member_renew, name='member_renew'),
    path('analytics/', views.analytics, name='analytics'),
    path('settings/', views.settings_view, name='settings'),
]
