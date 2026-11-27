from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from book_app.models import Book, Rental
from user_app.permissions import Perms, require_perm
from user_app.services import get_or_create_patron

from . import services
from .models import Fine, RentalRequest, Reservation


def _patron(request):
    """Joriy foydalanuvchining kutubxona a'zoligi.

    P1-B dan boshlab TALABA HAM, XODIM/O'QITUVCHI HAM kitob so'ray oladi —
    shuning uchun bu yerda `user_type` tekshirilmaydi. A'zolik hali ochilmagan
    bo'lsa (eski foydalanuvchi), shu yerda ochiladi.
    """
    user = request.user
    if not user.is_authenticated:
        return None
    try:
        return get_or_create_patron(user)
    except Exception:  # a'zolik ochilmasa — amal bloklanadi, sahifa ishlayveradi
        import logging
        logging.getLogger('patrons').exception("A'zolikni olishda xatolik: %s", user.username)
        return None


def _render_actions(request, book, message=None, ok=True):
    """Kitob amallari blokini (HTMX target) qayta render qiladi."""
    ctx = services.book_action_context(_patron(request), book)
    ctx['action_message'] = message
    ctx['action_ok'] = ok
    return render(request, 'book_app/book/partials/_book_actions.html', ctx)


@require_POST
@login_required
def request_rental(request, pk):
    book = get_object_or_404(Book, pk=pk)
    patron = _patron(request)
    if patron is None:
        return _render_actions(request, book, "Kutubxona a'zoligi topilmadi.", ok=False)
    _, msg = services.create_rental_request(patron, book)
    return _render_actions(request, book, msg)


@require_POST
@login_required
def cancel_request(request, pk):
    book = get_object_or_404(Book, pk=pk)
    patron = _patron(request)
    if patron is None:
        return _render_actions(request, book, "Kutubxona a'zoligi topilmadi.", ok=False)
    _, msg = services.cancel_rental_request(patron, book)
    return _render_actions(request, book, msg)


@require_POST
@login_required
def reserve_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    patron = _patron(request)
    if patron is None:
        return _render_actions(request, book, "Kutubxona a'zoligi topilmadi.", ok=False)
    _, msg = services.create_reservation(patron, book)
    return _render_actions(request, book, msg)


@require_POST
@login_required
def cancel_reservation(request, pk):
    book = get_object_or_404(Book, pk=pk)
    patron = _patron(request)
    if patron is None:
        return _render_actions(request, book, "Kutubxona a'zoligi topilmadi.", ok=False)
    _, msg = services.cancel_reservation(patron, book)
    return _render_actions(request, book, msg)


@login_required
def my_rentals(request):
    """"Mening ijaralarim" — endi talabaga ham, xodimga ham ochiq."""
    patron = _patron(request)
    if patron is None:
        return render(request, '403.html', status=403)

    active_rentals = (Rental.objects
                      .filter(patron=patron, return_date__isnull=True)
                      .select_related('copy__book'))
    rental_history = (Rental.objects
                      .filter(patron=patron, return_date__isnull=False)
                      .select_related('copy__book')[:20])
    pending_requests = (RentalRequest.objects
                        .filter(patron=patron, status=RentalRequest.Status.PENDING)
                        .select_related('book'))
    reservations = (Reservation.objects
                    .filter(patron=patron,
                            status__in=[Reservation.Status.WAITING, Reservation.Status.AVAILABLE])
                    .select_related('book'))
    fines = (Fine.objects
             .filter(patron=patron, is_paid=False)
             .select_related('rental__copy__book'))

    ctx = {
        'patron': patron,
        'active_rentals': active_rentals,
        'rental_history': rental_history,
        'pending_requests': pending_requests,
        'reservations': reservations,
        'fines': fines,
        'tabs': [
            ('active', 'Joriy', len(active_rentals)),
            ('requests', "So'rovlar", len(pending_requests)),
            ('reservations', 'Navbatlar', len(reservations)),
            ('fines', 'Jarimalar', len(fines)),
            ('history', 'Tarix', 0),
        ],
    }
    return render(request, 'circulation/my_rentals.html', ctx)


# ===================================================== Kutubxonachi paneli

def _manage_context():
    return {
        'pending_requests': (RentalRequest.objects
                             .filter(status=RentalRequest.Status.PENDING)
                             .select_related('book', 'patron__user')),
        'active_rentals': (Rental.objects
                           .filter(return_date__isnull=True)
                           .select_related('copy__book', 'patron__user')),
        'unpaid_fines': (Fine.objects
                         .filter(is_paid=False)
                         .select_related('patron__user', 'rental__copy__book')),
    }


def _render_panel(request, message=None, ok=True):
    ctx = _manage_context()
    ctx['panel_message'] = message
    ctx['panel_ok'] = ok
    return render(request, 'circulation/partials/_manage_panel.html', ctx)


@require_perm(Perms.CIRC_CHECKOUT)
def manage(request):
    # Eski sahifa — endi kutubxonachi paneli (/panel/) bilan almashtirildi
    return redirect('panel:requests')


@require_POST
@require_perm(Perms.CIRC_CHECKOUT)
def approve_request_view(request, pk):
    req = get_object_or_404(RentalRequest, pk=pk)
    _, msg = services.approve_request(req, librarian=request.user)
    return _render_panel(request, msg)


@require_POST
@require_perm(Perms.CIRC_CHECKOUT)
def reject_request_view(request, pk):
    req = get_object_or_404(RentalRequest, pk=pk)
    _, msg = services.reject_request(req, librarian=request.user)
    return _render_panel(request, msg)


@require_POST
@require_perm(Perms.CIRC_CHECKIN)
def return_rental_view(request, pk):
    rental = get_object_or_404(Rental, pk=pk)
    _, msg = services.return_rental(rental)
    return _render_panel(request, msg)


@require_POST
@require_perm(Perms.BILLING_COLLECT)
def mark_fine_paid_view(request, pk):
    fine = get_object_or_404(Fine, pk=pk)
    _, msg = services.mark_fine_paid(fine)
    return _render_panel(request, msg)
