from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from audit.models import ActionLog
from audit.services import log_action, log_change, snapshot
from book_app.models import Book, Genre, Item, Rental
from book_app.services import change_item_status, create_items, withdraw_item
from circulation.loans import OPEN_HOLDS
from circulation.models import Reservation
from holdings.models import ItemType, Library, ShelfLocation
from user_app.permissions import Perms, has_perm, require_perm

from ..exports import csv_response, wants_csv
from ..forms import PanelBookForm
from ..htmx import render_partial_or_page, toast

MAX_COPIES = 100

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
    category = category if category.isdigit() else ''
    if category:
        books = books.filter(category_id=category)
    # Ma'lumotnomalardan kelgan havolalar: muallif, nashriyot, turkum, mavzu
    related = {}
    for param, lookup in (('author', 'authors'), ('publisher', 'publisher_id'),
                          ('series', 'series_id'), ('subject', 'subjects')):
        value = request.GET.get(param, '')
        if value.isdigit():
            books = books.filter(**{lookup: value})
            related[param] = value
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
    books = books.order_by(sort if sort in SORTS else '-id', '-pk')

    if wants_csv(request):
        return _export_books(request, books)

    page_obj = Paginator(books, 20).get_page(request.GET.get('page', 1))
    filters = {key: value for key, value in (
        ('q', q), ('category', category), ('mode', mode), ('active', active), ('sort', sort),
        ('record_type', record_type), ('textbook', textbook), ('faculty', faculty),
    ) if value}
    filters.update(related)

    ctx = {
        'query': '&' + urlencode(filters) if filters else '',
        'export_query': urlencode({**filters, 'export': 'csv'}),
        'related': related,
        'active': 'books', 'page_title': 'Kitoblar', 'page_obj': page_obj,
        'q': q, 'category': category, 'mode': mode, 'active_filter': active, 'sort': sort,
        'record_type': record_type, 'textbook': textbook, 'faculty': faculty,
        'categories': Genre.objects.all(), 'modes': Book.ReadingMode.choices,
        'record_types': Book.RecordType.choices,
        'total': page_obj.paginator.count,
    }
    return render_partial_or_page(request, 'panel/books/list.html', 'panel/books/_table.html', ctx)


def _export_books(request, books):
    books = books.select_related('publisher')
    rows = ((b.title, ', '.join(a.full_name for a in b.authors.all()), b.category.name,
             b.publisher.name if b.publisher_id else '', b.published_year, b.isbn, b.udc,
             b.language, b.items_count, b.available_count, 'Faol' if b.is_active else 'Nofaol')
            for b in books.iterator(chunk_size=500))
    return csv_response(request, 'kitoblar',
                        ['Sarlavha', 'Mualliflar', 'Katalog', 'Nashriyot', 'Yil', 'ISBN', 'UDK',
                         'Til', 'Nusxa', 'Mavjud', 'Holat'], rows)


def _number(raw, default=0, maximum=100):
    try:
        return max(0, min(int(raw), maximum))
    except (TypeError, ValueError):
        return default


@require_perm(Perms.CATALOG_EDIT)
def book_create(request):
    form = PanelBookForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        book = form.save()
        log_action(ActionLog.Action.BIBLIO_CREATE, obj=book)
        copies = _number(request.POST.get('initial_copies'), maximum=MAX_COPIES)
        if copies and has_perm(request.user, Perms.ITEMS_MANAGE):
            create_items(book, copies, created_by=request.user)
            messages.success(request, f"Kitob va {copies} ta nusxa yaratildi.")
        else:
            messages.success(request, "Kitob yaratildi.")
        if 'save_and_new' in request.POST:
            return redirect('panel:book_create')
        return redirect('panel:book_detail', pk=book.pk)
    return render(request, 'panel/books/form.html',
                  {'form': form, 'active': 'books', 'page_title': 'Yangi kitob'})


@require_perm(Perms.CATALOG_EDIT)
def book_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    before = snapshot(book)
    form = PanelBookForm(request.POST or None, request.FILES or None, instance=book)
    if request.method == 'POST' and form.is_valid():
        form.save()
        log_change(ActionLog.Action.BIBLIO_EDIT, book, before)
        messages.success(request, "Saqlandi.")
        return redirect('panel:book_detail', pk=book.pk)
    return render(request, 'panel/books/form.html',
                  {'form': form, 'book': book, 'active': 'books',
                   'page_title': 'Kitobni tahrirlash'})


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
        'contributors': book.contributors_by_role,
        'queue_count': Reservation.objects.filter(
            book=book, status__in=OPEN_HOLDS).count(),
    })
    return render(request, 'panel/books/detail.html', ctx)


def _delete_summary(book):
    """O'chirishdan oldin nima yo'qolishini hisoblaydi."""
    return {
        'items': Item.objects.filter(book=book).count(),
        'loans': Rental.objects.filter(copy__book=book).count(),
        'open_loans': Rental.objects.filter(copy__book=book, return_date__isnull=True).count(),
        'reviews': book.reviews.count(),
        'holds': Reservation.objects.filter(book=book, status__in=OPEN_HOLDS).count(),
    }


