"""
Panelning ma'lumotnomalari: muallif, katalog, nashriyot, turkum, mavzu va
a'zo toifasi. Har biri `crud.Resource` — view va manzillar avtomatik.
"""
from django.db import transaction

from book_app.models import Author, Book, Contributor, Genre, Publisher, Series, Subject
from book_app.search import update_search_text
from user_app.models import PatronCategory
from user_app.permissions import Perms

from . import forms
from .crud import Column, Resource


def _books(param):
    """Kitoblar ro'yxatiga filtrlangan havola yasovchi funksiya."""
    return lambda obj: f'/panel/books/?{param}={obj.pk}'


def _reindex(book_ids):
    """Ommaviy `update()` signallarni chaqirmaydi — qidiruv indeksi qo'lda yangilanadi."""
    for book in Book.objects.filter(pk__in=book_ids):
        update_search_text(book)


# --------------------------------------------------------------------------
#  Birlashtirish: manbadagi bog'liqliklar maqsadga o'tadi, manba o'chiriladi
# --------------------------------------------------------------------------

@transaction.atomic
def merge_authors(source, target):
    book_ids = set()
    for link in Contributor.objects.filter(author=source):
        book_ids.add(link.book_id)
        if Contributor.objects.filter(book_id=link.book_id, author=target,
                                      role=link.role).exists():
            link.delete()
        else:
            Contributor.objects.filter(pk=link.pk).update(author=target)

    # Eski yozilish variant sifatida saqlanadi — qidiruv uni ham topadi
    variants = list(target.name_variants or [])
    for name in [source.full_name, *(source.name_variants or [])]:
        if name and name != target.full_name and name not in variants:
            variants.append(name)
    target.name_variants = variants
    for field in ('birth_year', 'death_year', 'nationality', 'bio', 'photo'):
        if not getattr(target, field) and getattr(source, field):
            setattr(target, field, getattr(source, field))
    target.save()
    source.delete()
    _reindex(book_ids)


@transaction.atomic
def merge_genres(source, target):
    book_ids = list(Book.objects.filter(category=source).values_list('pk', flat=True))
    Book.objects.filter(pk__in=book_ids).update(category=target)
    source.delete()
    _reindex(book_ids)


@transaction.atomic
def merge_publishers(source, target):
    book_ids = list(Book.objects.filter(publisher=source).values_list('pk', flat=True))
    Book.objects.filter(pk__in=book_ids).update(publisher=target)
    Series.objects.filter(publisher=source).update(publisher=target)
    source.delete()
    _reindex(book_ids)


@transaction.atomic
def merge_series(source, target):
    book_ids = list(Book.objects.filter(series=source).values_list('pk', flat=True))
    Book.objects.filter(pk__in=book_ids).update(series=target)
    source.delete()
    _reindex(book_ids)


@transaction.atomic
def merge_subjects(source, target):
    books = list(Book.objects.filter(subjects=source))
    for book in books:
        book.subjects.add(target)
        book.subjects.remove(source)
    Subject.objects.filter(parent=source).exclude(pk=target.pk).update(parent=target)
    if target.parent_id == source.pk:
        Subject.objects.filter(pk=target.pk).update(parent=source.parent_id)
    source.delete()
    Subject.objects.filter(pk=target.pk).update(
        books_count=Book.objects.filter(subjects=target).count())


# --------------------------------------------------------------------------
#  Ma'lumotnomalar
# --------------------------------------------------------------------------

AUTHORS = Resource(
    name='authors', single='author', model=Author, form_class=forms.PanelAuthorForm,
    title="Mualliflar", label="muallif", icon='feather',
    subtitle="Bir muallif ikki xil yozilgan bo'lsa — birlashtiring, eski yozilishi ham qidiriladi.",
    columns=(
        Column("Ism va familiya", lambda a: a.full_name),
        Column("Yillari", lambda a: a.life_years),
        Column("Davlati", lambda a: a.nationality),
    ),
    search=('full_name', 'name_variants'), ordering=('full_name',),
    usage='contributor', usage_link=_books('author'), merge=merge_authors,
)

GENRES = Resource(
    name='genres', single='genre', model=Genre, form_class=forms.PanelGenreForm,
    title="Kataloglar", label="katalog", icon='folder',
    subtitle="O'chirib qo'yilgan katalogdagi kitoblar saytda ko'rinmaydi.",
    columns=(
        Column("Nomi", lambda g: g.name),
        Column("Tartib", lambda g: g.order, numeric=True),
    ),
    search=('name',), ordering=('order', 'name'),
    usage='book', usage_link=_books('category'), toggle='is_active', merge=merge_genres,
)

PUBLISHERS = Resource(
    name='publishers', single='publisher', model=Publisher, form_class=forms.PanelPublisherForm,
    title="Nashriyotlar", label="nashriyot", icon='building',
    columns=(
        Column("Nomi", lambda p: p.name),
        Column("Shahar", lambda p: p.city),
        Column("Veb-sayt", lambda p: p.website),
    ),
    search=('name', 'city'), ordering=('name',),
    usage='books', usage_link=_books('publisher'), merge=merge_publishers,
)

SERIES = Resource(
    name='series', single='series', model=Series, form_class=forms.PanelSeriesForm,
    title="Turkumlar", label="turkum", icon='layers',
    columns=(
        Column("Nomi", lambda s: s.name),
        Column("ISSN", lambda s: s.issn),
        Column("Nashriyot", lambda s: s.publisher.name if s.publisher_id else ''),
    ),
    search=('name', 'issn'), ordering=('name',),
    usage='books', usage_link=_books('series'), merge=merge_series,
)

SUBJECTS = Resource(
    name='subjects', single='subject', model=Subject, form_class=forms.PanelSubjectForm,
    title="Mavzular", label="mavzu", icon='bookmark',
    subtitle="Mavzu rubrikalari, kalit so'zlar va UDK/BBK bo'limlari.",
    columns=(
        Column("Nomi", lambda s: s.name),
        Column("Turi", lambda s: s.get_kind_display()),
        Column("Kod", lambda s: s.code),
        Column("Yuqori mavzu", lambda s: s.parent.name if s.parent_id else ''),
    ),
    search=('name', 'code'), ordering=('name',),
    usage='books', usage_link=_books('subject'), merge=merge_subjects,
)

CATEGORIES = Resource(
    name='categories', single='category', model=PatronCategory,
    form_class=forms.PanelCategoryForm,
    title="A'zo toifalari", label="toifa", icon='shield',
    subtitle="Ijara muddati, limit, uzaytirish va jarima qoidalari shu yerda belgilanadi.",
    columns=(
        Column("Toifa", lambda c: c.name),
        Column("Muddat (kun)", lambda c: c.default_loan_days, numeric=True),
        Column("Limit", lambda c: c.loan_limit, numeric=True),
        Column("Uzaytirish", lambda c: c.renewals_allowed, numeric=True),
        Column("Jarima / kun", lambda c: int(c.fine_per_day), numeric=True),
    ),
    search=('name', 'code'), ordering=('order', 'name'),
    usage='patrons', usage_label="A'zolar",
    usage_link=lambda c: f'/panel/members/?category={c.code}', toggle='is_active',
    view_perm=Perms.SETTINGS_MANAGE, edit_perm=Perms.SETTINGS_MANAGE,
    delete_perm=Perms.SETTINGS_MANAGE, audit_action='SETTINGS',
)

RESOURCES = (GENRES, AUTHORS, PUBLISHERS, SERIES, SUBJECTS, CATEGORIES)
