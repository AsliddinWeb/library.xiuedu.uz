from django.shortcuts import render
from django.contrib.auth.decorators import login_required

def is_student(user):
    return user.is_authenticated and user.user_type == "STUDENT"

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