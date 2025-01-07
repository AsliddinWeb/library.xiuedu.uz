from .models import Genre

def book_processor(request):
    categories = Genre.objects.all()


    return {
        'categories': categories,
    }
