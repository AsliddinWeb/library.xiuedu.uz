"""
Desk uchun qidiruv: skaner o'qigan kod yoki qo'lda yozilgan matn bo'yicha
a'zo va nusxani topadi.

**Aniq** moslik (bilet raqami, HEMIS ID, shtrix-kod, inventar raqami) bilan amal
darrov bajarilishi mumkin; matnli qidiruv natijasi esa doim xodimga ko'rsatiladi —
taxminiy moslik bo'yicha kitob berib yubormaslik uchun.
"""
from django.db.models import Case, IntegerField, Q, Value, When

from book_app.models import Book, Item
from book_app.search import search_books
from user_app.models import Patron

PATRON_LIMIT = 8
BOOK_LIMIT = 8
ITEM_LIMIT = 20


def _patrons():
    return Patron.objects.select_related('user', 'category', 'user__student_profile',
                                         'user__employe_profile')


def exact_patrons(code):
    """Bilet raqami yoki HEMIS/login identifikatori to'liq mos kelgan a'zolar."""
    code = (code or '').strip()
    if not code:
        return []
    by_card = list(_patrons().filter(card_number__iexact=code))
    if by_card:
        return by_card
    return list(_patrons().filter(
        Q(user__username__iexact=code) | Q(user__hemis_uuid__iexact=code)
        | Q(user__university_id__iexact=code))[:PATRON_LIMIT])


def search_patrons(query):
    """Ism, familiya, bilet, telefon yoki guruh bo'yicha — har so'z mos kelishi shart."""
    words = (query or '').split()
    if not words or len(''.join(words)) < 2:
        return []
    patrons = _patrons()
    for word in words:
        patrons = patrons.filter(
            Q(full_name__icontains=word) | Q(card_number__icontains=word)
            | Q(phone__icontains=word) | Q(user__username__icontains=word)
            | Q(user__first_name__icontains=word) | Q(user__second_name__icontains=word)
            | Q(user__student_profile__group__icontains=word))
    return list(patrons.order_by('user__second_name', 'full_name')[:PATRON_LIMIT])


def _items():
    return Item.objects.select_related('book', 'item_type', 'library', 'shelf_location')


def exact_items(code):
    """Shtrix-kod (yagona) yoki inventar raqami bo'yicha nusxalar."""
    code = (code or '').strip()
    if not code:
        return []
    by_barcode = list(_items().filter(barcode__iexact=code))
    if by_barcode:
        return by_barcode
    return list(_items().filter(inventory_number__iexact=code)
                .order_by('book__title', 'pk')[:ITEM_LIMIT])


def matching_books(query):
    if len((query or '').strip()) < 2:
        return []
    return list(search_books(Book.objects.all(), query)[:BOOK_LIMIT])


def items_of(books):
    """Berilgan kitoblarning nusxalari — bo'shlari oldinda."""
    free_first = Case(When(status=Item.Status.AVAILABLE, then=Value(0)),
                      default=Value(1), output_field=IntegerField())
    return list(_items().filter(book__in=[book.pk for book in books])
                .order_by(free_first, 'book__title', 'inventory_number')[:ITEM_LIMIT])
