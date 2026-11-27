"""
OPAC — o'quvchi uchun katalog (qidiruv va kashfiyot).

P5: transliteratsiyali qidiruv (`book_app.search`) + fasetli filtrlar.
Eski `student_book_list` o'rniga shu view ishlaydi; URL o'zgarmadi.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from ..models import Book, Genre, Subject
from ..search import search_books

PER_PAGE = 18

#: Saralash variantlari. `relevance` faqat qidiruv bo'lganda ma'noga ega.
SORTS = {
    'relevance': "Mosligi bo'yicha",
    '-id': "Yangi qo'shilgan",
    '-view_count': "Ko'p o'qilgan",
    '-avg_rating': "Yuqori reyting",
    'title': "Nom (A-Z)",
}

#: Faset: nashr turi
FORMATS = {
    'digital': "Raqamli (onlayn o'qish)",
    'physical': "Jismoniy (ijaraga)",
    'audio': "Audio",
}


def _apply_facets(books, params):
    """Tanlangan fasetlarni qo'llaydi va qo'llanganlarini qaytaradi."""
    applied = {}

    category = params.get('category', '')
    if category:
        books = books.filter(category_id=category)
        applied['category'] = category

    subject = params.get('subject', '')
    if subject:
        books = books.filter(subjects__id=subject)
        applied['subject'] = subject

    language = params.get('language', '').strip()
    if language:
        books = books.filter(language__iexact=language)
        applied['language'] = language

    fmt = params.get('format', '')
    if fmt == 'digital':
        books = books.filter(Q(electronic_version__gt='') | Q(audio_version__gt=''))
        applied['format'] = fmt
    elif fmt == 'physical':
        books = books.filter(items_count__gt=0)
        applied['format'] = fmt
    elif fmt == 'audio':
        books = books.filter(audio_version__gt='')
        applied['format'] = fmt

    if params.get('available') == '1':
        books = books.filter(available_count__gt=0)
        applied['available'] = '1'

    faculty = params.get('faculty', '').strip()
    if faculty:
        books = books.filter(faculty__icontains=faculty)
        applied['faculty'] = faculty

    for key, lookup in (('year_from', 'published_year__gte'),
                        ('year_to', 'published_year__lte')):
        value = params.get(key, '').strip()
        if value.isdigit():
            books = books.filter(**{lookup: int(value)})
            applied[key] = value

    return books, applied


@login_required
def catalog(request):
    query = request.GET.get('q', '').strip()

    books = (Book.objects
             .filter(is_active=True, category__is_active=True)
             .select_related('category')
             .prefetch_related('authors'))

    if query:
        books = search_books(books, query)

    books, applied = _apply_facets(books, request.GET)
    books = books.distinct()

    # Saralash: qidiruvda standart — moslik, aks holda yangi qo'shilganlar
    sort = request.GET.get('sort') or ('relevance' if query else '-id')
    if sort != 'relevance' and sort in SORTS:
        books = books.order_by(sort)
    elif sort == 'relevance' and not query:
        books = books.order_by('-id')

    page_obj = Paginator(books, PER_PAGE).get_page(request.GET.get('page', 1))

    # Faset ro'yxatlari — joriy natijalar bo'yicha sonlar bilan
    base = Book.objects.filter(is_active=True, category__is_active=True)
    if query:
        base = search_books(base, query)

    categories = (Genre.objects.filter(is_active=True, book__in=base)
                  .annotate(n=Count('book', distinct=True))
                  .filter(n__gt=0).order_by('-n', 'name')[:12])
    subjects = (Subject.objects.filter(books__in=base)
                .annotate(n=Count('books', distinct=True))
                .filter(n__gt=0).order_by('-n', 'name')[:12])
    languages = (base.values('language')
                 .annotate(n=Count('id')).filter(n__gt=0).order_by('-n')[:8])

    # Faol filtrlarni saqlagan holda havola yasash uchun
    query_string = ''.join(
        f"&{key}={value}" for key, value in
        [('q', query), ('sort', sort)] + list(applied.items()) if value)

    context = {
        'page_obj': page_obj,
        'books': page_obj,
        'total': page_obj.paginator.count,
        'query': query,
        'sort': sort,
        'sorts': SORTS,
        'formats': FORMATS,
        'applied': applied,
        'has_filters': bool(applied),
        'categories': categories,
        'subjects': subjects,
        'languages': languages,
        'query_string': query_string,
    }

    if getattr(request, 'htmx', False):
        return render(request, 'opac/_results.html', context)
    return render(request, 'opac/catalog.html', context)
