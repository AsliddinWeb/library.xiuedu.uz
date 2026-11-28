"""
Sirkulyatsiya ro'yxatlari: so'rovlar, ijaralar, navbatlar, jarimalar.

Kundalik berish/qabul qilish deskda bajariladi (`views/desk.py`); bu sahifalar
butun ro'yxatni ko'rish, saralab ishlash va eksport uchun. Har amal natijasi
bildirishnoma bo'lib chiqadi va ro'yxat o'zi yangilanadi.
"""
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.http import urlencode
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from book_app.models import Rental
from circulation import loans, services
from circulation.models import Fine, RentalRequest, Reservation
from user_app.permissions import Perms, has_perm, require_perm

from ..exports import csv_response, wants_csv
from ..htmx import render_partial_or_page, toast

__all__ = [
    'requests_view', 'request_approve', 'request_reject',
    'rentals_view', 'rental_return', 'rental_renew', 'rental_lost',
    'reservations_view', 'reservation_cancel',
    'fines_view', 'fine_mark_paid', 'fine_waive', 'fine_adjust',
]

PER_PAGE = 20


def _param(request, key, default=''):
    return request.POST.get(key, request.GET.get(key, default))


def _search(qs, query, *book_fields):
    """Har so'z a'zo (ism, bilet, login) yoki kitob maydonlaridan biriga mos kelsin."""
    fields = ('patron__card_number', 'patron__full_name', 'patron__user__username',
              'patron__user__first_name', 'patron__user__second_name', *book_fields)
    for word in query.split():
        condition = Q()
        for field in fields:
            condition |= Q(**{f'{field}__icontains': word})
        qs = qs.filter(condition)
    return qs


def _list_context(request, base, views, default, *, order, search_fields, active, title):
    """Tablar (soni bilan), qidiruv va sahifalash — to'rt ro'yxat uchun umumiy.

    `views` — [(kod, nom, Q yoki None)].
    """
    current = _param(request, 'view', default)
    conditions = {code: condition for code, _, condition in views}
    if current not in conditions:
        current = default
    query = _param(request, 'q').strip()
    searched = _search(base, query, *search_fields) if query else base

    counts = searched.aggregate(**{
        f'tab_{code}': Count('pk', filter=condition) if condition is not None else Count('pk')
        for code, _, condition in views
    })
    tabs = [(code, label, counts[f'tab_{code}']) for code, label, _ in views]

    filtered = searched if conditions[current] is None else searched.filter(conditions[current])
    filtered = filtered.order_by(*order)
    page = Paginator(filtered, PER_PAGE).get_page(_param(request, 'page', 1))

    extra = {'view': current, **({'q': query} if query else {})}
    return {
        'active': active,
        'page_title': title,
        'tabs': tabs,
        'view': current,
        'q': query,
        'page_obj': page,
        'query': '&' + urlencode(extra),
        'export_query': urlencode({**extra, 'export': 'csv'}),
        'filtered': filtered,
        'today': now().date(),
    }


def _render(request, name, context, *, message='', ok=True):
    response = render_partial_or_page(
        request, f'panel/circulation/{name}.html', f'panel/circulation/_{name}.html', context)
    if message:
        toast(response, message, 'success' if ok else 'danger')
    return response


# ============================================================ So'rovlar

def _requests_ctx(request):
    status = RentalRequest.Status
    return _list_context(
        request,
        RentalRequest.objects.select_related('book', 'patron__user', 'patron__category',
                                             'decided_by'),
        [('pending', 'Kutilmoqda', Q(status=status.PENDING)),
         ('approved', 'Tasdiqlangan', Q(status=status.APPROVED)),
         ('rejected', 'Rad etilgan', Q(status=status.REJECTED)),
         ('all', 'Barchasi', None)],
        'pending', order=('-created_at', '-pk'), search_fields=('book__title',),
        active='requests', title="Ijara so'rovlari")


def _requests_page(request, **kwargs):
    ctx = _requests_ctx(request)
    page = ctx['page_obj']
    free = dict(RentalRequest.objects.filter(pk__in=[r.pk for r in page])
                .annotate(free=Count('book__item',
                                     filter=Q(book__item__status='AVAILABLE')))
                .values_list('pk', 'free'))
    for req in page:
        req.free_copies = free.get(req.pk, 0)
    return _render(request, 'requests', ctx, **kwargs)


@require_perm(Perms.CIRC_CHECKOUT)
def requests_view(request):
    if wants_csv(request):
        rows = ((r.borrower_name, r.patron.card_number if r.patron else '', r.book.title,
                 r.created_at, r.get_status_display(), r.note)
                for r in _requests_ctx(request)['filtered'])
        return csv_response(request, 'sorovlar',
                            ["A'zo", 'Bilet', 'Kitob', 'Sana', 'Holat', 'Izoh'], rows)
    return _requests_page(request)


