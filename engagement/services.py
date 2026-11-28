"""Engagement (sharh/reyting/sevimli/ro'yxat) biznes mantig'i."""
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Max
from django.utils.timezone import now

from user_app.permissions import Perms, has_perm
from user_app.services import is_teacher

from .models import Favorite, Review, Shelf, ShelfItem

#: Bitta foydalanuvchi ocha oladigan ro'yxatlar va bitta ro'yxatdagi kitoblar chegarasi
MAX_SHELVES_PER_USER = 50
MAX_ITEMS_PER_SHELF = 500


def recompute_rating(book):
    """Kitobning o'rtacha reytingini (faqat tasdiqlangan sharhlar) qayta hisoblaydi."""
    agg = (Review.objects
           .filter(book=book, is_approved=True)
           .aggregate(avg=Avg('rating'), count=Count('id')))
    book.avg_rating = round(agg['avg'] or 0, 2)
    book.rating_count = agg['count'] or 0
    book.save(update_fields=['avg_rating', 'rating_count'])


def is_favorite(user, book):
    return Favorite.objects.filter(user=user, book=book).exists()


def toggle_favorite(user, book):
    fav = Favorite.objects.filter(user=user, book=book).first()
    if fav:
        fav.delete()
        return False
    Favorite.objects.create(user=user, book=book)
    return True


def submit_review(user, book, rating, text):
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return None, "Bahoni tanlang."
    if not (1 <= rating <= 5):
        return None, "Baho 1 dan 5 gacha bo'lishi kerak."

    Review.objects.update_or_create(
        user=user, book=book,
        defaults={'rating': rating, 'text': (text or '').strip(), 'is_approved': False},
    )
    return True, "Sharhingiz qabul qilindi — moderatsiyadan keyin ko'rinadi."


def engagement_context(user, book):
    reviews = Review.objects.filter(book=book, is_approved=True).select_related('user')
    my_review = None
    fav = False
    if user is not None and user.is_authenticated:
        my_review = Review.objects.filter(user=user, book=book).first()
        fav = is_favorite(user, book)
    return {
        'reviews': reviews,
        'my_review': my_review,
        'is_favorite': fav,
    }


# --- Moderatsiya ---

def approve_review(review):
    if not review.is_approved:
        review.is_approved = True
        review.save(update_fields=['is_approved'])
        recompute_rating(review.book)

        from notifications.models import Notification
        from notifications.services import notify
        notify(review.user, "Sharhingiz tasdiqlandi",
               f"«{review.book.title}» kitobiga qoldirgan sharhingiz e'lon qilindi.",
               type=Notification.Type.REVIEW_APPROVED, link=f'/books/{review.book_id}/')


def reject_review(review):
    book = review.book
    review.delete()
    recompute_rating(book)


# =============================================================================
#  Ro'yxatlar (Shelf)
#
#  Qoida: har kim o'ziga SHAXSIY ro'yxat ochadi. Boshqalarga ko'rinadigan ro'yxatni
#  faqat o'qituvchi yoki kutubxonachi e'lon qila oladi (nazoratsiz ommaviy matn
#  chiqib ketmasin). "Kutubxona tanlovi" belgisi — faqat kutubxonachida.
# =============================================================================

def is_curator(user) -> bool:
    """Katalogni boshqaradigan xodim (har qanday ro'yxatni tahrirlay oladi)."""
    return has_perm(user, Perms.CATALOG_EDIT)


def can_publish_shelf(user) -> bool:
    return is_curator(user) or is_teacher(user)


def _is_library_employee(user) -> bool:
    """"Faqat xodimlarga" ro'yxatini ko'ra oladiganlar."""
    return user.user_type == user.UserType.EMPLOYE or is_curator(user)


