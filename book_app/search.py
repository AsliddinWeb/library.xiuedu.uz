"""
Katalog qidiruvi.

Uch qatlamli:
  1. **Transliteratsiya** (`translit.fold`) — kirill va lotin yozuv bir ko'rinishga
     keltiriladi, chalkashadigan harflar (q/k, x/h) birlashtiriladi.
  2. **To'liq matnli qidiruv** (PostgreSQL FTS) — so'z bo'yicha aniq moslik va
     reyting; `simple` konfiguratsiyasi ishlatiladi (o'zbek tili uchun Postgres'da
     lug'at yo'q, lekin matn allaqachon normallashgan).
  3. **Trigram** (`pg_trgm`) — xato yozilgan so'zni ham topadi:
     "algaritm" -> "Algoritmlar".

Indeks `Book.search_text` (folded matn) va `Book.search_vector` da saqlanadi;
ikkalasi ham `update_search_text()` orqali yangilanadi.
"""
import logging

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import F, Q

from .translit import fold

logger = logging.getLogger('search')

#: So'z darajasidagi trigram o'xshashligi chegarasi (0..1).
#: `TrigramWordSimilarity` so'rovni butun matn bilan emas, undagi ENG MOS
#: so'z bilan solishtiradi — uzun matnda ham "algaritm" -> "algoritmlar"
#: topiladi. Real fondda o'lchandi: mos yozuv 0.42–1.0, begona yozuv 0.0–0.11
#: oralig'ida — shuning uchun chegara 0.35.
WORD_SIMILARITY_THRESHOLD = 0.35


# --------------------------------------------------------------------------
#  Indeksni qurish
# --------------------------------------------------------------------------

def build_search_text(book) -> str:
    """Kitobning qidiruv matni: sarlavha, mualliflar, mavzular, nashriyot...

    Hammasi `fold()` dan o'tkaziladi — kirillda yozilgan yozuv lotincha
    so'rovda ham topiladi.
    """
    parts = [
        book.title,
        book.subtitle,
        book.parallel_title,
        book.isbn,
        book.udc,
        book.bbk,
        book.faculty,
        book.department,
        book.series_number,
    ]

    if book.pk:
        parts += [author.full_name for author in book.authors.all()]
        parts += [subject.name for subject in book.subjects.all()]
    if book.publisher_id:
        parts.append(book.publisher.name)
    if book.series_id:
        parts.append(book.series.name)
    if book.category_id:
        parts.append(book.category.name)

    return fold(" ".join(str(part) for part in parts if part))


def build_search_title(book) -> str:
    """Faqat sarlavhalar — reytingda ustunlik berish uchun alohida saqlanadi."""
    return fold(" ".join(str(part) for part in
                         (book.title, book.subtitle, book.parallel_title) if part))


def update_search_text(book, save=True):
    """Bitta kitobning qidiruv matnini qayta hisoblaydi."""
    book.search_text = build_search_text(book)[:4000]
    book.search_title = build_search_title(book)[:1000]
    if save:
        type(book).objects.filter(pk=book.pk).update(
            search_text=book.search_text, search_title=book.search_title)
        refresh_search_vector(book.pk)
    return book.search_text


def refresh_search_vector(book_id=None):
    """`search_vector` ni qayta quradi — sarlavha OG'IRROQ vazn bilan.

    `setweight` tufayli sarlavhada uchragan so'z reytingda mavzu yoki
    nashriyotda uchragandan yuqori turadi ("huquq" so'rovida "Davlat va huquq
    nazariyasi" birinchi, kategoriyasi "huquq" bo'lgan boshqa kitob keyin).

    FTS vektori SQL darajasida yangilanadi — minglab yozuv uchun tez.
    """
    if connection.vendor != 'postgresql':
        return 0

    from .models import Book
    qs = Book.objects.all() if book_id is None else Book.objects.filter(pk=book_id)
    return qs.update(
        search_vector=(SearchVector('search_title', config='simple', weight='A') +
                       SearchVector('search_text', config='simple', weight='D')))


def rebuild_all(batch_size=500, stdout=None):
    """Butun katalog uchun indeksni qayta quradi (management buyruq uchun)."""
    from .models import Book

    books = (Book.objects
             .select_related('publisher', 'series', 'category')
             .prefetch_related('authors', 'subjects'))

    updated, bucket = 0, []
    for book in books.iterator(chunk_size=batch_size):
        book.search_text = build_search_text(book)[:4000]
        book.search_title = build_search_title(book)[:1000]
        bucket.append(book)
        if len(bucket) >= batch_size:
            Book.objects.bulk_update(bucket, ['search_text', 'search_title'])
            updated += len(bucket)
            bucket = []
            if stdout:
                stdout.write(f"  ... {updated}", ending='\r')
    if bucket:
        Book.objects.bulk_update(bucket, ['search_text', 'search_title'])
        updated += len(bucket)

    refresh_search_vector()
    return updated


# --------------------------------------------------------------------------
#  Qidiruv
# --------------------------------------------------------------------------

def search_books(queryset, query: str):
    """Qidiruv natijalari — moslik darajasi bo'yicha saralangan.

    SQLite'da (testlar) oddiy `icontains` ishlaydi; PostgreSQL'da FTS + trigram.
    """
    text = fold(query or "")
    if not text:
        return queryset

    if connection.vendor != 'postgresql':
        return queryset.filter(search_text__icontains=text)

    from django.contrib.postgres.search import TrigramWordSimilarity

    search_query = SearchQuery(text, config='simple', search_type='websearch')

    return (queryset
            .annotate(
                rank=SearchRank(F('search_vector'), search_query),
                title_similarity=TrigramWordSimilarity(text, 'search_title'),
                similarity=TrigramWordSimilarity(text, 'search_text'),
            )
            .filter(
                Q(search_vector=search_query) |
                Q(similarity__gte=WORD_SIMILARITY_THRESHOLD) |
                Q(search_text__icontains=text)
            )
            # Saralash tartibi:
            #   1) FTS reytingi — sarlavha vazni og'irroq (setweight A/D)
            #   2) sarlavhaga trigram o'xshashligi — xato yozilgan so'rovda hal qiladi
            #   3) umumiy o'xshashlik, keyin ommaboplik
            .order_by('-rank', '-title_similarity', '-similarity', '-view_count'))


def suggest(queryset, query: str, limit=8):
    """Qidiruv maydonidagi tezkor takliflar (avtomatik to'ldirish)."""
    text = fold(query or "")
    if len(text) < 2:
        return queryset.none()
    return (search_books(queryset, query)
            .only('id', 'title', 'slug', 'cover_image')[:limit])