@require_POST
@require_perm(Perms.CIRC_CHECKOUT)
def request_approve(request, pk):
    rental, message = services.approve_request(
        get_object_or_404(RentalRequest, pk=pk), librarian=request.user)
    return _requests_page(request, message=message, ok=rental is not None)


@require_POST
@require_perm(Perms.CIRC_CHECKOUT)
def request_reject(request, pk):
    ok, message = services.reject_request(
        get_object_or_404(RentalRequest, pk=pk), librarian=request.user,
        note=request.POST.get('note', '').strip()[:255])
    return _requests_page(request, message=message, ok=ok)


# ============================================================ Ijaralar

def _rentals_ctx(request):
    today = now().date()
    return _list_context(
        request,
        Rental.objects.select_related('copy__book', 'patron__user', 'patron__category', 'fine'),
        [('active', 'Faol', Q(return_date__isnull=True)),
         ('overdue', "Muddati o'tgan", Q(return_date__isnull=True, due_date__lt=today)),
         ('returned', 'Qaytarilgan', Q(return_date__isnull=False)),
         ('all', 'Barchasi', None)],
        'active',
        order=(('-return_date', '-pk') if _param(request, 'view') == 'returned'
               else ('due_date', 'pk')),
        search_fields=('copy__book__title', 'copy__barcode', 'copy__inventory_number'),
        active='rentals', title='Ijaralar')


def _rentals_page(request, **kwargs):
    return _render(request, 'rentals', _rentals_ctx(request), **kwargs)


@require_perm(Perms.CIRC_CHECKOUT, Perms.CIRC_CHECKIN)
def rentals_view(request):
    if wants_csv(request):
        rows = ((r.borrower_name, r.patron.card_number if r.patron else '', r.copy.book.title,
                 r.copy.barcode or r.copy.inventory_number, r.borrowed_date, r.due_date,
                 r.return_date, r.renewals_count)
                for r in _rentals_ctx(request)['filtered'])
        return csv_response(request, 'ijaralar',
                            ["A'zo", 'Bilet', 'Kitob', 'Shtrix-kod', 'Berilgan', 'Muddat',
                             'Qaytarilgan', 'Uzaytirilgan'], rows)
    return _rentals_page(request)


def _checkin_message(result):
    parts = [result.message]
    if result.fine and not result.fine.is_paid:
        parts.append(f"Jarima: {result.fine.amount:.0f} so'm.")
    if result.next_hold:
        parts.append(f"Navbatda {result.next_hold.borrower_name} — kitobni chetga olib qo'ying.")
    return ' '.join(parts)


@require_POST
@require_perm(Perms.CIRC_CHECKIN)
def rental_return(request, pk):
    rental = get_object_or_404(
        Rental.objects.select_related('copy__book', 'patron__user', 'patron__category'), pk=pk)
    result = loans.checkin(rental, request.user)
    return _rentals_page(request, message=_checkin_message(result), ok=result.ok)


@require_POST
@require_perm(Perms.CIRC_RENEW)
def rental_renew(request, pk):
    result = loans.renew(get_object_or_404(Rental, pk=pk), request.user)
    message = result.message
    if not result.ok and result.can_override:
        message += " Zarur bo'lsa, deskda sabab yozib uzaytiring."
    return _rentals_page(request, message=message, ok=result.ok)


def _amount(raw):
    """Foydalanuvchi yozgan summa -> Decimal yoki None."""
    try:
        value = Decimal(str(raw).replace(' ', '').replace(',', '.') or '0')
    except InvalidOperation:
        return None
    return value if value.is_finite() and 0 <= value < Decimal('1000000000') else None


@require_POST
@require_perm(Perms.CIRC_CHECKIN)
def rental_lost(request, pk):
    """Kitob yo'qolgan: ijara yopiladi, nusxa «Yo'qolgan» bo'ladi, to'lov yoziladi."""
    rental = get_object_or_404(
        Rental.objects.select_related('copy__book', 'patron__user', 'patron__category'), pk=pk)
    amount = _amount(request.POST.get('amount', '0'))
    if amount is None:
        return _rentals_page(request, message="Summa noto'g'ri yozilgan.", ok=False)
    if amount and not has_perm(request.user, Perms.BILLING_CHARGE):
        return _rentals_page(request, message="To'lov yozishga ruxsatingiz yo'q — summani 0 qiling.",
                             ok=False)
    result = loans.declare_lost(rental, request.user, amount=amount,
                                note=request.POST.get('note', '').strip())
    return _rentals_page(request, message=result.message, ok=result.ok)


# ============================================================ Navbatlar

