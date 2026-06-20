from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from book_app.models import Rental
from engagement.models import Favorite, Review
from reading.models import ReadingHistory


@login_required
def profile(request):
    student = getattr(request.user, 'student_profile', None)
    stats = {}
    if student is not None:
        stats = {
            'rentals': Rental.objects.filter(student=student).count(),
            'favorites': Favorite.objects.filter(user=request.user).count(),
            'reviews': Review.objects.filter(user=request.user).count(),
            'reads': ReadingHistory.objects.filter(user=request.user).count(),
        }
    return render(request, 'student/profile.html', {'student': student, 'stats': stats})
