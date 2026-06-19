from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from book_app.models import Rental
from circulation import services
from circulation.models import Fine, RentalRequest, Reservation
from user_app.utils import library_admin_role_required


def _param(request, key, default=''):
    return request.POST.get(key, request.GET.get(key, default))


# ============================================================ So'rovlar

def _requests_ctx(request):
    qs = RentalRequest.objects.select_related('book', 'student__user')
    status = _param(request, 'status', 'PENDING')
    if status in RentalRequest.Status.values:
        qs = qs.filter(status=status)
    q = _param(request, 'q').strip()
    if q:
        qs = qs.filter(Q(book__title__icontains=q) |
                       Q(student__user__username__icontains=q) |
                       Q(student__user__first_name__icontains=q))
    return {'active': 'requests', 'page_title': "Ijara so'rovlari", 'requests': qs[:100],
            'status': status, 'q': q, 'statuses': RentalRequest.Status.choices}


@library_admin_role_required
def requests_view(request):
    ctx = _requests_ctx(request)
    tpl = 'panel/circulation/_requests.html' if getattr(request, 'htmx', False) else 'panel/circulation/requests.html'
    return render(request, tpl, ctx)


@require_POST
@library_admin_role_required
def request_approve(request, pk):
    services.approve_request(get_object_or_404(RentalRequest, pk=pk), librarian=request.user)
    return render(request, 'panel/circulation/_requests.html', _requests_ctx(request))


@require_POST
@library_admin_role_required
def request_reject(request, pk):
    services.reject_request(get_object_or_404(RentalRequest, pk=pk), librarian=request.user)
    return render(request, 'panel/circulation/_requests.html', _requests_ctx(request))


# ============================================================ Ijaralar

def _rentals_ctx(request):
    qs = Rental.objects.select_related('copy__book', 'student__user')
    view = _param(request, 'view', 'active')
    if view == 'active':
        qs = qs.filter(return_date__isnull=True)
    elif view == 'overdue':
        from django.utils.timezone import now
        qs = qs.filter(return_date__isnull=True, due_date__lt=now().date())
    elif view == 'returned':
        qs = qs.filter(return_date__isnull=False)
    q = _param(request, 'q').strip()
    if q:
        qs = qs.filter(Q(copy__book__title__icontains=q) |
                       Q(student__user__username__icontains=q) |
                       Q(student__user__first_name__icontains=q))
    return {'active': 'rentals', 'page_title': 'Ijaralar', 'rentals': qs.order_by('-id')[:100],
            'view': view, 'q': q}


@library_admin_role_required
def rentals_view(request):
    ctx = _rentals_ctx(request)
    tpl = 'panel/circulation/_rentals.html' if getattr(request, 'htmx', False) else 'panel/circulation/rentals.html'
    return render(request, tpl, ctx)


@require_POST
@library_admin_role_required
def rental_return(request, pk):
    services.return_rental(get_object_or_404(Rental, pk=pk))
    return render(request, 'panel/circulation/_rentals.html', _rentals_ctx(request))


# ============================================================ Navbatlar

def _reservations_ctx(request):
    qs = Reservation.objects.select_related('book', 'student__user').filter(
        status__in=[Reservation.Status.WAITING, Reservation.Status.AVAILABLE])
    q = _param(request, 'q').strip()
    if q:
        qs = qs.filter(Q(book__title__icontains=q) | Q(student__user__first_name__icontains=q))
    return {'active': 'reservations', 'page_title': 'Navbatlar',
            'reservations': qs.order_by('book', 'created_at')[:100], 'q': q}


@library_admin_role_required
def reservations_view(request):
    ctx = _reservations_ctx(request)
    tpl = 'panel/circulation/_reservations.html' if getattr(request, 'htmx', False) else 'panel/circulation/reservations.html'
    return render(request, tpl, ctx)


@require_POST
@library_admin_role_required
def reservation_cancel(request, pk):
    res = get_object_or_404(Reservation, pk=pk)
    res.status = Reservation.Status.CANCELLED
    res.save(update_fields=['status'])
    return render(request, 'panel/circulation/_reservations.html', _reservations_ctx(request))


# ============================================================ Jarimalar

def _fines_ctx(request):
    qs = Fine.objects.select_related('student__user', 'rental__copy__book')
    view = _param(request, 'view', 'unpaid')
    if view == 'unpaid':
        qs = qs.filter(is_paid=False)
    elif view == 'paid':
        qs = qs.filter(is_paid=True)
    q = _param(request, 'q').strip()
    if q:
        qs = qs.filter(Q(student__user__first_name__icontains=q) |
                       Q(student__user__username__icontains=q))
    total = sum(f.amount for f in qs if not f.is_paid)
    return {'active': 'fines', 'page_title': 'Jarimalar', 'fines': qs.order_by('-created_at')[:100],
            'view': view, 'q': q, 'total_unpaid': total}


@library_admin_role_required
def fines_view(request):
    ctx = _fines_ctx(request)
    tpl = 'panel/circulation/_fines.html' if getattr(request, 'htmx', False) else 'panel/circulation/fines.html'
    return render(request, tpl, ctx)


@require_POST
@library_admin_role_required
def fine_mark_paid(request, pk):
    services.mark_fine_paid(get_object_or_404(Fine, pk=pk))
    return render(request, 'panel/circulation/_fines.html', _fines_ctx(request))
