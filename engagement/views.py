from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from book_app.models import Book
from reading.models import ReadingHistory
from user_app.utils import library_admin_role_required

from . import services
from .models import Favorite, Review

# ----------------------------------------------------------- partial render

def _render_reviews(request, book, message=None):
    ctx = services.engagement_context(request.user, book)
    ctx['book'] = book
    ctx['review_message'] = message
    return render(request, 'engagement/partials/_reviews.html', ctx)


def _render_favorite(request, book):
    return render(request, 'engagement/partials/_favorite_button.html', {
        'book': book,
        'is_favorite': services.is_favorite(request.user, book),
    })


# ----------------------------------------------------------- talaba amallari

@require_POST
@login_required
def toggle_favorite(request, pk):
    book = get_object_or_404(Book, pk=pk)
    services.toggle_favorite(request.user, book)
    return _render_favorite(request, book)


@require_POST
@login_required
def submit_review(request, pk):
    book = get_object_or_404(Book, pk=pk)
    _, msg = services.submit_review(request.user, book,
                                    request.POST.get('rating'), request.POST.get('text'))
    return _render_reviews(request, book, message=msg)


@login_required
def my_library(request):
    favorites = (Favorite.objects.filter(user=request.user)
                 .select_related('book__category').prefetch_related('book__authors'))
    history = (ReadingHistory.objects.filter(user=request.user)
               .select_related('book')[:24])
    my_reviews = (Review.objects.filter(user=request.user).select_related('book'))
    return render(request, 'engagement/my_library.html', {
        'favorites': favorites,
        'history': history,
        'my_reviews': my_reviews,
    })


# ----------------------------------------------------------- moderatsiya

def _render_moderation(request, message=None):
    pending = Review.objects.filter(is_approved=False).select_related('user', 'book')
    return render(request, 'engagement/partials/_moderation_panel.html', {
        'pending_reviews': pending,
        'mod_message': message,
    })


@library_admin_role_required
def moderate(request):
    # Eski sahifa — endi kutubxonachi paneli (/panel/reviews/) bilan almashtirildi
    return redirect('panel:reviews')


@require_POST
@library_admin_role_required
def approve_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    services.approve_review(review)
    return _render_moderation(request, "Sharh tasdiqlandi.")


@require_POST
@library_admin_role_required
def reject_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    services.reject_review(review)
    return _render_moderation(request, "Sharh rad etildi.")
