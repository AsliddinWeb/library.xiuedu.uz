import json
from datetime import timedelta

from django.db.models import Count
from django.shortcuts import render
from django.utils.timezone import now

from book_app.models import Book, Genre, Rental
from circulation.models import Fine, RentalRequest, Reservation
from engagement.models import Review
from user_app.models import StudentProfile
from user_app.utils import library_admin_role_required


@library_admin_role_required
def dashboard(request):
    today = now().date()

    pending = RentalRequest.objects.filter(status=RentalRequest.Status.PENDING)
    overdue_qs = (Rental.objects
                  .filter(return_date__isnull=True, due_date__lt=today)
                  .select_related('copy__book', 'student__user'))

    stats = {
        'pending_requests': pending.count(),
        'active_rentals': Rental.objects.filter(return_date__isnull=True).count(),
        'overdue': overdue_qs.count(),
        'reservations': Reservation.objects.filter(status=Reservation.Status.WAITING).count(),
        'unpaid_fines': Fine.objects.filter(is_paid=False).count(),
        'pending_reviews': Review.objects.filter(is_approved=False).count(),
        'books': Book.objects.count(),
        'students': StudentProfile.objects.count(),
    }

    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    counts = {d: 0 for d in days}
    for d in Rental.objects.filter(borrowed_date__gte=days[0]).values_list('borrowed_date', flat=True):
        if d in counts:
            counts[d] += 1
    rentals_chart = {'labels': [d.strftime('%d.%m') for d in days], 'data': [counts[d] for d in days]}

    cats = Genre.objects.annotate(c=Count('book')).filter(c__gt=0).order_by('-c')[:6]
    cats_chart = {'labels': [g.name for g in cats], 'data': [g.c for g in cats]}

    ctx = {
        'active': 'dashboard',
        'page_title': 'Boshqaruv paneli',
        'stats': stats,
        'recent_requests': pending.select_related('book', 'student__user')[:6],
        'overdue': overdue_qs[:6],
        'rentals_chart': json.dumps(rentals_chart),
        'cats_chart': json.dumps(cats_chart),
    }
    return render(request, 'panel/dashboard.html', ctx)


@library_admin_role_required
def coming_soon(request, active='', title='Bo\'lim'):
    return render(request, 'panel/coming_soon.html', {'active': active, 'page_title': title})
