"""
Excel'da tayyorlangan ro'yxatdan (CSV) kitob import qilish.

Ikki bosqich: avval fayl o'qilib har qator tekshiriladi (ko'rib chiqish), keyin
kutubxonachi tasdiqlasa bazaga yoziladi. Xato qatorlar tashlab ketiladi —
fayldagi bitta xato butun importni to'xtatmaydi.
"""
import csv
import io
import re

from django.db import transaction
from django.utils.text import slugify
from django.utils.timezone import now

from book_app.models import Author, Book, Genre, Publisher
from book_app.services import create_items

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
MAX_COPIES = 100

#: ustun kaliti -> (shablondagi nom, qabul qilinadigan boshqa nomlar)
COLUMNS = {
    'title': ("Sarlavha", ('nomi', 'kitob nomi', 'title')),
    'authors': ("Mualliflar", ('muallif', 'authors', 'author')),
    'category': ("Katalog", ("bo'lim", 'category')),
    'publisher': ("Nashriyot", ('publisher',)),
    'year': ("Yil", ('nashr yili', 'year')),
    'isbn': ("ISBN", ()),
    'udc': ("UDK", ('udc',)),
    'language': ("Til", ('language',)),
    'pages': ("Sahifa", ('betlar', 'pages')),
    'copies': ("Nusxa soni", ('nusxa', 'soni', 'copies')),
    'price': ("Narx", ('narxi', 'price')),
    'description': ("Tavsif", ('izoh', 'description')),
}
EXAMPLE = ["O'tkan kunlar", "Abdulla Qodiriy", "Badiiy adabiyot", "Sharq", "2019",
           "9789943000001", "821.512.133", "O'zbekcha", "384", "3", "45000", "Roman"]


class ImportProblem(Exception):
    """Faylni umuman o'qib bo'lmaydi."""


def template_header():
    return [label for label, _ in COLUMNS.values()]


def _normal(text):
    return re.sub(r'\s+', ' ', (text or '').replace('’', "'").replace('ʻ', "'")
                  .strip().lower())


