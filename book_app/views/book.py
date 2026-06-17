from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from django.core.paginator import Paginator
from django.db.models import Q

from ..utils import is_book_borrowed_by_student

from ..models import Book, Genre


@login_required
def student_book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related('category').prefetch_related('authors'),
        pk=pk,
    )

    book_rental = None
    student_profile = getattr(request.user, 'student_profile', None)
    if student_profile is not None:
        book_rental = is_book_borrowed_by_student(student_profile, book)

    context = {
        'book': book,
        'book_rental': book_rental,
    }
    return render(request, "book_app/book/detail.html", context)


@login_required
def student_book_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')

    books = (
        Book.objects
        .select_related('category')
        .prefetch_related('authors')
        .filter(category__is_active=True)
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
