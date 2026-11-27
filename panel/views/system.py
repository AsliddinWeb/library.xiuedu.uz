import json
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from book_app.models import Book, Genre, Rental
from circulation.models import LibrarySettings
from engagement import services as eng_services
from engagement.models import Review
from reading.models import ReadingHistory
from user_app.models import Patron
from user_app.permissions import Perms, require_perm

from ..forms import PanelSettingsForm

# ============================================================ Sharhlar

def _reviews_ctx(request):
    view = request.POST.get('view', request.GET.get('view', 'pending'))
    qs = Review.objects.select_related('user', 'book')
    if view == 'pending':
        qs = qs.filter(is_approved=False)
    elif view == 'approved':
        qs = qs.filter(is_approved=True)
    page_no = request.POST.get('page', request.GET.get('page', 1))
    page = Paginator(qs.order_by('-id'), 20).get_page(page_no)
    return {'active': 'reviews', 'page_title': 'Sharhlar', 'reviews': page, 'page_obj': page, 'view': view}


@require_perm(Perms.MODERATE_REVIEWS)
def reviews_view(request):
    ctx = _reviews_ctx(request)
    tpl = 'panel/system/_reviews.html' if getattr(request, 'htmx', False) else 'panel/system/reviews.html'
    return render(request, tpl, ctx)


@require_POST
@require_perm(Perms.MODERATE_REVIEWS)
def review_approve(request, pk):
    eng_services.approve_review(get_object_or_404(Review, pk=pk))
    return render(request, 'panel/system/_reviews.html', _reviews_ctx(request))


@require_POST
@require_perm(Perms.MODERATE_REVIEWS)
def review_reject(request, pk):
    eng_services.reject_review(get_object_or_404(Review, pk=pk))
    return render(request, 'panel/system/_reviews.html', _reviews_ctx(request))


# ============================================================ Analitika

@require_perm(Perms.REPORTS_VIEW)
def analytics(request):
    today = now().date()
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    counts = {d: 0 for d in days}
    for d in Rental.objects.filter(borrowed_date__gte=days[0]).values_list('borrowed_date', flat=True):
        if d in counts:
            counts[d] += 1
    rentals_chart = {'labels': [d.strftime('%d.%m') for d in days], 'data': [counts[d] for d in days]}

    cats = Genre.objects.annotate(c=Count('book')).filter(c__gt=0).order_by('-c')[:8]
    cats_chart = {'labels': [g.name for g in cats], 'data': [g.c for g in cats]}

    viewed = list(Book.objects.filter(view_count__gt=0).order_by('-view_count')[:8])
    viewed_chart = {'labels': [b.title[:24] for b in viewed], 'data': [b.view_count for b in viewed]}

    rented = list(Book.objects.annotate(rc=Count('copy__rental')).filter(rc__gt=0).order_by('-rc')[:8])
    rented_chart = {'labels': [b.title[:24] for b in rented], 'data': [b.rc for b in rented]}

    active_patrons = list(Patron.objects.annotate(rc=Count('loans')).filter(rc__gt=0)
                          .order_by('-rc')[:8].select_related('user', 'category'))

    stats = {
        'books': Book.objects.count(),
        'patrons': Patron.objects.count(),
        'rentals': Rental.objects.count(),
        'reads': ReadingHistory.objects.count(),
    }
    return render(request, 'panel/system/analytics.html', {
        'active': 'analytics', 'page_title': 'Analitika', 'stats': stats,
        'top_rated': Book.objects.filter(rating_count__gt=0).order_by('-avg_rating', '-rating_count')[:8],
        'active_patrons': active_patrons,
        'rentals_chart': json.dumps(rentals_chart), 'cats_chart': json.dumps(cats_chart),
        'viewed_chart': json.dumps(viewed_chart), 'rented_chart': json.dumps(rented_chart),
    })


# ============================================================ Sozlamalar

@require_perm(Perms.SETTINGS_MANAGE)
def settings_view(request):
    obj = LibrarySettings.load()
    form = PanelSettingsForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Sozlamalar saqlandi.")
        return redirect('panel:settings')
    return render(request, 'panel/system/settings.html',
                  {'active': 'settings', 'page_title': 'Sozlamalar', 'form': form})
