"""
Abonement deski — kutubxonachining asosiy ish oynasi (`/panel/desk/`).

Ikki rejim:
  · **Berish** — a'zo tanlanadi (bilet skanerlanadi yoki ism yoziladi), so'ng
    kitoblar ketma-ket skanerlanadi. Yonida a'zoning qo'lidagi kitoblar, navbati,
    so'rovlari va jarimalari — hammasi shu yerdan boshqariladi.
  · **Qabul qilish** — faqat shtrix-kod skanerlanadi; kechikish, jarima va
    navbatdagi a'zo darrov ko'rsatiladi.

Barcha amallar HTMX bilan `#desk` blokini yangilaydi: sahifa qayta yuklanmaydi va
skaner uchun maydon doim fokusda qoladi. Qoidalar `circulation.loans` ichida.
"""
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from book_app.models import Book, Item, Rental
from circulation import loans, lookup, services
from circulation.models import Fine, RentalRequest, Reservation
from user_app.models import Patron
from user_app.permissions import Perms, has_perm, require_perm

from ..htmx import render_partial_or_page, toast

__all__ = ['desk', 'desk_patrons', 'desk_checkout', 'desk_checkin', 'desk_renew',
           'desk_hold', 'desk_hold_cancel', 'desk_request_approve', 'desk_fine_pay']

CHECKOUT, CHECKIN = 'checkout', 'checkin'


def _mode(request):
    """So'ralgan rejim; ruxsati bo'lmasa — ruxsati bori."""
    asked = request.POST.get('mode') or request.GET.get('mode')
    can_out = has_perm(request.user, Perms.CIRC_CHECKOUT)
    can_in = has_perm(request.user, Perms.CIRC_CHECKIN)
    if asked == CHECKIN and can_in:
        return CHECKIN
    return CHECKOUT if can_out else CHECKIN


def _patron(request, pk):
    """A'zo ma'lumotlari faqat berish ruxsati borga ochiladi."""
    if not pk or not str(pk).isdigit() or not has_perm(request.user, Perms.CIRC_CHECKOUT):
        return None
    return (Patron.objects.select_related('user', 'category', 'user__student_profile',
                                          'user__employe_profile')
            .filter(pk=pk).first())


def _patron_panel(patron):
    """Tanlangan a'zoning joriy holati."""
    services.recalc_patron_counters(patron)
    today = now().date()
    rentals = list(Rental.objects.filter(patron=patron, return_date__isnull=True)
                   .select_related('copy__book').order_by('due_date', 'pk'))
    loan_days = services.loan_days_for(patron)
    return {
        'open_loans': rentals,
        'holds': Reservation.objects.filter(patron=patron, status__in=loans.OPEN_HOLDS)
                 .select_related('book').order_by('-status', 'created_at'),
        'pending': RentalRequest.objects.filter(patron=patron,
                                                status=RentalRequest.Status.PENDING)
                   .select_related('book'),
        'unpaid': Fine.objects.filter(patron=patron, is_paid=False)
                  .select_related('rental__copy__book'),
        'blocks': loans.patron_blocks(patron),
        'loan_days': loan_days,
        'loan_limit': services.loan_limit_for(patron),
        'default_due': today + timedelta(days=loan_days),
    }


def _render(request, mode, patron=None, **extra):
    today = now().date()
    ctx = {
        'active': 'desk',
        'page_title': 'Berish va qaytarish',
        'mode': mode,
        'patron': patron,
        'today': today,
        **extra,
    }
    if mode == CHECKOUT and patron:
        ctx.update(_patron_panel(patron))
    if mode == CHECKIN:
        ctx['returned_today'] = (Rental.objects.filter(return_date=today)
                                 .select_related('copy__book', 'patron__user')
                                 .order_by('-updated_at')[:10])
        ctx['returned_today_count'] = Rental.objects.filter(return_date=today).count()
    return render_partial_or_page(request, 'panel/desk/desk.html', 'panel/desk/_desk.html', ctx)


def _respond(request, mode, patron=None, *, message='', level='success', **extra):
    response = _render(request, mode, patron, **extra)
    if message:
        toast(response, message, level)
    return response


def _result(request, mode, patron, result, **extra):
    """`loans.Result` ni javobga aylantiradi."""
    return _respond(request, mode, patron, message=result.message,
                    level='success' if result.ok else 'danger', result=result, **extra)


