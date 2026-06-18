"""Engagement (sharh/reyting/sevimli) biznes mantig'i."""
from django.db.models import Avg, Count

from .models import Review, Favorite


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

        from notifications.services import notify
        from notifications.models import Notification
        notify(review.user, "Sharhingiz tasdiqlandi",
               f"«{review.book.title}» kitobiga qoldirgan sharhingiz e'lon qilindi.",
               type=Notification.Type.REVIEW_APPROVED, link=f'/books/{review.book_id}/')


def reject_review(review):
    book = review.book
    review.delete()
    recompute_rating(book)
