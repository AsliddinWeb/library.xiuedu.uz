from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from book_app.models import Book, Rental
from user_app.utils import library_admin_role_required

from . import services
from .models import Fine, RentalRequest, Reservation


def _student(request):
    """Faqat user_type STUDENT bo'lsa profilni qaytaradi (rolga asoslangan)."""
    from user_app.models import User
    user = request.user
    if user.is_authenticated and user.user_type == User.UserType.STUDENT:
        return getattr(user, 'student_profile', None)
    return None


def _render_actions(request, book, message=None, ok=True):
    """Kitob amallari blokini (HTMX target) qayta render qiladi."""
    ctx = services.book_action_context(_student(request), book)
    ctx['action_message'] = message
    ctx['action_ok'] = ok
    return render(request, 'book_app/book/partials/_book_actions.html', ctx)


@require_POST
@login_required
def request_rental(request, pk):
    book = get_object_or_404(Book, pk=pk)
    student = _student(request)
    if student is None:
        return _render_actions(request, book, "Bu amal faqat talabalar uchun.", ok=False)
    _, msg = services.create_rental_request(student, book)
    return _render_actions(request, book, msg)


@require_POST
@login_required
def cancel_request(request, pk):
    book = get_object_or_404(Book, pk=pk)
    student = _student(request)
    if student is None:
        return _render_actions(request, book, "Bu amal faqat talabalar uchun.", ok=False)
    _, msg = services.cancel_rental_request(student, book)
    return _render_actions(request, book, msg)


@require_POST
@login_required
def reserve_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    student = _student(request)
    if student is None:
        return _render_actions(request, book, "Bu amal faqat talabalar uchun.", ok=False)
    _, msg = services.create_reservation(student, book)
    return _render_actions(request, book, msg)


@require_POST
@login_required
def cancel_reservation(request, pk):
    book = get_object_or_404(Book, pk=pk)
    student = _student(request)
    if student is None:
        return _render_actions(request, book, "Bu amal faqat talabalar uchun.", ok=False)
    _, msg = services.cancel_reservation(student, book)
    return _render_actions(request, book, msg)


@login_required
def my_rentals(request):
    student = _student(request)
    if student is None:
        return render(request, '403.html', status=403)

    active_rentals = (Rental.objects
                      .filter(student=student, return_date__isnull=True)
                      .select_related('copy__book'))
    rental_history = (Rental.objects
                      .filter(student=student, return_date__isnull=False)
                      .select_related('copy__book')[:20])
    pending_requests = (RentalRequest.objects
                        .filter(student=student, status=RentalRequest.Status.PENDING)
                        .select_related('book'))
    reservations = (Reservation.objects
                    .filter(student=student,
                            status__in=[Reservation.Status.WAITING, Reservation.Status.AVAILABLE])
                    .select_related('book'))
    fines = (Fine.objects
             .filter(student=student, is_paid=False)
             .select_related('rental__copy__book'))

    ctx = {
        'active_rentals': active_rentals,
        'rental_history': rental_history,
        'pending_requests': pending_requests,
        'reservations': reservations,
        'fines': fines,
    }
    return render(request, 'circulation/my_rentals.html', ctx)


# ===================================================== Kutubxonachi paneli

def _manage_context():
    return {
        'pending_requests': (RentalRequest.objects
                             .filter(status=RentalRequest.Status.PENDING)
                             .select_related('book', 'student__user')),
        'active_rentals': (Rental.objects
                           .filter(return_date__isnull=True)
                           .select_related('copy__book', 'student__user')),
        'unpaid_fines': (Fine.objects
                         .filter(is_paid=False)
                         .select_related('student__user', 'rental__copy__book')),
    }


def _render_panel(request, message=None, ok=True):
    ctx = _manage_context()
    ctx['panel_message'] = message
    ctx['panel_ok'] = ok
    return render(request, 'circulation/partials/_manage_panel.html', ctx)


@library_admin_role_required
def manage(request):
    return render(request, 'circulation/manage.html', _manage_context())


@require_POST
@library_admin_role_required
def approve_request_view(request, pk):
    req = get_object_or_404(RentalRequest, pk=pk)
    _, msg = services.approve_request(req, librarian=request.user)
    return _render_panel(request, msg)


@require_POST
@library_admin_role_required
def reject_request_view(request, pk):
    req = get_object_or_404(RentalRequest, pk=pk)
    _, msg = services.reject_request(req, librarian=request.user)
    return _render_panel(request, msg)


@require_POST
@library_admin_role_required
def return_rental_view(request, pk):
    rental = get_object_or_404(Rental, pk=pk)
    _, msg = services.return_rental(rental)
    return _render_panel(request, msg)


@require_POST
@library_admin_role_required
def mark_fine_paid_view(request, pk):
    fine = get_object_or_404(Fine, pk=pk)
    _, msg = services.mark_fine_paid(fine)
    return _render_panel(request, msg)
