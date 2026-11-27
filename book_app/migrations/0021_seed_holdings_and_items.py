"""
P2 data-migratsiyasi: fond tuzilmasi seed qilinadi va mavjud nusxalar to'ldiriladi.

  1. Filial ("Asosiy fond") va 6 ta nusxa turi yaratiladi.
  2. Har bir mavjud nusxaga **shtrix-kod** beriladi (XIU + 9 raqam), filial va tur
     biriktiriladi, `status` eski `is_available` qiymatidan kelib chiqib qo'yiladi.
  3. Kitoblarning fond ko'rsatkichlari (`items_count`, `available_count`) hisoblanadi.
  4. Muallif nomlari qidiruv uchun normallashtiriladi.

Orqaga qaytarish: ma'lumot o'chirilmaydi (jadvallar sxema migratsiyasi bilan qaytadi).
"""
from django.db import migrations

ITEM_TYPES = [
    # (code, name, is_loanable, default_loan_days, order)
    ('DARSLIK', "Darslik", True, 0, 10),
    ('OQUV', "O'quv qo'llanma", True, 0, 20),
    ('BADIIY', "Badiiy adabiyot", True, 0, 30),
    ('ILMIY', "Ilmiy adabiyot", True, 0, 40),
    ('DAVRIY', "Davriy nashr", False, 0, 50),
    ('NODIR', "Nodir nashr", False, 0, 60),
]


def normalize(text):
    """Qidiruv uchun oddiy normalizatsiya: kichik harf + apostroflarni birxillashtirish."""
    if not text:
        return ''
    result = text.lower()
    for ch in ("'", "`", "ʼ", "’"):
        result = result.replace(ch, "'")
    return result.strip()


def seed(apps, schema_editor):
    Library = apps.get_model('holdings', 'Library')
    ItemType = apps.get_model('holdings', 'ItemType')
    ShelfLocation = apps.get_model('holdings', 'ShelfLocation')
    Item = apps.get_model('book_app', 'Item')
    Book = apps.get_model('book_app', 'Book')
    Author = apps.get_model('book_app', 'Author')

    # --- 1. Filial va javon ---
    library, _ = Library.objects.get_or_create(
        code='MAIN',
        defaults={'name': "Asosiy fond", 'kind': 'MAIN', 'order': 10},
    )
    shelf, _ = ShelfLocation.objects.get_or_create(
        library=library, code='UMUMIY',
        defaults={'name': "Belgilanmagan javon",
                  'navigation_hint': "Javon hali belgilanmagan"},
    )

    # --- 2. Nusxa turlari ---
    types = {}
    for code, name, loanable, days, order in ITEM_TYPES:
        item_type, _ = ItemType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'is_loanable': loanable,
                      'default_loan_days': days, 'order': order},
        )
        types[code] = item_type
    default_type = types['BADIIY']

    # --- 3. Mavjud nusxalar: shtrix-kod, filial, tur, holat ---
    counter = 0
    updated = []
    for item in Item.objects.select_related('book').order_by('id'):
        counter += 1
        if not item.barcode:
            item.barcode = f"XIU{counter:09d}"
        item.library_id = item.library_id or library.pk
        item.item_type_id = item.item_type_id or default_type.pk
        item.shelf_location_id = item.shelf_location_id or shelf.pk
        item.status = 'AVAILABLE' if item.is_available else 'ON_LOAN'
        if not item.acquired_on and item.book_id:
            created = getattr(item.book, 'created_at', None)
            item.acquired_on = created.date() if created else None
        updated.append(item)

    if updated:
        Item.objects.bulk_update(
            updated,
            ['barcode', 'library', 'item_type', 'shelf_location', 'status', 'acquired_on'],
        )
    print(f"  {len(updated)} ta nusxaga shtrix-kod va joylashuv berildi")

    # --- 4. Kitob ko'rsatkichlari ---
    books = []
    for book in Book.objects.all():
        items = Item.objects.filter(book=book)
        book.items_count = items.count()
        book.available_count = items.filter(status='AVAILABLE').count()
        book.search_text = normalize(book.title)
        books.append(book)
    if books:
        Book.objects.bulk_update(books, ['items_count', 'available_count', 'search_text'])
    print(f"  {len(books)} ta kitobning fond ko'rsatkichi hisoblandi")

    # --- 5. Muallif nomlari ---
    authors = []
    for author in Author.objects.all():
        author.normalized_name = normalize(author.full_name)
        authors.append(author)
    if authors:
        Author.objects.bulk_update(authors, ['normalized_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0020_contributor_itemstatuslog_publisher_series_subject_and_more'),
        ('holdings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
