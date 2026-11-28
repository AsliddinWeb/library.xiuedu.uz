from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.utils.timezone import localdate
from django.views.decorators.http import require_POST

from audit.models import ActionLog
from audit.services import log_action, log_change, snapshot
from book_app.models import Book, Genre, Item, Rental
from circulation.models import Fine, LibrarySettings
from engagement import services as eng_services
from engagement.models import Review
from reading.models import ReadingHistory
from user_app.models import Patron, PatronCategory
from user_app.permissions import Perms, require_perm

from ..exports import csv_response, wants_csv
from ..forms import PanelSettingsForm
from ..htmx import render_partial_or_page, toast

# ============================================================ Sharhlar

REVIEW_VIEWS = (('pending', 'Kutilmoqda', Q(is_approved=False)),
                ('approved', "E'lon qilingan", Q(is_approved=True)),
                ('all', 'Barchasi', None))


def _reviews_ctx(request):
    view = request.POST.get('view') or request.GET.get('view') or 'pending'
    conditions = {code: condition for code, _, condition in REVIEW_VIEWS}
    if view not in conditions:
        view = 'pending'
    query = (request.POST.get('q') or request.GET.get('q') or '').strip()
    base = Review.objects.select_related('user', 'book')
    if query:
        base = base.filter(Q(book__title__icontains=query) | Q(text__icontains=query)
                           | Q(user__first_name__icontains=query)
                           | Q(user__second_name__icontains=query))
    tabs = [(code, label, (base if condition is None else base.filter(condition)).count())
            for code, label, condition in REVIEW_VIEWS]
    reviews = base if conditions[view] is None else base.filter(conditions[view])
    number = request.POST.get('page') or request.GET.get('page') or 1
    page = Paginator(reviews.order_by('-id'), 20).get_page(number)
    return {'active': 'reviews', 'page_title': 'Sharhlar', 'page_obj': page, 'view': view,
            'q': query, 'tabs': tabs,
            'query': '&' + urlencode({'view': view, **({'q': query} if query else {})})}


def _reviews_response(request, message=''):
    response = render_partial_or_page(
        request, 'panel/system/reviews.html', 'panel/system/_reviews.html', _reviews_ctx(request))
    return toast(response, message) if message else response


@require_perm(Perms.MODERATE_REVIEWS)
def reviews_view(request):
    return _reviews_response(request)


@require_POST
@require_perm(Perms.MODERATE_REVIEWS)
def review_approve(request, pk):
    review = get_object_or_404(Review, pk=pk)
    eng_services.approve_review(review)
    log_action(ActionLog.Action.MODERATE, obj=review, note="Sharh tasdiqlandi")
    return _reviews_response(request, "Sharh e'lon qilindi.")


@require_POST
@require_perm(Perms.MODERATE_REVIEWS)
def review_reject(request, pk):
    review = get_object_or_404(Review.objects.select_related('book', 'user'), pk=pk)
    log_action(ActionLog.Action.MODERATE, obj=review,
               note=f"Sharh o'chirildi: {review.text[:200]}")
    eng_services.reject_review(review)
    return _reviews_response(request, "Sharh o'chirildi.")


# ============================================================ Analitika

PERIODS = ((7, "7 kun"), (30, "30 kun"), (90, "90 kun"), (365, "1 yil"))


def _daily(queryset, field, days):
    """Har kun uchun yozuvlar soni: {sana: son}."""
    rows = (queryset.filter(**{f'{field}__gte': days[0]})
            .values_list(field).annotate(total=Count('pk')).order_by())
    found = dict(rows)
    return [found.get(day, 0) for day in days]


@require_perm(Perms.REPORTS_VIEW)
def analytics(request):
    try:
        period = int(request.GET.get('period', 30))
    except ValueError:
        period = 30
    if period not in dict(PERIODS):
        period = 30

    today = localdate()
    start = today - timedelta(days=period - 1)
    days = [start + timedelta(days=offset) for offset in range(period)]
    issued = _daily(Rental.objects.all(), 'borrowed_date', days)
    returned = _daily(Rental.objects.all(), 'return_date', days)

    if wants_csv(request):
        return csv_response(request, f'hisobot-{period}-kun',
                            ['Sana', 'Berilgan', 'Qaytarilgan'], zip(days, issued, returned))

    summary = {
        'issued': sum(issued),
        'returned': sum(returned),
        'new_books': Book.objects.filter(created_at__date__gte=start).count(),
        'new_items': Item.objects.filter(acquired_on__gte=start).count(),
        'new_patrons': Patron.objects.filter(registered_on__gte=start).count(),
        'reads': ReadingHistory.objects.filter(opened_at__date__gte=start).count(),
        'collected': Fine.objects.filter(
            is_paid=True, is_waived=False, paid_at__date__gte=start,
        ).aggregate(total=Sum('amount', default=0))['total'],
    }
    totals = {
        'books': Book.objects.count(),
        'items': Item.objects.exclude(status=Item.Status.WITHDRAWN).count(),
        'patrons': Patron.objects.count(),
        'on_loan': Rental.objects.filter(return_date__isnull=True).count(),
    }

    cats = Genre.objects.annotate(c=Count('book')).filter(c__gt=0).order_by('-c')[:8]
    viewed = list(Book.objects.filter(view_count__gt=0).order_by('-view_count')[:8])
    rented = list(Book.objects
                  .annotate(rc=Count('item__rental',
                                     filter=Q(item__rental__borrowed_date__gte=start)))
                  .filter(rc__gt=0).order_by('-rc')[:8])
    active_patrons = list(Patron.objects
                          .annotate(rc=Count('loans', filter=Q(loans__borrowed_date__gte=start)))
                          .filter(rc__gt=0).order_by('-rc')
                          .select_related('user', 'category')[:8])

    def chart(labels, *series):
        return {'labels': labels, 'series': [{'name': name, 'data': data}
                                             for name, data in series]}

    return render(request, 'panel/system/analytics.html', {
        'active': 'analytics', 'page_title': 'Analitika',
        'period': period, 'periods': PERIODS, 'start': start, 'today': today,
        'summary': summary, 'totals': totals,
        'top_rated': (Book.objects.filter(rating_count__gt=0)
                      .order_by('-avg_rating', '-rating_count')[:8]),
        'active_patrons': active_patrons,
        'rentals_chart': chart([d.strftime('%d.%m') for d in days],
                               ('Berilgan', issued), ('Qaytarilgan', returned)),
        'cats_chart': chart([g.name for g in cats], ('Kitoblar', [g.c for g in cats])),
        'viewed_chart': chart([b.title[:28] for b in viewed],
                              ("Ko'rishlar", [b.view_count for b in viewed])),
        'rented_chart': chart([b.title[:28] for b in rented],
                              ('Ijaralar', [b.rc for b in rented])),
    })


# ============================================================ Sozlamalar

@require_perm(Perms.SETTINGS_MANAGE)
def settings_view(request):
    obj = LibrarySettings.load()
    before = snapshot(obj)
    form = PanelSettingsForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        log_change(ActionLog.Action.SETTINGS, obj, before)
        messages.success(request, "Sozlamalar saqlandi.")
        return redirect('panel:settings')
    return render(request, 'panel/system/settings.html', {
        'active': 'settings', 'page_title': 'Sozlamalar', 'form': form,
        'categories': PatronCategory.objects.filter(is_active=True),
    })