def _decode(raw):
    for encoding in ('utf-8-sig', 'cp1251'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportProblem("Fayl kodlanishi tushunarsiz. Excel'da «CSV UTF-8» ko'rinishida saqlang.")


def _read_table(upload):
    if upload.size > MAX_BYTES:
        raise ImportProblem("Fayl 2 MB dan katta. Uni bo'laklarga ajrating.")
    raw = upload.read()
    if raw[:2] == b'PK':
        raise ImportProblem("Bu Excel (.xlsx) fayli. «Boshqacha saqlash» orqali CSV qiling.")
    text = _decode(raw)
    if not text.strip():
        raise ImportProblem("Fayl bo'sh.")
    first = text.splitlines()[0]
    delimiter = max((';', ',', '\t'), key=first.count)
    try:
        return list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error as error:
        raise ImportProblem(f"CSV o'qilmadi: {error}") from error


def _column_map(header):
    names = {}
    for key, (label, aliases) in COLUMNS.items():
        for name in (label, *aliases):
            names[_normal(name)] = key
    found = {}
    for index, cell in enumerate(header):
        key = names.get(_normal(cell))
        if key and key not in found:
            found[key] = index
    missing = [COLUMNS[key][0] for key in ('title', 'category') if key not in found]
    if missing:
        raise ImportProblem("Birinchi qatorda majburiy ustun yo'q: " + ', '.join(missing))
    return found


def _integer(value, *, low, high):
    value = value.replace(' ', '')
    if not value:
        return None, True
    if not value.isdigit() or not low <= int(value) <= high:
        return None, False
    return int(value), True


def _check_row(data):
    """Qatorni tozalaydi va xatolar ro'yxatini qaytaradi."""
    errors = []
    row = {key: ' '.join(data.get(key, '').split()) for key in COLUMNS}
    row['description'] = data.get('description', '').strip()

    for key, limit in (('title', 500), ('category', 100), ('publisher', 200),
                       ('udc', 40), ('language', 50)):
        if len(row[key]) > limit:
            errors.append(f"{COLUMNS[key][0]} {limit} belgidan uzun")
    if not row['title']:
        errors.append("Sarlavha bo'sh")
    if not row['category']:
        errors.append("Katalog bo'sh")

    row['authors'] = [name.strip() for name in re.split(r'[;|,]', row['authors']) if name.strip()]
    if any(len(name) > 200 for name in row['authors']):
        errors.append("Muallif ismi juda uzun")

    for key, low, high in (('year', 1000, now().year + 1), ('pages', 1, 100000),
                           ('copies', 0, MAX_COPIES)):
        row[key], ok = _integer(row[key], low=low, high=high)
        if not ok:
            errors.append(f"{COLUMNS[key][0]} noto'g'ri ({low}–{high})")

    price = row['price'].replace(' ', '').replace(',', '.')
    if price and not re.fullmatch(r'\d{1,9}(\.\d{1,2})?', price):
        errors.append("Narx noto'g'ri")
        price = ''
    row['price'] = price

    isbn = row['isbn'].replace('-', '').replace(' ', '').upper()
    if isbn and not re.fullmatch(r'\d{13}|\d{9}[\dX]', isbn):
        errors.append("ISBN 10 yoki 13 belgidan iborat bo'lishi kerak")
    row['isbn'] = isbn
    return row, errors


def find_existing(row):
    """Shu kitob katalogda bormi: ISBN yoki sarlavha + yil + birinchi muallif."""
    if row['isbn']:
        book = Book.objects.filter(isbn=row['isbn']).first()
        if book:
            return book
    books = Book.objects.filter(title__iexact=row['title'], published_year=row['year'])
    if row['authors']:
        books = books.filter(authors__full_name__iexact=row['authors'][0])
    return books.first()


def parse(upload):
    """Faylni o'qiydi. Qaytaradi: qatorlar ro'yxati (sessiyaga yozsa bo'ladigan dict)."""
    table = _read_table(upload)
    columns = _column_map(table[0])
    body = [(number, cells) for number, cells in enumerate(table[1:], start=2)
            if any(cell.strip() for cell in cells)]
    if not body:
        raise ImportProblem("Faylda sarlavha qatoridan boshqa ma'lumot yo'q.")
    if len(body) > MAX_ROWS:
        raise ImportProblem(f"Bir faylda {MAX_ROWS} tadan ortiq qator bo'lmasin.")

    rows, seen = [], set()
    for number, cells in body:
        data = {key: cells[index] if index < len(cells) else ''
                for key, index in columns.items()}
        row, errors = _check_row(data)
        key = row['isbn'] or (_normal(row['title']), row['year'],
                              _normal(row['authors'][0]) if row['authors'] else '')
        if not errors and key in seen:
            errors.append("Faylda takrorlangan qator")
        seen.add(key)

        existing = None if errors else find_existing(row)
        row.update(line=number, errors=errors, existing=existing.pk if existing else None)
        rows.append(row)
    return rows


def _named(model, field, value):
    return (model.objects.filter(**{f'{field}__iexact': value}).first()
            or model.objects.create(**{field: value}))


@transaction.atomic
def apply(rows, *, user, add_copies_to_existing=False, with_items=True):
    """Tasdiqlangan qatorlarni yozadi. Qaytaradi: hisob lug'ati."""
    summary = {'books': 0, 'copies': 0, 'skipped': 0}
    for row in rows:
        if row['errors']:
            summary['skipped'] += 1
            continue
        copies = (row['copies'] or 0) if with_items else 0
        existing = find_existing(row)
        if existing:
            if add_copies_to_existing and copies:
                summary['copies'] += len(create_items(
                    existing, copies, price=row['price'] or 0, created_by=user))
            else:
                summary['skipped'] += 1
            continue

        book = Book.objects.create(
            title=row['title'],
            category=_named(Genre, 'name', row['category']),
            publisher=_named(Publisher, 'name', row['publisher']) if row['publisher'] else None,
            published_year=row['year'],
            isbn=row['isbn'],
            udc=row['udc'],
            language=row['language'] or Book._meta.get_field('language').get_default(),
            page_count=row['pages'],
            description=row['description'],
            reading_mode=Book.ReadingMode.PHYSICAL,
        )
        if row['authors']:
            book.authors.set([_named(Author, 'full_name', name) for name in row['authors']])
        book.slug = f"{slugify(book.title)[:280] or 'kitob'}-{book.pk}"
        book.save()
        summary['books'] += 1
        if copies:
            summary['copies'] += len(create_items(
                book, copies, price=row['price'] or 0, created_by=user))
    return summary
