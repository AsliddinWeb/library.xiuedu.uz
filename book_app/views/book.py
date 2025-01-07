from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test

from ..utils import is_book_borrowed_by_student

from ..models import Book

def is_student(user):
    return user.is_authenticated and user.user_type == "STUDENT"

@login_required
# @user_passes_test(is_student, login_url="book_app:unauthorized")
def student_book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)

    book_rental = is_book_borrowed_by_student(request.user.student_profile, book)

    context = {
        'book': book,
        'book_rental': book_rental
    }
    return render(request, "book_app/book/detail.html", context)
