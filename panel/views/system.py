import json
from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from book_app.models import Book, Genre, Rental
from circulation.models import Fine, LibrarySettings
from engagement import services as eng_services
from engagement.models import Review
from reading.models import ReadingHistory
from user_app.models import StudentProfile
from user_app.utils import library_admin_role_required

from ..forms import PanelSettingsForm

# ============================================================ Sharhlar

def _reviews_ctx(request):
    view = request.POST.get('view', request.GET.get('view', 'pending'))
    qs = Review.objects.select_related('user', 'book')
    if view == 'pending':
        qs = qs.filter(is_approved=False)
    elif view == 'approved':
        qs = qs.filter(is_approved=True)
    return {'active': 'reviews', 'page_title': 'Sharhlar', 'reviews': qs[:100], 'view': view}


@library_admin_role_required
def reviews_view(request):
    ctx = _reviews_ctx(request)
    tpl = 'panel/system/_reviews.html' if getattr(request, 'htmx', False) else 'panel/system/reviews.html'
    return render(request, tpl, ctx)


@require_POST
@library_admin_role_required
def review_approve(request, pk):
    eng_services.approve_review(get_object_or_404(Review, pk=pk))
    return render(request, 'panel/system/_reviews.html', _reviews_ctx(request))


@require_POST
@library_admin_role_required
def review_reject(request, pk):
    eng_services.reject_review(get_object_or_404(Review, pk=pk))
    return render(request, 'panel/system/_reviews.html', _reviews_ctx(request))


# ============================================================ Talabalar

@library_admin_role_required
def members(request):
    qs = StudentProfile.objects.select_related('user').annotate(
        rentals=Count('rental', distinct=True))
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__username__icontains=q) |
                       Q(group__icontains=q) | Q(faculty__icontains=q))
    ctx = {'active': 'members', 'page_title': 'Talabalar', 'members': qs.order_by('user__username')[:100], 'q': q}
    if getattr(request, 'htmx', False):
        return render(request, 'panel/system/_members.html', ctx)
    return render(request, 'panel/system/members.html', ctx)


@library_admin_role_required
def member_detail(request, pk):
    member = get_object_or_404(StudentProfile.objects.select_related('user'), pk=pk)
    rentals = Rental.objects.filter(student=member).select_related('copy__book').order_by('-id')[:30]
    fines = Fine.objects.filter(student=member).select_related('rental__copy__book')
    return render(request, 'panel/system/member_detail.html', {
        'active': 'members', 'page_title': member.user.get_full_name(),
        'member': member, 'rentals': rentals, 'fines': fines,
        'active_count': Rental.objects.filter(student=member, return_date__isnull=True).count(),
        'unpaid_fines': fines.filter(is_paid=False).count(),
    })


# ============================================================ Analitika

@library_admin_role_required
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

    active_students = list(StudentProfile.objects.annotate(rc=Count('rental')).filter(rc__gt=0)
                           .order_by('-rc')[:8].select_related('user'))

    stats = {
        'books': Book.objects.count(),
        'students': StudentProfile.objects.count(),
        'rentals': Rental.objects.count(),
        'reads': ReadingHistory.objects.count(),
    }
    return render(request, 'panel/system/analytics.html', {
        'active': 'analytics', 'page_title': 'Analitika', 'stats': stats,
        'top_rated': Book.objects.filter(rating_count__gt=0).order_by('-avg_rating', '-rating_count')[:8],
        'active_students': active_students,
        'rentals_chart': json.dumps(rentals_chart), 'cats_chart': json.dumps(cats_chart),
        'viewed_chart': json.dumps(viewed_chart), 'rented_chart': json.dumps(rented_chart),
    })


# ============================================================ Sozlamalar

@library_admin_role_required
def settings_view(request):
    obj = LibrarySettings.load()
    form = PanelSettingsForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Sozlamalar saqlandi.")
        return redirect('panel:settings')
    return render(request, 'panel/system/settings.html',
                  {'active': 'settings', 'page_title': 'Sozlamalar', 'form': form})
