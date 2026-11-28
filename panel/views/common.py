from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils.timezone import localdate, now

from audit.models import ActionLog
from book_app.models import Book, Genre, Rental
from circulation.models import Fine, RentalRequest, Reservation
from engagement.models import Review
from notifications.models import Notification
from user_app.models import Patron
from user_app.permissions import (
    PERMISSION_GROUPS,
    Perms,
    has_perm,
    require_perm,
    staff_required,
    user_permissions,
)


@staff_required
def dashboard(request):
    today = now().date()

    pending = RentalRequest.objects.filter(status=RentalRequest.Status.PENDING)
    open_loans = Rental.objects.filter(return_date__isnull=True)
    overdue_qs = (open_loans.filter(due_date__lt=today)
                  .select_related('copy__book', 'patron__user').order_by('due_date'))
    ready = Reservation.objects.filter(status=Reservation.Status.AVAILABLE)

    stats = {
        'pending_requests': pending.count(),
        'active_rentals': open_loans.count(),
        'overdue': overdue_qs.count(),
        'ready_holds': ready.count(),
        'issued_today': Rental.objects.filter(borrowed_date=today).count(),
        'returned_today': Rental.objects.filter(return_date=today).count(),
        'due_today': open_loans.filter(due_date=today).count(),
        'reservations': Reservation.objects.filter(status=Reservation.Status.WAITING).count(),
        'unpaid_fines': Fine.objects.filter(is_paid=False).count(),
        'pending_reviews': Review.objects.filter(is_approved=False).count(),
        'books': Book.objects.count(),
        'patrons': Patron.objects.count(),
    }

    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    counts = {d: 0 for d in days}
    for d in Rental.objects.filter(borrowed_date__gte=days[0]).values_list('borrowed_date', flat=True):
        if d in counts:
            counts[d] += 1
    cats = Genre.objects.annotate(c=Count('book')).filter(c__gt=0).order_by('-c')[:6]

    user = request.user
    ctx = {
        'active': 'dashboard',
        'page_title': 'Boshqaruv paneli',
        'stats': stats,
        # A'zo ismlari ko'rinadigan bloklar — faqat shu ishga ruxsati borga
        'recent_requests': (pending.select_related('book', 'patron__user')[:6]
                            if has_perm(user, Perms.CIRC_CHECKOUT) else None),
        'overdue': (overdue_qs[:6]
                    if has_perm(user, Perms.CIRC_CHECKIN, Perms.CIRC_CHECKOUT)
                    else None),
        'ready_holds': (ready.select_related('book', 'patron__user').order_by('hold_until')[:6]
                        if has_perm(user, Perms.CIRC_HOLDS, Perms.CIRC_CHECKOUT) else None),
        'my_actions': ActionLog.objects.filter(actor=user).order_by('-at')[:8],
        'rentals_chart': {'labels': [d.strftime('%d.%m') for d in days],
                          'data': [counts[d] for d in days]},
        'cats_chart': {'labels': [g.name for g in cats], 'data': [g.c for g in cats]},
    }
    return render(request, 'panel/dashboard.html', ctx)


@require_perm(Perms.CATALOG_VIEW)
def coming_soon(request, active='', title='Bo\'lim'):
    return render(request, 'panel/coming_soon.html', {'active': active, 'page_title': title})


#: Profildagi "mening ishim" ko'rsatkichlari: (nom, ikonka, harakatlar)
WORK_STATS = (
    ('Kitob berildi', 'upload', (ActionLog.Action.CHECKOUT,)),
    ('Qabul qilindi', 'download', (ActionLog.Action.CHECKIN,)),
    ('Kataloglash', 'book', (ActionLog.Action.BIBLIO_CREATE, ActionLog.Action.BIBLIO_EDIT)),
    ('Nusxa amallari', 'barcode', (ActionLog.Action.ITEM_CREATE, ActionLog.Action.ITEM_EDIT,
                                  ActionLog.Action.ITEM_WITHDRAW)),
    ("A'zolar bilan", 'users', (ActionLog.Action.PATRON_CREATE, ActionLog.Action.PATRON_EDIT,
                               ActionLog.Action.PATRON_BLOCK)),
    ("To'lovlar", 'cash', (ActionLog.Action.PAYMENT, ActionLog.Action.WAIVE,
                           ActionLog.Action.FINE_CHARGE)),
)


def _work_stats(user):
    """Xodimning bugungi va shu oydagi ishlari (audit jurnalidan)."""
    today = localdate()
    mine = ActionLog.objects.filter(actor=user, at__date__gte=today.replace(day=1))
    totals = mine.aggregate(**{
        key: Count('pk', filter=condition)
        for index, (_, _, actions) in enumerate(WORK_STATS)
        for key, condition in (
            (f'month_{index}', Q(action__in=actions)),
            (f'today_{index}', Q(action__in=actions, at__date=today)))
    })
    return [{'label': label, 'icon': icon, 'today': totals[f'today_{index}'],
             'month': totals[f'month_{index}']}
            for index, (label, icon, _) in enumerate(WORK_STATS)]


@staff_required
def profile(request):
    """Xodimning o'z hisobi: bajargan ishlari, rollari va ruxsatlari."""
    granted = user_permissions(request.user)
    groups = [(title, [label for flag, label in items if flag in granted])
              for title, items in PERMISSION_GROUPS]
    return render(request, 'panel/profile.html', {
        'active': 'profile',
        'page_title': "Mening hisobim",
        'work_stats': _work_stats(request.user),
        'history': Paginator(ActionLog.objects.filter(actor=request.user).order_by('-at'), 20)
                   .get_page(request.GET.get('page', 1)),
        'permission_groups': [(title, labels) for title, labels in groups if labels],
    })


@staff_required
def notifications(request):
    return render(request, 'panel/notifications.html', {
        'active': 'notifications',
        'page_title': "Bildirishnomalar",
        'items': Notification.objects.filter(user=request.user),
    })