@require_perm(Perms.CATALOG_DELETE)
def book_delete(request, pk):
    """Ijara tarixi bor kitob o'chirilmaydi — aks holda tarix va jarimalar yo'qoladi."""
    book = get_object_or_404(Book, pk=pk)
    summary = _delete_summary(book)
    if request.method == 'POST':
        if 'deactivate' in request.POST:
            book.is_active = False
            book.save(update_fields=['is_active', 'updated_at'])
            log_action(ActionLog.Action.BIBLIO_EDIT, obj=book, note="Nofaol qilindi")
            messages.success(request, "Kitob nofaol qilindi — saytda ko'rinmaydi.")
            return redirect('panel:book_detail', pk=book.pk)
        if summary['loans']:
            messages.error(request, "Ijara tarixi bor kitob o'chirilmaydi.")
            return redirect('panel:book_delete', pk=book.pk)
        log_action(ActionLog.Action.BIBLIO_DELETE, obj=book)
        book.delete()
        messages.success(request, "Kitob o'chirildi.")
        return redirect('panel:books')
    return render(request, 'panel/books/delete.html',
                  {'book': book, 'summary': summary, 'active': 'books',
                   'page_title': "Kitobni o'chirish"})


# ---------------- Nusxalar (HTMX) ----------------

def _copies_ctx(book):
    """Nusxalar bloki uchun umumiy kontekst (partiya amallari ham shu yerdan)."""
    return {
        'book': book,
        'copies': (Item.objects.filter(book=book)
                   .select_related('item_type', 'library', 'shelf_location')
                   .order_by('inventory_number', 'pk')),
        'item_statuses': Item.Status.choices,
        'item_types': ItemType.objects.filter(is_active=True),
        'libraries': Library.objects.filter(is_active=True),
        'sources': Item.Source.choices,
        'shelves': (ShelfLocation.objects.filter(is_active=True)
                    .select_related('library').order_by('library', 'code')),
    }


def _render_copies(request, book, message='', level='success'):
    book.refresh_from_db()
    response = render(request, 'panel/books/_copies.html', _copies_ctx(book))
    return toast(response, message, level) if message else response


def _choice(model, pk):
    return model.objects.filter(pk=pk, is_active=True).first() if str(pk).isdigit() else None


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def copy_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    quantity = max(1, _number(request.POST.get('quantity', 1), default=1, maximum=MAX_COPIES))

    shelf = _choice(ShelfLocation, request.POST.get('shelf_location'))
    library = _choice(Library, request.POST.get('library')) or (shelf.library if shelf else None)
    if shelf and library and shelf.library_id != library.pk:
        return _render_copies(request, book, "Tanlangan javon boshqa filialga tegishli.", 'danger')

    source = request.POST.get('source')
    raw_price = (request.POST.get('price') or '').replace(' ', '').replace(',', '.')
    try:
        price = Decimal(raw_price or '0')
    except InvalidOperation:
        price = None
    if price is None or not price.is_finite() or not 0 <= price < Decimal('1000000000'):
        return _render_copies(request, book, "Narx noto'g'ri yozilgan.", 'danger')

    created = create_items(
        book, quantity, created_by=request.user,
        item_type=_choice(ItemType, request.POST.get('item_type')),
        library=library, shelf_location=shelf, price=price,
        acquisition_source=source if source in Item.Source.values else Item.Source.PURCHASE,
        status=(Item.Status.NOT_FOR_LOAN if request.POST.get('reading_room')
                else Item.Status.AVAILABLE))
    codes = (created[0].barcode if len(created) == 1
             else f"{created[0].barcode} … {created[-1].barcode}")
    return _render_copies(request, book, f"{len(created)} ta nusxa qo'shildi: {codes}")


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def copy_toggle(request, pk):
    """Nusxani "mavjud" va "faqat zalda" holatlari orasida almashtiradi.

    Ijaradagi nusxa bu yerdan o'zgartirilmaydi — u qaytarilganda o'zi bo'shaydi.
    """
    item = get_object_or_404(Item, pk=pk)
    if item.rental_set.filter(return_date__isnull=True).exists():
        return _render_copies(
            request, item.book,
            "Ijaradagi nusxaning holatini bu yerdan o'zgartirib bo'lmaydi.", 'danger')

    new_status = (Item.Status.NOT_FOR_LOAN if item.status == Item.Status.AVAILABLE
                  else Item.Status.AVAILABLE)
    _, message = change_item_status(item, new_status, reason="Panelda qo'lda o'zgartirildi",
                                    by=request.user)
    return _render_copies(request, item.book, message)


@require_POST
@require_perm(Perms.ITEMS_WITHDRAW)
def copy_delete(request, pk):
    """Nusxani hisobdan chiqaradi (jismonan o'chirmaydi — fond tarixi saqlanadi)."""
    item = get_object_or_404(Item, pk=pk)
    book = item.book

    if item.rental_set.filter(return_date__isnull=True).exists():
        return _render_copies(request, book,
                              "Faol ijaradagi nusxani hisobdan chiqarib bo'lmaydi.", 'danger')
    if item.status == Item.Status.WITHDRAWN:
        return _render_copies(request, book, "Bu nusxa allaqachon hisobdan chiqarilgan.",
                              'warning')
    reason = request.POST.get('reason', '').strip() or "Panel orqali"
    withdraw_item(item, reason=reason, by=request.user)
    return _render_copies(request, book, f"{item.barcode or item.inventory_number} hisobdan chiqarildi.")