def _override_flag(request):
    if request.POST.get('override') != '1':
        return False
    if not has_perm(request.user, Perms.CIRC_OVERRIDE):
        raise PermissionDenied("Cheklovni chetlab o'tishga ruxsatingiz yo'q.")
    return True


# --------------------------------------------------------------------------
#  Sahifa va qidiruv
# --------------------------------------------------------------------------

@require_perm(Perms.CIRC_CHECKOUT, Perms.CIRC_CHECKIN)
def desk(request):
    mode = _mode(request)
    patron = _patron(request, request.GET.get('patron'))
    query = request.GET.get('q', '').strip()
    matches = None

    if mode == CHECKOUT and query and not patron:
        exact = lookup.exact_patrons(query)
        if len(exact) == 1:
            patron = exact[0]
        else:
            matches = exact or lookup.search_patrons(query)

    response = _render(request, mode, patron, q='' if patron else query, matches=matches)
    if patron and query and getattr(request, 'htmx', False):
        response['HX-Push-Url'] = f'/panel/desk/?patron={patron.pk}'
    return response


@require_perm(Perms.CIRC_CHECKOUT)
def desk_patrons(request):
    """Yozish davomida a'zo takliflari."""
    query = request.GET.get('q', '').strip()
    matches = lookup.exact_patrons(query) or lookup.search_patrons(query)
    return render_partial_or_page(
        request, 'panel/desk/desk.html', 'panel/desk/_patron_results.html',
        {'matches': matches if len(query) >= 2 else None, 'q': query, 'mode': CHECKOUT,
         'active': 'desk', 'page_title': 'Berish va qaytarish'})


# --------------------------------------------------------------------------
#  Berish
# --------------------------------------------------------------------------

def _without_copies(books):
    """Topilgan kitoblar orasida fondda birorta ham nusxasi yo'qlari."""
    stocked = set(Item.objects.filter(book__in=[book.pk for book in books])
                  .values_list('book_id', flat=True))
    return [book for book in books if book.pk not in stocked]


def _book_to_queue(patron, item, result):
    """Nusxa band bo'lsa — navbatga yozish taklif qilinadigan kitob."""
    busy = {'on_loan', 'unavailable', 'held'}
    if not busy & {block.code for block in result.blocks}:
        return None
    if Rental.objects.filter(patron=patron, copy__book_id=item.book_id,
                             return_date__isnull=True).exists():
        return None
    return item.book_id


@require_POST
@require_perm(Perms.CIRC_CHECKOUT)
def desk_checkout(request):
    patron = _patron(request, request.POST.get('patron'))
    if patron is None:
        return _respond(request, CHECKOUT, message="Avval a'zoni tanlang.", level='warning')

    override = _override_flag(request)
    code = request.POST.get('code', '').strip()
    item_pk = request.POST.get('item', '')
    due_raw = request.POST.get('due_date', '').strip()
    try:
        due = date.fromisoformat(due_raw) if due_raw else None
    except ValueError:
        return _respond(request, CHECKOUT, patron, message="Sana noto'g'ri yozilgan.",
                        level='danger', code=code)

    if item_pk.isdigit():
        item = get_object_or_404(Item.objects.select_related('book'), pk=item_pk)
    elif not code:
        return _respond(request, CHECKOUT, patron, message="Shtrix-kodni kiriting.",
                        level='warning', due=due_raw)
    else:
        exact = lookup.exact_items(code)
        if len(exact) != 1:
            if not exact:
                other = lookup.exact_patrons(code)
                if len(other) == 1:
                    # Skanerga keyingi a'zoning bileti tushdi
                    return _respond(request, CHECKOUT, other[0],
                                    message=f"A'zo tanlandi: {other[0].display_name}",
                                    due=due_raw)
            books = [] if exact else lookup.matching_books(code)
            candidates = exact or lookup.items_of(books)
            if not candidates and not books:
                return _respond(request, CHECKOUT, patron,
                                message=f"«{code}» bo'yicha nusxa topilmadi.", level='danger',
                                due=due_raw)
            return _respond(request, CHECKOUT, patron, candidates=candidates,
                            books_without_items=_without_copies(books),
                            code=code, due=due_raw)
        item = exact[0]

    result = loans.checkout(patron, item, request.user, due_date=due, override=override,
                            reason=request.POST.get('reason', ''))
    extra = {'due': due_raw}
    if not result.ok:
        extra.update(
            retry={'url': 'panel:desk_checkout', 'item': item.pk, 'due_date': due_raw},
            blocked_item=item, hold_book=_book_to_queue(patron, item, result))
    return _result(request, CHECKOUT, patron, result, **extra)


