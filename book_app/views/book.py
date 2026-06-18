from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from ..models import Book, Genre


@login_required
def student_book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related('category').prefetch_related('authors'),
        pk=pk,
    )

    from circulation.services import book_action_context
    from engagement.services import engagement_context
    student_profile = getattr(request.user, 'student_profile', None)
    context = book_action_context(student_profile, book)
    context.update(engagement_context(request.user, book))
    return render(request, "book_app/book/detail.html", context)


@login_required
def student_book_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')

    books = (
        Book.objects
        .select_related('category')
        .prefetch_related('authors')
        .filter(is_active=True, category__is_active=True)
    )

    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(authors__full_name__icontains=query)
        ).distinct()

    if category_id:
        books = books.filter(category_id=category_id)

    paginator = Paginator(books, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'query': query,
        'category_id': category_id,
        'categories': Genre.objects.filter(is_active=True),
    }

    # HTMX so'rovida faqat grid qismini qaytaramiz (to'liq sahifa qayta yuklanmaydi)
    if getattr(request, 'htmx', False):
        return render(request, "book_app/book/partials/_book_grid.html", context)
    return render(request, "book_app/book/book_list.html", context)
