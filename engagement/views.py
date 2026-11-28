from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from book_app.citation import gost
from book_app.models import Book
from reading.models import ReadingHistory
from user_app.permissions import Perms, reader_required, require_perm

from . import services
from .forms import ShelfForm
from .models import Favorite, Review, Shelf

# ----------------------------------------------------------- partial render

def _render_reviews(request, book, message=None):
    ctx = services.engagement_context(request.user, book)
    ctx['book'] = book
    ctx['review_message'] = message
    return render(request, 'engagement/partials/_reviews.html', ctx)


def _render_favorite(request, book):
    return render(request, 'engagement/partials/_favorite_button.html', {
        'book': book,
        'is_favorite': services.is_favorite(request.user, book),
    })


# ----------------------------------------------------------- o'quvchi amallari

@require_POST
@reader_required
def toggle_favorite(request, pk):
    book = get_object_or_404(Book, pk=pk)
    services.toggle_favorite(request.user, book)
    return _render_favorite(request, book)


@require_POST
@reader_required
def submit_review(request, pk):
    book = get_object_or_404(Book, pk=pk)
    _, msg = services.submit_review(request.user, book,
                                    request.POST.get('rating'), request.POST.get('text'))
    return _render_reviews(request, book, message=msg)


@reader_required
def my_library(request):
    favorites = (Favorite.objects.filter(user=request.user)
                 .select_related('book__category').prefetch_related('book__authors'))
    history = (ReadingHistory.objects.filter(user=request.user)
               .select_related('book')[:24])
    my_reviews = (Review.objects.filter(user=request.user).select_related('book'))
    return render(request, 'opac/my_library.html', {
        'favorites': favorites,
        'history': history,
        'my_reviews': my_reviews,
        'my_shelves': _own_shelves(request.user),
    })


# ----------------------------------------------------------- ro'yxatlar

def _own_shelves(user):
    return (Shelf.objects.filter(owner=user)
            .annotate(books_count=Count('items'))
            .order_by('-updated_at'))


def _viewable_shelf(request, slug):
    """Ko'rishga ruxsat bo'lmasa 404 — shaxsiy ro'yxat borligi ham oshkor bo'lmaydi."""
    shelf = get_object_or_404(Shelf.objects.select_related('owner'), slug=slug)
    if not services.can_view_shelf(request.user, shelf):
        raise Http404
    return shelf


def _editable_shelf(request, slug):
    shelf = _viewable_shelf(request, slug)
    if not services.can_edit_shelf(request.user, shelf):
        raise Http404
    return shelf


@login_required
def shelf_list(request):
    published = list(services.public_shelves(request.user)
                     .exclude(owner=request.user)
                     .filter(books_count__gt=0))
    return render(request, 'opac/shelves.html', {
        'my_shelves': _own_shelves(request.user),
        'official_shelves': [s for s in published if s.is_official],
        'other_shelves': [s for s in published if not s.is_official],
    })


@login_required
def shelf_create(request):
    form = ShelfForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        data = dict(form.cleaned_data)
        shelf, msg = services.create_shelf(request.user, data.pop('name'), **data)
        if shelf:
            messages.success(request, msg)
            return redirect(shelf)
        form.add_error(None, msg)
    return render(request, 'opac/shelf_form.html', {'form': form, 'shelf': None})


@login_required
def shelf_detail(request, slug):
    shelf = _viewable_shelf(request, slug)
    items = list(shelf.items
                 .select_related('book__category', 'book__publisher', 'book__series')
                 .prefetch_related('book__authors'))
    return render(request, 'opac/shelf_detail.html', {
        'shelf': shelf,
        'items': items,
        'citations': [gost(item.book) for item in items],
        'can_edit': services.can_edit_shelf(request.user, shelf),
    })


@login_required
def shelf_edit(request, slug):
    shelf = _editable_shelf(request, slug)
    form = ShelfForm(request.POST or None, instance=shelf, user=request.user)
    if request.method == 'POST' and form.is_valid():
        shelf = form.save()
        messages.success(request, "Ro'yxat saqlandi.")
        return redirect(shelf)
    # Yaroqsiz forma `instance`ni o'zgartirib yuboradi — sahifaga asl yozuvni beramiz
    shelf = Shelf.objects.get(pk=shelf.pk)
    return render(request, 'opac/shelf_form.html', {'form': form, 'shelf': shelf})


@require_POST
@login_required
def shelf_delete(request, slug):
    shelf = _editable_shelf(request, slug)
    name = shelf.name
    shelf.delete()
    messages.success(request, f"«{name}» ro'yxati o'chirildi.")
    return redirect('engagement:shelf_list')


@require_POST
@login_required
def shelf_remove_item(request, slug, book_pk):
    shelf = _editable_shelf(request, slug)
    _, msg = services.remove_from_shelf(shelf, get_object_or_404(Book, pk=book_pk))
    messages.success(request, msg)
    return redirect(shelf)


@require_POST
@login_required
def shelf_item_note(request, slug, book_pk):
    shelf = _editable_shelf(request, slug)
    item = get_object_or_404(shelf.items, book_id=book_pk)
    item.note = request.POST.get('note', '').strip()[:255]
    item.save(update_fields=['note'])
    messages.success(request, "Izoh saqlandi.")
    return redirect(shelf)


# --- Kitob sahifasidagi "Ro'yxatga" menyusi (HTMX) --------------------------

def _render_picker(request, book, message=None, ok=True):
    return render(request, 'engagement/partials/_shelf_picker.html', {
        'book': book,
        'shelves': services.shelves_with_book(request.user, book),
        'picker_message': message,
        'picker_ok': ok,
    })


@login_required
def shelf_picker(request, pk):
    return _render_picker(request, get_object_or_404(Book, pk=pk))


@require_POST
@login_required
def shelf_toggle(request, pk, slug):
    book = get_object_or_404(Book, pk=pk)
    # Menyuda faqat o'z ro'yxatlari — boshqanikiga bu yo'l bilan yozib bo'lmaydi
    shelf = get_object_or_404(Shelf, slug=slug, owner=request.user)
    _, msg = services.toggle_shelf_item(shelf, book)
    return _render_picker(request, book, msg)


@require_POST
@login_required
def shelf_quick_add(request, pk):
    """Menyudan yangi ro'yxat ochib, kitobni darrov qo'shadi."""
    book = get_object_or_404(Book, pk=pk)
    shelf, msg = services.create_shelf(request.user, request.POST.get('name'))
    if shelf is None:
        return _render_picker(request, book, msg, ok=False)
    services.add_to_shelf(shelf, book)
    return _render_picker(request, book, f"«{shelf.name}» yaratildi va kitob qo'shildi.")


# ----------------------------------------------------------- moderatsiya

def _render_moderation(request, message=None):
    pending = Review.objects.filter(is_approved=False).select_related('user', 'book')
    return render(request, 'engagement/partials/_moderation_panel.html', {
        'pending_reviews': pending,
        'mod_message': message,
    })


@require_perm(Perms.MODERATE_REVIEWS)
def moderate(request):
    # Eski sahifa — endi kutubxonachi paneli (/panel/reviews/) bilan almashtirildi
    return redirect('panel:reviews')


@require_POST
@require_perm(Perms.MODERATE_REVIEWS)
def approve_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    services.approve_review(review)
    return _render_moderation(request, "Sharh tasdiqlandi.")


@require_POST
@require_perm(Perms.MODERATE_REVIEWS)
def reject_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    services.reject_review(review)
    return _render_moderation(request, "Sharh rad etildi.")
