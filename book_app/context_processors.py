from .models import Genre, Book


def book_processor(request):
    """Sidebar/nav uchun yengil kontekst.

    Diqqat: bu har bir requestda ishlaydi — shuning uchun BARCHA kitob
    obyektlarini yuklamaymiz. Faqat kataloglar (kichik, lazy) va kitoblar
    soni (arzon COUNT) beriladi.
    """
    return {
        'categories': Genre.objects.all(),
        'books_count': Book.objects.count(),
    }
