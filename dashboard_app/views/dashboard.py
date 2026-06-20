from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils.timezone import now

from book_app.models import Book, Genre, Rental
from user_app.roles import Roles, effective_role


def home(request):
    return render(request, "home.html")


@login_required
def dashboard(request):
    role = effective_role(request.user)

    if role == Roles.ADMIN:
        return redirect('/admin/')
    if role == Roles.STUDENT:
        return _student_dashboard(request)
    if role == Roles.LIBRARIAN:
        return redirect('/panel/')
    if role == Roles.EMPLOYEE:
        return render(request, 'dashboard/employee.html')

    # Roli aniqlanmagan xodim — standart sifatida xodim paneli
    return render(request, 'dashboard/employee.html')


def _student_dashboard(request):
    from circulation.models import Fine, Reservation
    from reading.models import ReadingProgress

    base_qs = (Book.objects.select_related('category').prefetch_related('authors')
               .filter(is_active=True, category__is_active=True))

    popular_books = (base_qs.annotate(rental_count=Count('copy__rental'))
                     .order_by('-rating_count', '-rental_count', '-view_count')[:12])

    one_month_ago = now() - timedelta(days=30)
    recent_books = base_qs.filter(created_at__gte=one_month_ago).order_by('-created_at')[:12]
    if not recent_books:
        recent_books = base_qs.order_by('-created_at')[:12]

    # Davom ettirish — o'qish jarayoni
    continue_reading = (ReadingProgress.objects
                        .filter(user=request.user, percent__lt=100)
                        .select_related('book').order_by('-updated_at')[:6])

    # Ijaralar + eslatmalar
    active_rentals = []
    overdue_count = unpaid_fines = available_res = 0
    student_profile = getattr(request.user, 'student_profile', None)
    if student_profile is not None:
        active_rentals = list(Rental.objects
                              .filter(student=student_profile, return_date__isnull=True)
                              .select_related('copy__book'))
        overdue_count = sum(1 for r in active_rentals if r.is_overdue)
        unpaid_fines = Fine.objects.filter(student=student_profile, is_paid=False).count()
        available_res = Reservation.objects.filter(
            student=student_profile, status=Reservation.Status.AVAILABLE).count()

    ctx = {
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
    return render(request, "dashboard/student.html", ctx)
