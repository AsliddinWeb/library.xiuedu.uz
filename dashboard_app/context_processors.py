def librarian(request):
    """Kutubxonachi panel sidebar'i uchun jonli badge sonlari (LibraryAdmin/Admin)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    from user_app.roles import Roles, effective_role
    if effective_role(user) not in (Roles.LIBRARIAN, Roles.ADMIN):
        return {}

    from book_app.models import Rental
    from circulation.models import Fine, RentalRequest, Reservation
    from engagement.models import Review
    return {
        'lib_stats': {
            'pending_requests': RentalRequest.objects.filter(
                status=RentalRequest.Status.PENDING).count(),
            'pending_reviews': Review.objects.filter(is_approved=False).count(),
            'active_rentals': Rental.objects.filter(return_date__isnull=True).count(),
            'reservations': Reservation.objects.filter(
                status=Reservation.Status.WAITING).count(),
            'unpaid_fines': Fine.objects.filter(is_paid=False).count(),
        }
    }
