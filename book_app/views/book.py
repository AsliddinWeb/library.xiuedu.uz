from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from ..models import Book


@login_required
def student_book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related('category').prefetch_related('authors'),
        pk=pk,
    )

    from circulation.services import book_action_context
    from engagement.services import engagement_context
    # Ijara/navbat amallari kutubxona a'zoligi (Patron) bo'yicha — talaba ham, xodim ham
    patron = None
    if request.user.is_authenticated:
        from user_app.services import get_or_create_patron
        patron = get_or_create_patron(request.user)
    context = book_action_context(patron, book)
    context.update(engagement_context(request.user, book))
    context['similar'] = (Book.objects
                          .filter(category=book.category, is_active=True)
                          .exclude(pk=book.pk)
                          .select_related('category').prefetch_related('authors')
                          .order_by('-rating_count', '-view_count')[:6])
    return render(request, "book_app/book/detail.html", context)


# Katalog ro'yxati P5 da OPAC qidiruviga ko'chdi — `catalog_opac.py` ga qarang.
# Eski nom (`student_book_list`) URL'larda ishlatilgani uchun saqlanadi.
from .catalog_opac import catalog as student_book_list  # noqa: E402,F401
