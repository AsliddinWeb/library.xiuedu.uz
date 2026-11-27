from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from ..models import Book, Item


@login_required
def student_book_detail(request, pk):
    """Kitob sahifasi (OPAC): amallar, nusxalar, tavsif, o'xshash kitoblar."""
    book = get_object_or_404(
        Book.objects
        .select_related('category', 'publisher', 'series')
        .prefetch_related('authors', 'subjects', 'contributor_set__author'),
        pk=pk,
    )

    from circulation.services import book_action_context
    from engagement.services import engagement_context

    from ..citation import gost

    # Ijara/navbat amallari kutubxona a'zoligi (Patron) bo'yicha — talaba ham, xodim ham
    patron = None
    if request.user.is_authenticated:
        from user_app.services import get_or_create_patron
        patron = get_or_create_patron(request.user)

    context = book_action_context(patron, book)
    context.update(engagement_context(request.user, book))

    # Nusxalar: o'quvchi qaysi javondan olishini bilishi kerak
    context['items'] = (book.item_set
                        .select_related('item_type', 'library', 'shelf_location')
                        .exclude(status=Item.Status.WITHDRAWN)
                        .order_by('library__name', 'inventory_number'))

    # O'xshash kitoblar: avval mavzu bo'yicha, yetmasa katalog bo'yicha
    subject_ids = list(book.subjects.values_list('id', flat=True))
    similar = Book.objects.none()
    if subject_ids:
        similar = (Book.objects
                   .filter(subjects__id__in=subject_ids, is_active=True)
                   .exclude(pk=book.pk).distinct())
    if similar.count() < 6:
        similar = (Book.objects
                   .filter(category=book.category, is_active=True)
                   .exclude(pk=book.pk))
    context['similar'] = (similar
                          .select_related('category').prefetch_related('authors')
                          .order_by('-rating_count', '-view_count')[:6])

    context['citation'] = gost(book)
    return render(request, "opac/book_detail.html", context)


# Katalog ro'yxati P5 da OPAC qidiruviga ko'chdi — `catalog_opac.py` ga qarang.
# Eski nom (`student_book_list`) URL'larda ishlatilgani uchun saqlanadi.
from .catalog_opac import catalog as student_book_list  # noqa: E402,F401
