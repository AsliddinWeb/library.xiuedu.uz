"""
Unfold admin sidebar uchun counter (badge) funksiyalari.

Har bir funksiya `request` qabul qiladi va sidebar'da ko'rsatiladigan
son/qiymatni qaytaradi. Xatolik bo'lsa, admin buzilmasligi uchun bo'sh
qiymat qaytariladi.
"""


def _safe(fn):
    """Badge xatoligi admin panelini buzmasligi uchun himoya."""
    try:
        value = fn()
        return str(value) if value else ""
    except Exception:
        return ""


# --- Kutubxona ---

def book_count(request):
    from book_app.models import Book
    return _safe(lambda: Book.objects.count())


def author_count(request):
    from book_app.models import Author
    return _safe(lambda: Author.objects.count())


def genre_count(request):
    from book_app.models import Genre
    return _safe(lambda: Genre.objects.filter(is_active=True).count())


def available_copies(request):
    """Hozir mavjud (band bo'lmagan) nusxalar soni."""
    from book_app.models import Copy
    return _safe(lambda: Copy.objects.filter(is_available=True).count())


def active_rentals(request):
    """Hali qaytarilmagan (faol) ijaralar soni."""
    from book_app.models import Rental
    return _safe(lambda: Rental.objects.filter(return_date__isnull=True).count())


# --- Foydalanuvchilar ---

def user_count(request):
    from user_app.models import User
    return _safe(lambda: User.objects.count())


def student_count(request):
    from user_app.models import StudentProfile
    return _safe(lambda: StudentProfile.objects.count())


def employee_count(request):
    from user_app.models import EmployeProfile
    return _safe(lambda: EmployeProfile.objects.count())


# --- Ijara (circulation) ---

def pending_requests(request):
    """Kutilayotgan ijara so'rovlari."""
    from circulation.models import RentalRequest
    return _safe(lambda: RentalRequest.objects.filter(status=RentalRequest.Status.PENDING).count())


def waiting_reservations(request):
    """Navbatda turgan rezervatsiyalar."""
    from circulation.models import Reservation
    return _safe(lambda: Reservation.objects.filter(status=Reservation.Status.WAITING).count())


def unpaid_fines(request):
    """To'lanmagan jarimalar."""
    from circulation.models import Fine
    return _safe(lambda: Fine.objects.filter(is_paid=False).count())
