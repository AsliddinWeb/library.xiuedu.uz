from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from book_app.models import Book, Copy, Genre
from book_app.utils import add_copies
from user_app.utils import library_admin_role_required

from ..forms import PanelBookForm

SORTS = {'title', '-title', '-created_at', 'created_at', '-view_count', 'view_count', '-id'}


@library_admin_role_required
def book_list(request):
    books = (Book.objects
             .select_related('category')
             .prefetch_related('authors')
             .annotate(
                 copies_total=Count('copy', distinct=True),
                 copies_avail=Count('copy', filter=Q(copy__is_available=True), distinct=True)))

    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(
            Q(title__icontains=q) | Q(isbn__icontains=q) | Q(authors__full_name__icontains=q)
        ).distinct()

    category = request.GET.get('category', '')
    if category:
        books = books.filter(category_id=category)
    mode = request.GET.get('mode', '')
    if mode:
        books = books.filter(reading_mode=mode)
    active = request.GET.get('active', '')
    if active in ('1', '0'):
        books = books.filter(is_active=(active == '1'))

    sort = request.GET.get('sort', '-id')
    books = books.order_by(sort if sort in SORTS else '-id')

    page_obj = Paginator(books, 12).get_page(request.GET.get('page', 1))

    ctx = {
        'active': 'books', 'page_title': 'Kitoblar', 'page_obj': page_obj,
        'q': q, 'category': category, 'mode': mode, 'active_filter': active, 'sort': sort,
        'categories': Genre.objects.all(), 'modes': Book.ReadingMode.choices,
        'total': page_obj.paginator.count,
    }
    if getattr(request, 'htmx', False):
        return render(request, 'panel/books/_table.html', ctx)
    return render(request, 'panel/books/list.html', ctx)


@library_admin_role_required
def book_create(request):
    form = PanelBookForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        book = form.save()
        messages.success(request, "Kitob yaratildi.")
        return redirect('panel:book_detail', pk=book.pk)
    return render(request, 'panel/books/form.html',
                  {'form': form, 'active': 'books', 'page_title': 'Yangi kitob'})


@library_admin_role_required
def book_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    form = PanelBookForm(request.POST or None, request.FILES or None, instance=book)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Saqlandi.")
        return redirect('panel:book_detail', pk=book.pk)
    return render(request, 'panel/books/form.html',
                  {'form': form, 'book': book, 'active': 'books', 'page_title': 'Kitobni tahrirlash'})


@library_admin_role_required
def book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related('category').prefetch_related('authors'), pk=pk)
    return render(request, 'panel/books/detail.html',
                  {'book': book, 'active': 'books', 'page_title': book.title})


@library_admin_role_required
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        messages.success(request, "Kitob o'chirildi.")
        return redirect('panel:books')
    return render(request, 'panel/books/delete.html',
                  {'book': book, 'active': 'books', 'page_title': "Kitobni o'chirish"})


# ---------------- Nusxalar (HTMX) ----------------

def _render_copies(request, book):
    return render(request, 'panel/books/_copies.html', {'book': book})


@require_POST
@library_admin_role_required
def copy_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    try:
        qty = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        qty = 1
    add_copies(book, max(1, min(qty, 50)))
    return _render_copies(request, book)


@require_POST
@library_admin_role_required
def copy_toggle(request, pk):
    copy = get_object_or_404(Copy, pk=pk)
    copy.is_available = not copy.is_available
    copy.save(update_fields=['is_available'])
    return _render_copies(request, copy.book)


@require_POST
@library_admin_role_required
def copy_delete(request, pk):
    copy = get_object_or_404(Copy, pk=pk)
    book = copy.book
    # faol ijaradagi nusxani o'chirmaymiz
    if copy.rental_set.filter(return_date__isnull=True).exists():
        messages.error(request, "Faol ijaradagi nusxani o'chirib bo'lmaydi.")
    else:
        copy.delete()
    return _render_copies(request, book)
