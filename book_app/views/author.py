from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages

from user_app.utils import library_admin_role_required
from ..models import Author
from ..forms import AuthorForm


@library_admin_role_required
def authors_list(request):
    authors = Author.objects.all()

    create_form = AuthorForm(request.POST)

    success_message = request.GET.get('successMessage', '')

    ctx = {
        # Menu active
        'sidebarAdditional': True,
        'sidebarAdditionalAuthors': True,

        # Main
        'authors': authors,
        'create_form': create_form,
        'successMessage': success_message,  # successMessage ni contextga qo'shish
    }

    return render(request, 'book_app/author/list.html', ctx)


@library_admin_role_required
def author_create(request):
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        bio = request.POST.get('bio')

        if full_name:
            # Muallifni qo'shish
            Author.objects.create(full_name=full_name, bio=bio)
            success_message = "Muallif muvaffaqiyatli qo'shildi."
            # URL parametrlarini qo'shish
            return redirect(reverse('book_app:authors_list') + f"?successMessage={success_message}")

        else:
            success_message = "Ism Familiya maydoni to'ldirilishi shart."
            return redirect(reverse('book_app:authors_list') + f"?successMessage={success_message}")

    return redirect('book_app:authors_list')

@library_admin_role_required
def author_edit(request, author_id):
    author = get_object_or_404(Author, id=author_id)

    if request.method == "POST":
        author.full_name = request.POST.get('full_name')
        author.bio = request.POST.get('bio')
        author.save()
        messages.success(request, "Muallif muvaffaqiyatli tahrirlandi.")
        return redirect('book_app:authors_list')

    return render(request, 'book_app/author/edit.html', {'author': author})


@library_admin_role_required
def author_delete(request, author_id):
    author = get_object_or_404(Author, id=author_id)

    if request.method == "POST":
        author.delete()
        messages.success(request, "Muallif muvaffaqiyatli o'chirildi.")
        return redirect('book_app:authors_list')

    return render(request, 'book_app/author/delete.html', {'author': author})
