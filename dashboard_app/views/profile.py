from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from book_app.models import Rental
from engagement.models import Favorite, Review
from reading.models import ReadingHistory
from user_app.roles import is_library_staff
from user_app.services import get_or_create_patron


@login_required
def profile(request):
    if is_library_staff(request.user):
        return redirect('panel:profile')
    student = getattr(request.user, 'student_profile', None)
    # Talaba ham, xodim ham a'zo — ko'rsatkichlar ikkalasi uchun
    stats = {
        'rentals': Rental.objects.filter(patron__user=request.user).count(),
        'favorites': Favorite.objects.filter(user=request.user).count(),
        'reviews': Review.objects.filter(user=request.user).count(),
        'reads': ReadingHistory.objects.filter(user=request.user).count(),
    }
    return render(request, 'student/profile.html', {
        'student': student,
        'stats': stats,
        'patron': get_or_create_patron(request.user),
    })
