from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect

from book_app.models import Book, Rental, Genre
from user_app.models import User

# Student requirements
from django.db.models import Count
from django.utils.timezone import now
from datetime import timedelta

def home(request):
    return render(request, "home.html")

@login_required(login_url="/auth/student-login")
def dashboard(request):
    user = request.user

    if user.is_authenticated:
        if user.is_superuser:
            return redirect('/admin')

        if user.user_type == "STUDENT":
            all_books = Book.objects.all()

            # Popular books
            popular_books = (
                Book.objects.annotate(rental_count=Count('copy__rental'))
                .order_by('-rental_count')[:15]
            )

            # Recent books
            one_month_ago = now() - timedelta(days=30)
            recent_books = Book.objects.filter(created_at__gte=one_month_ago).order_by('-created_at')[:12]

            rental_books = Rental.objects.all()
            all_users = User.objects.all()

            ctx = {
                'all_books': all_books,
                'popular_books': popular_books,
                'recent_books': recent_books,

                'rental_books': rental_books,
                'all_users': all_users,
            }
            return render(request, "dashboard/student.html", ctx)
        else:
            if user.employe_profile.current_role.name == 'Admin':
                return redirect('/admin')

            elif user.employe_profile.current_role.name == 'LibraryAdmin':

                return render(request, 'dashboard/library_admin.html')

            elif user.employe_profile.current_role.name == 'Employee':

                return render(request, 'dashboard/employee.html')
            else:
                return JsonResponse({'error': 'No valid role assigned.'}, status=403)
    else:
        return redirect('student_login')
