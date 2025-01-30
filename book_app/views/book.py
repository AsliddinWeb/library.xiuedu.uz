from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from django.core.paginator import Paginator
from django.db.models import Q

from ..utils import is_book_borrowed_by_student

from ..models import Book, Genre

def is_student(user):
    return user.is_authenticated and user.user_type == "STUDENT"

@login_required
def student_book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)

    book_rental = is_book_borrowed_by_student(request.user.student_profile, book)

    context = {
        'book': book,
        'book_rental': book_rental
    }
    return render(request, "book_app/book/detail.html", context)


@login_required
def student_book_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    language = request.GET.get('language', '')

    books = Book.objects.select_related('category').prefetch_related('authors').all()

    if query:
        books = books.filter(Q(title__icontains=query) | Q(authors__full_name__icontains=query)).distinct()

    if category_id:
        books = books.filter(category_id=category_id)

    # if language:
    #     books = books.filter(language=language)

    categories = Genre.objects.all()

    page_number = request.GET.get('page', 1)
    paginator = Paginator(books, 12)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'category_id': category_id,
        'language': language,
        'categories': categories,
    }
    return render(request, "book_app/book/book_list.html", context)
