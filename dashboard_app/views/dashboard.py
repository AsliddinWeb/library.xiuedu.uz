from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.timezone import localdate, now

from book_app.courses import published_reserves, reserves_for_student
from book_app.models import Book, Contributor, Genre, Rental
from engagement.models import Favorite, Shelf
from user_app.roles import home_url, is_library_staff


def home(request):
    """Bosh sahifa — fonddagi haqiqiy sonlar va kitoblar bilan (mehmonga ham ochiq)."""
    books = Book.objects.filter(is_active=True, category__is_active=True)
    stats = books.aggregate(
        total=Count('id'),
        digital=Count('id', filter=Q(electronic_version__gt='') | Q(remote_file_url__gt='')),
        audio=Count('id', filter=Q(audio_version__gt='')),
    )
    stats['authors'] = (Contributor.objects.filter(book__in=books)
                        .values('author').distinct().count())

    genres = list(Genre.objects.filter(is_active=True)
                  .annotate(n=Count('book', filter=Q(book__is_active=True)))
                  .filter(n__gt=0).order_by('-n', 'name'))
    stats['genres'] = len(genres)

    base = books.select_related('category').prefetch_related('authors')
    popular = list(base.order_by('-view_count', '-rating_count', '-id')[:12])

    return render(request, "home.html", {
        'stats': stats,
        'genres': genres[:8],
        'all_genres': genres[:24],
        'popular_books': popular,
        'recent_books': base.order_by('-created_at', '-id')[:12],
        # Muqovasi borlar oldinda — hero chiroyli ko'rinsin
        'hero_books': sorted(popular, key=lambda b: not b.cover_image)[:4],
        'course_count': published_reserves().count(),
    })


@login_required
def dashboard(request):
    # Administrator va kutubxona xodimi o'z ish joyiga ketadi
    if is_library_staff(request.user):
        return redirect(home_url(request.user))

    # Talaba ham, HEMIS xodimi ham o'quvchi — bir xil kabinetni ko'radi
    return _reader_cabinet(request)


def _reader_cabinet(request):
    """O'quvchi kabineti — talaba va xodim uchun bir xil."""
    from circulation.models import Fine, Reservation
    from reading.models import ReadingProgress

    base_qs = (Book.objects.select_related('category').prefetch_related('authors')
               .filter(is_active=True, category__is_active=True))

    popular_books = (base_qs.annotate(rental_count=Count('item__rental'))
                     .order_by('-rating_count', '-rental_count', '-view_count')[:12])

    one_month_ago = now() - timedelta(days=30)
    recent_books = base_qs.filter(created_at__gte=one_month_ago).order_by('-created_at')[:12]
    if not recent_books:
        recent_books = base_qs.order_by('-created_at')[:12]

    # Davom ettirish — o'qish jarayoni
    continue_reading = (ReadingProgress.objects
                        .filter(user=request.user, percent__lt=100)
                        .select_related('book__category')
                        .prefetch_related('book__authors')
                        .order_by('-updated_at')[:6])

    # Ijaralar + eslatmalar
    active_rentals = []
    overdue_count = unpaid_fines = available_res = 0
    from user_app.services import get_or_create_patron
    patron = get_or_create_patron(request.user)
    if patron is not None:
        active_rentals = list(Rental.objects
                              .filter(patron=patron, return_date__isnull=True)
                              .select_related('copy__book__category')
                              .prefetch_related('copy__book__authors'))
        overdue_count = sum(1 for r in active_rentals if r.is_overdue)
        unpaid_fines = Fine.objects.filter(patron=patron, is_paid=False).count()
        available_res = Reservation.objects.filter(
            patron=patron, status=Reservation.Status.AVAILABLE).count()

    today = localdate()
    for rental in active_rentals:
        rental.days_left = (rental.due_date - today).days if rental.due_date else None

    ctx = {
        'patron': patron,
        'my_courses': reserves_for_student(request.user)[:3],
        'favorites_count': Favorite.objects.filter(user=request.user).count(),
        'shelves_count': Shelf.objects.filter(owner=request.user).count(),
        'reading_count': (ReadingProgress.objects
                          .filter(user=request.user, percent__lt=100).count()),
        'continue_reading': continue_reading,
        'popular_books': popular_books,
        'recent_books': recent_books,
        'active_rentals': active_rentals,
        'active_rentals_count': len(active_rentals),
        'overdue_count': overdue_count,
        'unpaid_fines': unpaid_fines,
        'available_res': available_res,
        'genres': Genre.objects.filter(is_active=True)[:10],
    }
    return render(request, "opac/cabinet.html", ctx)