def _reservations_ctx(request):
    status = Reservation.Status
    ctx = _list_context(
        request,
        Reservation.objects.select_related('book', 'patron__user', 'patron__category'),
        [('open', 'Faol', Q(status__in=loans.OPEN_HOLDS)),
         ('ready', 'Tayyor', Q(status=status.AVAILABLE)),
         ('waiting', 'Navbatda', Q(status=status.WAITING)),
         ('closed', 'Yopilgan', ~Q(status__in=loans.OPEN_HOLDS))],
        'open', order=('book__title', 'created_at', 'pk'), search_fields=('book__title',),
        active='reservations', title='Navbatlar')
    for hold in ctx['page_obj']:
        hold.position = services.reservation_position(hold)
    return ctx


def _reservations_page(request, **kwargs):
    return _render(request, 'reservations', _reservations_ctx(request), **kwargs)


@require_perm(Perms.CIRC_HOLDS)
def reservations_view(request):
    if wants_csv(request):
        rows = ((r.book.title, r.borrower_name, r.patron.card_number if r.patron else '',
                 r.created_at, r.get_status_display(), r.hold_until)
                for r in _reservations_ctx(request)['filtered'])
        return csv_response(request, 'navbatlar',
                            ['Kitob', "A'zo", 'Bilet', 'Yozilgan', 'Holat', 'Saqlanadi'], rows)
    return _reservations_page(request)


@require_POST
@require_perm(Perms.CIRC_HOLDS)
def reservation_cancel(request, pk):
    result = loans.cancel_hold(
        get_object_or_404(Reservation.objects.select_related('book', 'patron'), pk=pk),
        request.user)
    message = result.message
    if result.next_hold:
        message += f" Navbat {result.next_hold.borrower_name}ga o'tdi."
    return _reservations_page(request, message=message, ok=result.ok)


# ============================================================ Jarimalar

def _fines_ctx(request):
    ctx = _list_context(
        request,
        Fine.objects.select_related('patron__user', 'patron__category', 'rental__copy__book'),
        [('unpaid', "To'lanmagan", Q(is_paid=False)),
         ('paid', "To'langan", Q(is_paid=True, is_waived=False)),
         ('waived', 'Kechirilgan', Q(is_waived=True)),
         ('all', 'Barchasi', None)],
        'unpaid', order=('-created_at', '-pk'), search_fields=('rental__copy__book__title',),
        active='fines', title='Jarimalar')

    month_start = now().date().replace(day=1)
    ctx['totals'] = Fine.objects.aggregate(
        unpaid=Sum('amount', filter=Q(is_paid=False), default=0),
        collected=Sum('amount', default=0,
                      filter=Q(is_paid=True, is_waived=False, paid_at__date__gte=month_start)),
        waived=Sum('amount', default=0,
                   filter=Q(is_waived=True, paid_at__date__gte=month_start)))
    return ctx


def _fines_page(request, **kwargs):
    return _render(request, 'fines', _fines_ctx(request), **kwargs)


@require_perm(Perms.BILLING_CHARGE, Perms.BILLING_COLLECT)
def fines_view(request):
    if wants_csv(request):
        rows = ((f.borrower_name, f.patron.card_number if f.patron else '',
                 f.rental.copy.book.title, f.days_overdue, f.amount,
                 'Kechirilgan' if f.is_waived else "To'langan" if f.is_paid else "To'lanmagan",
                 f.created_at, f.paid_at, f.note)
                for f in _fines_ctx(request)['filtered'])
        return csv_response(request, 'jarimalar',
                            ["A'zo", 'Bilet', 'Kitob', 'Kechikkan kun', "Summa (so'm)", 'Holat',
                             'Yozilgan', 'Yopilgan', 'Izoh'], rows)
    return _fines_page(request)


def _fine(pk):
    return get_object_or_404(Fine.objects.select_related('rental', 'patron__user'), pk=pk)


@require_POST
@require_perm(Perms.BILLING_COLLECT)
def fine_mark_paid(request, pk):
    ok, message = loans.collect_fine(_fine(pk), request.user)
    return _fines_page(request, message=message, ok=ok)


@require_POST
@require_perm(Perms.BILLING_WAIVE)
def fine_waive(request, pk):
    ok, message = loans.waive_fine(_fine(pk), request.user,
                                   request.POST.get('note', ''))
    return _fines_page(request, message=message, ok=ok)


@require_POST
@require_perm(Perms.BILLING_CHARGE)
def fine_adjust(request, pk):
    amount = _amount(request.POST.get('amount', ''))
    if amount is None:
        return _fines_page(request, message="Summa noto'g'ri yozilgan.", ok=False)
    ok, message = loans.adjust_fine(_fine(pk), request.user, amount,
                                    request.POST.get('note', ''))
    return _fines_page(request, message=message, ok=ok)
