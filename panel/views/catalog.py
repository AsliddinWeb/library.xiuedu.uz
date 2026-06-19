from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from book_app.models import Author, Genre
from user_app.utils import library_admin_role_required

from ..forms import PanelAuthorForm, PanelGenreForm

# ======================================================== Kataloglar (Genre)

@library_admin_role_required
def genre_list(request):
    genres = Genre.objects.annotate(books=Count('book')).order_by('order', 'name')
    q = request.GET.get('q', '').strip()
    if q:
        genres = genres.filter(name__icontains=q)
    ctx = {'active': 'genres', 'page_title': 'Kataloglar', 'genres': genres, 'q': q}
    if getattr(request, 'htmx', False):
        return render(request, 'panel/genres/_table.html', ctx)
    return render(request, 'panel/genres/list.html', ctx)


@library_admin_role_required
def genre_create(request):
    form = PanelGenreForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Katalog qo'shildi.")
        return redirect('panel:genres')
    return render(request, 'panel/genres/form.html',
                  {'form': form, 'active': 'genres', 'page_title': 'Yangi katalog'})


@library_admin_role_required
def genre_edit(request, pk):
    genre = get_object_or_404(Genre, pk=pk)
    form = PanelGenreForm(request.POST or None, instance=genre)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Saqlandi.")
        return redirect('panel:genres')
    return render(request, 'panel/genres/form.html',
                  {'form': form, 'genre': genre, 'active': 'genres', 'page_title': 'Katalogni tahrirlash'})


@require_POST
@library_admin_role_required
def genre_toggle(request, pk):
    genre = get_object_or_404(Genre, pk=pk)
    genre.is_active = not genre.is_active
    genre.save(update_fields=['is_active'])
    genres = Genre.objects.annotate(books=Count('book')).order_by('order', 'name')
    return render(request, 'panel/genres/_table.html',
                  {'genres': genres, 'q': ''})


@library_admin_role_required
def genre_delete(request, pk):
    genre = get_object_or_404(Genre, pk=pk)
    if request.method == 'POST':
        try:
            genre.delete()
            messages.success(request, "Katalog o'chirildi.")
        except ProtectedError:
            messages.error(request, "Katalogda kitoblar bor — avval ularni ko'chiring.")
        return redirect('panel:genres')
    return render(request, 'panel/genres/delete.html',
                  {'genre': genre, 'active': 'genres', 'page_title': "Katalogni o'chirish",
                   'book_count': genre.book_count()})


# ======================================================== Mualliflar (Author)

@library_admin_role_required
def author_list(request):
    authors = Author.objects.annotate(books=Count('book')).order_by('full_name')
    q = request.GET.get('q', '').strip()
    if q:
        authors = authors.filter(full_name__icontains=q)
    ctx = {'active': 'authors', 'page_title': 'Mualliflar', 'authors': authors, 'q': q}
    if getattr(request, 'htmx', False):
        return render(request, 'panel/authors/_table.html', ctx)
    return render(request, 'panel/authors/list.html', ctx)


@library_admin_role_required
def author_create(request):
    form = PanelAuthorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Muallif qo'shildi.")
        return redirect('panel:authors')
    return render(request, 'panel/authors/form.html',
                  {'form': form, 'active': 'authors', 'page_title': 'Yangi muallif'})


@library_admin_role_required
def author_edit(request, pk):
    author = get_object_or_404(Author, pk=pk)
    form = PanelAuthorForm(request.POST or None, instance=author)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Saqlandi.")
        return redirect('panel:authors')
    return render(request, 'panel/authors/form.html',
                  {'form': form, 'author': author, 'active': 'authors', 'page_title': 'Muallifni tahrirlash'})


@library_admin_role_required
def author_delete(request, pk):
    author = get_object_or_404(Author, pk=pk)
    if request.method == 'POST':
        author.delete()
        messages.success(request, "Muallif o'chirildi.")
        return redirect('panel:authors')
    return render(request, 'panel/authors/delete.html',
                  {'author': author, 'active': 'authors', 'page_title': "Muallifni o'chirish"})
