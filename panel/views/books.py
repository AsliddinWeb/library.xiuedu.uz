import os
from io import BytesIO

import requests as http
from django.contrib import messages
from django.core.files import File
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from book_app.models import Author, Book, Genre, Item
from book_app.services import change_item_status, create_items, withdraw_item
from user_app.permissions import Perms, require_perm

from ..forms import PanelBookForm

SORTS = {'title', '-title', '-created_at', 'created_at', '-view_count', 'view_count', '-id'}


@require_perm(Perms.CATALOG_VIEW)
def book_list(request):
    # Nusxa sonlari `Book.items_count` / `available_count` da saqlanadi —
    # har ro'yxatda COUNT qilinmaydi (P2 denormalizatsiyasi).
    books = (Book.objects
             .select_related('category')
             .prefetch_related('authors')
             .annotate(
                 copies_total=F('items_count'),
                 copies_avail=F('available_count')))

    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(
            Q(title__icontains=q) | Q(subtitle__icontains=q) | Q(isbn__icontains=q) |
            Q(udc__icontains=q) | Q(authors__full_name__icontains=q) |
            Q(publisher__name__icontains=q) | Q(subjects__name__icontains=q)
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

    # P2-B filtrlari: yozuv turi, darslik, fakultet
    record_type = request.GET.get('record_type', '')
    if record_type:
        books = books.filter(record_type=record_type)
    textbook = request.GET.get('textbook', '')
    if textbook in ('1', '0'):
        books = books.filter(is_textbook=(textbook == '1'))
    faculty = request.GET.get('faculty', '').strip()
    if faculty:
        books = books.filter(faculty__icontains=faculty)

    sort = request.GET.get('sort', '-id')
    books = books.order_by(sort if sort in SORTS else '-id')

    page_obj = Paginator(books, 12).get_page(request.GET.get('page', 1))

    ctx = {
        'active': 'books', 'page_title': 'Kitoblar', 'page_obj': page_obj,
        'q': q, 'category': category, 'mode': mode, 'active_filter': active, 'sort': sort,
        'record_type': record_type, 'textbook': textbook, 'faculty': faculty,
        'categories': Genre.objects.all(), 'modes': Book.ReadingMode.choices,
        'record_types': Book.RecordType.choices,
        'total': page_obj.paginator.count,
    }
    if getattr(request, 'htmx', False):
        return render(request, 'panel/books/_table.html', ctx)
    return render(request, 'panel/books/list.html', ctx)


@require_perm(Perms.CATALOG_EDIT)
def book_create(request):
    form = PanelBookForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        book = form.save()
        messages.success(request, "Kitob yaratildi.")
        return redirect('panel:book_detail', pk=book.pk)
    return render(request, 'panel/books/form.html',
                  {'form': form, 'active': 'books', 'page_title': 'Yangi kitob'})


@require_perm(Perms.CATALOG_EDIT)
def book_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    form = PanelBookForm(request.POST or None, request.FILES or None, instance=book)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Saqlandi.")
        return redirect('panel:book_detail', pk=book.pk)
    return render(request, 'panel/books/form.html',
                  {'form': form, 'book': book, 'active': 'books', 'page_title': 'Kitobni tahrirlash'})


@require_perm(Perms.CATALOG_VIEW)
def book_detail(request, pk):
    book = get_object_or_404(
        Book.objects
        .select_related('category', 'publisher', 'series')
        .prefetch_related('authors', 'subjects', 'contributor_set__author'),
        pk=pk)

    ctx = _copies_ctx(book)
    ctx.update({
        'active': 'books',
        'page_title': book.title,
        'breadcrumb': [{'label': "Kitoblar", 'url': '/panel/books/'},
                       {'label': book.title[:40]}],
    })
    return render(request, 'panel/books/detail.html', ctx)


@require_perm(Perms.CATALOG_DELETE)
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        messages.success(request, "Kitob o'chirildi.")
        return redirect('panel:books')
    return render(request, 'panel/books/delete.html',
                  {'book': book, 'active': 'books', 'page_title': "Kitobni o'chirish"})


# ---------------- Nusxalar (HTMX) ----------------

def _copies_ctx(book):
    """Nusxalar bloki uchun umumiy kontekst (partiya amallari ham shu yerdan)."""
    from holdings.models import ShelfLocation
    return {
        'book': book,
        'item_statuses': Item.Status.choices,
        'shelves': (ShelfLocation.objects.filter(is_active=True)
                    .select_related('library').order_by('library', 'code')),
    }


def _render_copies(request, book):
    return render(request, 'panel/books/_copies.html', _copies_ctx(book))


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def copy_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    try:
        qty = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        qty = 1
    create_items(book, max(1, min(qty, 50)), created_by=request.user)
    return _render_copies(request, book)


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def copy_toggle(request, pk):
    """Nusxani "mavjud" va "faqat zalda" holatlari orasida almashtiradi.

    Ijaradagi nusxa bu yerdan o'zgartirilmaydi — u qaytarilganda o'zi bo'shaydi.
    """
    item = get_object_or_404(Item, pk=pk)
    if item.status == Item.Status.ON_LOAN:
        messages.error(request, "Ijaradagi nusxaning holatini bu yerdan o'zgartirib bo'lmaydi.")
        return _render_copies(request, item.book)

    new_status = (Item.Status.NOT_FOR_LOAN if item.status == Item.Status.AVAILABLE
                  else Item.Status.AVAILABLE)
    change_item_status(item, new_status, reason="Panelda qo'lda o'zgartirildi", by=request.user)
    return _render_copies(request, item.book)


@require_POST
@require_perm(Perms.ITEMS_WITHDRAW)
def copy_delete(request, pk):
    """Nusxani hisobdan chiqaradi (jismonan o'chirmaydi — fond tarixi saqlanadi)."""
    item = get_object_or_404(Item, pk=pk)
    book = item.book

    if item.rental_set.filter(return_date__isnull=True).exists():
        messages.error(request, "Faol ijaradagi nusxani hisobdan chiqarib bo'lmaydi.")
    elif item.status == Item.Status.WITHDRAWN:
        messages.info(request, "Bu nusxa allaqachon hisobdan chiqarilgan.")
    else:
        withdraw_item(item, reason=request.POST.get('reason', "Panel orqali"), by=request.user)
        messages.success(request, f"{item.barcode} hisobdan chiqarildi.")
    return _render_copies(request, book)


@require_perm(Perms.CATALOG_IMPORT)
def import_books(request):
    """Tashqi API'dan kitoblarni ommaviy import (har bir kitob xato-bardosh)."""
    if request.method != 'POST':
        return render(request, 'panel/import.html', {'active': 'import', 'page_title': 'Kitob import'})

    url = request.POST.get('url', '').strip()
    if not url:
        return JsonResponse({'error': 'URL kiriting.'}, status=400)
    try:
        resp = http.get(url, timeout=20)
        resp.raise_for_status()
        results = resp.json().get('results', [])
    except Exception as e:
        return JsonResponse({'error': f"Manbaga ulanib bo'lmadi: {e}"}, status=400)

    created = 0
    for item in results:
        try:
            year_raw = str(item.get('year') or '')
            published_year = int(year_raw) if year_raw.isdigit() else None
            author, _ = Author.objects.get_or_create(full_name=item.get('author', {}).get('name') or "Noma'lum")
            category, _ = Genre.objects.get_or_create(name=item.get('category', {}).get('title') or 'Boshqa')
            book = Book.objects.create(
                title=item.get('title') or 'Nomsiz',
                published_year=published_year,
                description=item.get('description') or '',
                page_count=item.get('page_count') or None,
                category=category,
                reading_mode=Book.ReadingMode.DIGITAL,
            )
            book.authors.add(author)
            book.slug = f"{slugify(book.title)[:280] or 'kitob'}-{book.pk}"
            book.save(update_fields=['slug'])

            cover = item.get('photo')
            if cover:
                try:
                    ir = http.get(cover, timeout=15)
                    if ir.ok:
                        book.cover_image.save(os.path.basename(cover) or 'cover.jpg', File(BytesIO(ir.content)), save=True)
                except Exception:
                    pass
            src = item.get('source')
            if src:
                try:
                    br = http.get(src, timeout=30)
                    if br.ok:
                        book.electronic_version.save(os.path.basename(src) or 'book.pdf', File(BytesIO(br.content)), save=True)
                except Exception:
                    pass
            created += 1
        except Exception:
            continue

    return JsonResponse({'success': f"{created} ta kitob muvaffaqiyatli qo'shildi."})