def public_shelves(user):
    """Foydalanuvchiga ko'rinadigan e'lon qilingan ro'yxatlar (bo'shlari ham)."""
    visible = [Shelf.Visibility.PUBLIC]
    if user.is_authenticated and _is_library_employee(user):
        visible.append(Shelf.Visibility.STAFF)
    return (Shelf.objects.filter(visibility__in=visible)
            .select_related('owner')
            .annotate(books_count=Count('items')))


def can_view_shelf(user, shelf) -> bool:
    if shelf.visibility == Shelf.Visibility.PUBLIC:
        return True
    if not user.is_authenticated:
        return False
    if shelf.owner_id == user.pk:
        return True
    return shelf.visibility == Shelf.Visibility.STAFF and _is_library_employee(user)


def can_edit_shelf(user, shelf) -> bool:
    if not user.is_authenticated:
        return False
    if shelf.owner_id == user.pk:
        return True
    # Kutubxonachi faqat e'lon qilingan ro'yxatni tuzata oladi — shaxsiysi daxlsiz
    return shelf.visibility != Shelf.Visibility.PRIVATE and is_curator(user)


def create_shelf(user, name, **fields):
    """(ro'yxat | None, xabar)."""
    name = ' '.join((name or '').split())[:120]
    if not name:
        return None, "Ro'yxatga nom bering."
    if Shelf.objects.filter(owner=user).count() >= MAX_SHELVES_PER_USER:
        return None, f"Ro'yxatlar soni chegaraga yetdi ({MAX_SHELVES_PER_USER} ta)."
    if Shelf.objects.filter(owner=user, name__iexact=name).exists():
        return None, "Bunday nomli ro'yxatingiz bor."

    if not can_publish_shelf(user):
        fields['visibility'] = Shelf.Visibility.PRIVATE
    if not is_curator(user):
        fields['is_official'] = False

    try:
        with transaction.atomic():
            shelf = Shelf.objects.create(owner=user, name=name, **fields)
    except IntegrityError:  # ikki marta bosilgan tugma
        return None, "Bunday nomli ro'yxatingiz bor."
    return shelf, "Ro'yxat yaratildi."


def _touch(shelf):
    Shelf.objects.filter(pk=shelf.pk).update(updated_at=now())


def add_to_shelf(shelf, book):
    """(qo'shildimi, xabar)."""
    if shelf.items.filter(book=book).exists():
        return False, "Kitob ro'yxatda bor."
    if shelf.items.count() >= MAX_ITEMS_PER_SHELF:
        return False, f"Ro'yxat to'lgan ({MAX_ITEMS_PER_SHELF} ta)."
    last = shelf.items.aggregate(last=Max('order'))['last'] or 0
    _, created = ShelfItem.objects.get_or_create(
        shelf=shelf, book=book, defaults={'order': last + 1})
    _touch(shelf)
    return created, "Ro'yxatga qo'shildi."


def remove_from_shelf(shelf, book):
    deleted, _ = ShelfItem.objects.filter(shelf=shelf, book=book).delete()
    if deleted:
        _touch(shelf)
    return bool(deleted), "Ro'yxatdan olib tashlandi."


def toggle_shelf_item(shelf, book):
    """(hozir ro'yxatdami, xabar)."""
    if shelf.items.filter(book=book).exists():
        remove_from_shelf(shelf, book)
        return False, f"«{shelf.name}» ro'yxatidan olib tashlandi."
    added, message = add_to_shelf(shelf, book)
    if added:
        return True, f"«{shelf.name}» ro'yxatiga qo'shildi."
    return False, message


def shelves_with_book(user, book):
    """Foydalanuvchining ro'yxatlari + shu kitob ularda bormi (`has_book`)."""
    shelves = list(Shelf.objects.filter(owner=user)
                   .annotate(books_count=Count('items'))
                   .order_by('name'))
    containing = set(ShelfItem.objects.filter(shelf__owner=user, book=book)
                     .values_list('shelf_id', flat=True))
    for shelf in shelves:
        shelf.has_book = shelf.pk in containing
    return shelves