# --------------------------------------------------------------------------
#  Qabul qilish
# --------------------------------------------------------------------------

@require_POST
@require_perm(Perms.CIRC_CHECKIN)
def desk_checkin(request):
    mode = _mode(request)
    patron = _patron(request, request.POST.get('patron'))
    damaged = bool(request.POST.get('damaged'))
    rental_pk = request.POST.get('rental', '')
    code = request.POST.get('code', '').strip()

    def open_rentals(items):
        return list(Rental.objects.filter(copy__in=[i.pk for i in items],
                                          return_date__isnull=True)
                    .select_related('copy__book', 'patron__user', 'patron__category'))

    if rental_pk.isdigit():
        rental = get_object_or_404(
            Rental.objects.select_related('copy__book', 'patron__user', 'patron__category'),
            pk=rental_pk)
    elif not code:
        return _respond(request, mode, patron, message="Shtrix-kodni kiriting.", level='warning')
    else:
        exact = lookup.exact_items(code)
        found = open_rentals(exact or lookup.items_of(lookup.matching_books(code)))
        if exact and len(found) == 1:
            rental = found[0]
        elif found:
            return _respond(request, mode, patron, return_candidates=found, code=code,
                            damaged=damaged)
        elif len(exact) == 1:
            return _respond(
                request, mode, patron, idle_item=exact[0], level='warning',
                message=f"Bu nusxa ijarada emas — holati: {exact[0].get_status_display()}.")
        else:
            return _respond(request, mode, patron, level='danger',
                            message=f"«{code}» bo'yicha ochiq ijara topilmadi.")

    result = loans.checkin(rental, request.user, damaged=damaged)
    return _result(request, mode, patron, result, returned=result if result.ok else None)


# --------------------------------------------------------------------------
#  Uzaytirish, navbat, so'rov, jarima
# --------------------------------------------------------------------------

@require_POST
@require_perm(Perms.CIRC_RENEW)
def desk_renew(request):
    rental = get_object_or_404(Rental.objects.select_related('copy__book'),
                               pk=request.POST.get('rental') or 0)
    patron = _patron(request, rental.patron_id)
    result = loans.renew(rental, request.user, override=_override_flag(request),
                         reason=request.POST.get('reason', ''))
    extra = {}
    if not result.ok:
        extra['retry'] = {'url': 'panel:desk_renew', 'rental': rental.pk}
    return _result(request, CHECKOUT, patron, result, **extra)


@require_POST
@require_perm(Perms.CIRC_HOLDS)
def desk_hold(request):
    patron = get_object_or_404(Patron, pk=request.POST.get('patron') or 0)
    book = get_object_or_404(Book, pk=request.POST.get('book') or 0)
    result = loans.place_hold(patron, book, request.user)
    return _result(request, CHECKOUT, _patron(request, patron.pk), result)


@require_POST
@require_perm(Perms.CIRC_HOLDS)
def desk_hold_cancel(request):
    reservation = get_object_or_404(Reservation.objects.select_related('book', 'patron'),
                                    pk=request.POST.get('reservation') or 0)
    result = loans.cancel_hold(reservation, request.user)
    return _result(request, CHECKOUT, _patron(request, reservation.patron_id), result)


@require_POST
@require_perm(Perms.CIRC_CHECKOUT)
def desk_request_approve(request):
    req = get_object_or_404(RentalRequest.objects.select_related('book', 'patron'),
                            pk=request.POST.get('request') or 0)
    rental, message = services.approve_request(req, librarian=request.user)
    return _respond(request, CHECKOUT, _patron(request, req.patron_id), message=message,
                    level='success' if rental else 'danger')


@require_POST
@require_perm(Perms.BILLING_COLLECT)
def desk_fine_pay(request):
    fine = get_object_or_404(Fine, pk=request.POST.get('fine') or 0)
    ok, message = loans.collect_fine(fine, request.user)
    return _respond(request, _mode(request), _patron(request, fine.patron_id), message=message,
                    level='success' if ok else 'danger')
