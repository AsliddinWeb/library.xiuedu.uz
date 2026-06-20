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
    # Faqat talabalar ijara/navbat amallarini ko'radi (rolga asoslangan)
    student_profile = None
    if request.user.user_type == 'STUDENT':
        student_profile = getattr(request.user, 'student_profile', None)
    context = book_action_context(student_profile, book)
    context.update(engagement_context(request.user, book))
    return render(request, "book_app/book/detail.html", context)


SORTS = {
    '-id': 'Yangi qo\'shilgan',
    '-rating_count': 'Ommabop',
    '-view_count': 'Ko\'p o\'qilgan',
    'title': 'Nom (A-Z)',
}


@login_required
def student_book_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    digital = request.GET.get('digital', '')
    sort = request.GET.get('sort', '-id')

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
    if digital == '1':
        books = books.filter(Q(electronic_version__gt='') | Q(audio_version__gt=''))

    books = books.order_by(sort if sort in SORTS else '-id')

    page_obj = Paginator(books, 18).get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'query': query,
        'category_id': category_id,
        'digital': digital,
        'sort': sort,
        'sorts': SORTS,
        'total': page_obj.paginator.count,
        'categories': Genre.objects.filter(is_active=True),
    }

    if getattr(request, 'htmx', False):
        return render(request, "book_app/book/partials/_book_grid.html", context)
    return render(request, "book_app/book/book_list.html", context)
