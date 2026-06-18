from django.db.models import Count
from django.shortcuts import render

from book_app.models import Book, Copy, Rental
from circulation.models import RentalRequest, Fine
from reading.models import ReadingHistory
from user_app.models import User, StudentProfile
from user_app.utils import library_admin_role_required


@library_admin_role_required
def analytics(request):
    stats = {
        'books': Book.objects.count(),
        'copies': Copy.objects.count(),
        'active_rentals': Rental.objects.filter(return_date__isnull=True).count(),
        'pending_requests': RentalRequest.objects.filter(status=RentalRequest.Status.PENDING).count(),
        'users': User.objects.count(),
        'reads': ReadingHistory.objects.count(),
        'unpaid_fines': Fine.objects.filter(is_paid=False).count(),
        'students': StudentProfile.objects.count(),
    }

    most_viewed = list(Book.objects.filter(view_count__gt=0).order_by('-view_count')[:8])
    most_rented = list(
        Book.objects.annotate(rc=Count('copy__rental')).filter(rc__gt=0).order_by('-rc')[:8])
    top_rated = list(
        Book.objects.filter(rating_count__gt=0).order_by('-avg_rating', '-rating_count')[:8])
    active_students = list(
        StudentProfile.objects.annotate(rc=Count('rental')).filter(rc__gt=0)
        .order_by('-rc')[:8].select_related('user'))

    stats_cards = [
        ("Kitoblar", stats['books']),
        ("Nusxalar", stats['copies']),
        ("Faol ijaralar", stats['active_rentals']),
        ("Kutilayotgan so'rovlar", stats['pending_requests']),
        ("Talabalar", stats['students']),
        ("Foydalanuvchilar", stats['users']),
        ("O'qishlar", stats['reads']),
        ("To'lanmagan jarima", stats['unpaid_fines']),
    ]

    ctx = {
        'stats_cards': stats_cards,
        'most_viewed': most_viewed,
        'most_viewed_max': most_viewed[0].view_count if most_viewed else 0,
        'most_rented': most_rented,
        'most_rented_max': most_rented[0].rc if most_rented else 0,
        'top_rated': top_rated,
        'active_students': active_students,
        'active_students_max': active_students[0].rc if active_students else 0,
    }
    return render(request, 'dashboard/analytics.html', ctx)
