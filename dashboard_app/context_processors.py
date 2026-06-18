def librarian(request):
    """Kutubxonachi sidebar'i uchun jonli badge sonlari (faqat LibraryAdmin/Admin)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    from user_app.roles import Roles, effective_role
    if effective_role(user) not in (Roles.LIBRARIAN, Roles.ADMIN):
        return {}

    from circulation.models import RentalRequest
    from engagement.models import Review
    return {
        'lib_stats': {
            'pending_requests': RentalRequest.objects.filter(
                status=RentalRequest.Status.PENDING).count(),
            'pending_reviews': Review.objects.filter(is_approved=False).count(),
        }
    }
