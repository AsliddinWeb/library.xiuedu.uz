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
    base_qs = Book.objects.select_related('category').prefetch_related('authors')

    popular_books = (
        base_qs.filter(is_active=True, category__is_active=True)
        .annotate(rental_count=Count('copy__rental'))
        .order_by('-rental_count', '-id')[:6]
    )

    one_month_ago = now() - timedelta(days=30)
    recent_books = (
        base_qs.filter(is_active=True, category__is_active=True, created_at__gte=one_month_ago)
        .order_by('-created_at')[:6]
    )
    # Agar oxirgi oyda yangi kitob bo'lmasa — eng so'nggilarini ko'rsatamiz
    if not recent_books:
        recent_books = base_qs.filter(is_active=True, category__is_active=True).order_by('-created_at')[:6]

    # Talabaning joriy (qaytarilmagan) ijaralari
    active_rentals = []
    student_profile = getattr(request.user, 'student_profile', None)
    if student_profile is not None:
        active_rentals = (
            Rental.objects
            .filter(student=student_profile, return_date__isnull=True)
            .select_related('copy__book')
        )

    ctx = {
        'popular_books': popular_books,
        'recent_books': recent_books,
        'active_rentals': active_rentals,
        'active_rentals_count': len(active_rentals),
        'genres': Genre.objects.filter(is_active=True)[:8],
    }
    return render(request, "dashboard/student.html", ctx)
