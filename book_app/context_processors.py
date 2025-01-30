from .models import Genre, Book

def book_processor(request):
    categories = Genre.objects.all()
    all_books = Book.objects.select_related('category').prefetch_related('authors').all()


    return {
        'categories': categories,
        'all_books': all_books,
    }
