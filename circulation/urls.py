from django.urls import path

from . import views

app_name = "circulation"

urlpatterns = [
    path('my-rentals/', views.my_rentals, name='my_rentals'),

    # Kitob amallari (HTMX)
    path('books/<int:pk>/request/', views.request_rental, name='request_rental'),
    path('books/<int:pk>/request/cancel/', views.cancel_request, name='cancel_request'),
    path('books/<int:pk>/reserve/', views.reserve_book, name='reserve_book'),
    path('books/<int:pk>/reserve/cancel/', views.cancel_reservation, name='cancel_reservation'),

    # Kutubxonachi paneli
    path('manage/', views.manage, name='manage'),
    path('manage/request/<int:pk>/approve/', views.approve_request_view, name='approve_request'),
    path('manage/request/<int:pk>/reject/', views.reject_request_view, name='reject_request'),
    path('manage/rental/<int:pk>/return/', views.return_rental_view, name='return_rental'),
    path('manage/fine/<int:pk>/paid/', views.mark_fine_paid_view, name='mark_fine_paid'),
]
