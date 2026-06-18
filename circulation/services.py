"""
Ijara (circulation) biznes mantig'i — view'lar yupqa, mantiq shu yerda.
"""
from datetime import timedelta

from django.db import transaction
from django.utils.timezone import now

from book_app.models import Copy, Rental

from .models import LibrarySettings, RentalRequest, Reservation

# --- So'rovlar (queries) ---

def available_copies(book):
    return Copy.objects.filter(book=book, is_available=True).count()


def student_active_rental(student, book):
    return (Rental.objects
            .filter(student=student, copy__book=book, return_date__isnull=True)
            .first())


def student_pending_request(student, book):
    return (RentalRequest.objects
            .filter(student=student, book=book, status=RentalRequest.Status.PENDING)
            .first())


def student_reservation(student, book):
    return (Reservation.objects
            .filter(student=student, book=book,
                    status__in=[Reservation.Status.WAITING, Reservation.Status.AVAILABLE])
            .first())


def reservation_position(reservation):
    """Navbatdagi o'rin (1-dan boshlab)."""
    if reservation.status != Reservation.Status.WAITING:
        return None
    earlier = Reservation.objects.filter(
        book=reservation.book,
        status=Reservation.Status.WAITING,
        created_at__lt=reservation.created_at,
    ).count()
    return earlier + 1


def book_action_context(student, book):
    """Kitob detali/amallar uchun talabaning shu kitobga nisbatan holati."""
    reservation = student_reservation(student, book) if student else None
    return {
        'book': book,
        'avail': available_copies(book),
        'active_rental': student_active_rental(student, book) if student else None,
        'pending_request': student_pending_request(student, book) if student else None,
        'reservation': reservation,
        'reservation_pos': reservation_position(reservation) if reservation else None,
    }


# --- Amallar (actions) ---

def create_rental_request(student, book):
    if student_pending_request(student, book):
        return None, "Bu kitobga so'rovingiz allaqachon yuborilgan."
    if student_active_rental(student, book):
        return None, "Bu kitob hozir sizda ijarada."
    if available_copies(book) == 0:
        return None, "Mavjud nusxa yo'q — navbatga yozilishingiz mumkin."

    settings = LibrarySettings.load()
    active = Rental.objects.filter(student=student, return_date__isnull=True).count()
    if active >= settings.max_active_rentals:
        return None, f"Bir vaqtda {settings.max_active_rentals} tadan ortiq kitob olib bo'lmaydi."

    req = RentalRequest.objects.create(student=student, book=book)
    return req, "So'rov yuborildi. Kutubxonachi tasdiqlashini kuting."


def cancel_rental_request(student, book):
    req = student_pending_request(student, book)
    if not req:
        return False, "Bekor qilinadigan so'rov topilmadi."
    req.status = RentalRequest.Status.CANCELLED
    req.decided_at = now()
    req.save(update_fields=['status', 'decided_at'])
    return True, "So'rov bekor qilindi."


def create_reservation(student, book):
    if student_reservation(student, book):
        return None, "Siz allaqachon navbatdasiz."
    if student_active_rental(student, book):
        return None, "Bu kitob hozir sizda ijarada."
    res = Reservation.objects.create(student=student, book=book)
    return res, "Navbatga yozildingiz. Kitob bo'shaganda xabar olasiz."


def cancel_reservation(student, book):
    res = student_reservation(student, book)
    if not res:
        return False, "Bekor qilinadigan navbat topilmadi."
    res.status = Reservation.Status.CANCELLED
    res.save(update_fields=['status'])
    return True, "Navbat bekor qilindi."


# --- Kutubxonachi amallari ---

@transaction.atomic
def approve_request(req, librarian=None):
    """So'rovni tasdiqlaydi: bo'sh nusxa biriktiradi va Rental yaratadi."""
    if req.status != RentalRequest.Status.PENDING:
        return None, "Bu so'rov allaqachon hal qilingan."

    copy = (Copy.objects
            .select_for_update()
            .filter(book=req.book, is_available=True)
            .first())
    if copy is None:
        return None, "Mavjud nusxa yo'q. Tasdiqlab bo'lmaydi."

    settings = LibrarySettings.load()
    today = now().date()
    rental = Rental.objects.create(
        copy=copy,
        student=req.student,
        library_admin_checked=True,
        borrowed_date=today,
        due_date=today + timedelta(days=settings.rental_days),
    )
    copy.is_available = False
    copy.save(update_fields=['is_available'])

    req.status = RentalRequest.Status.APPROVED
    req.rental = rental
    req.decided_at = now()
    req.decided_by = librarian
    req.save(update_fields=['status', 'rental', 'decided_at', 'decided_by'])

    from notifications.models import Notification
    from notifications.services import notify
    notify(req.student.user, "So'rovingiz tasdiqlandi",
           f"«{req.book.title}» — kutubxonadan olishingiz mumkin. Qaytarish: {rental.due_date}.",
           type=Notification.Type.REQUEST_APPROVED, link='/circulation/my-rentals/')
    return rental, "So'rov tasdiqlandi."


def reject_request(req, librarian=None, note=""):
    if req.status != RentalRequest.Status.PENDING:
        return False, "Bu so'rov allaqachon hal qilingan."
    req.status = RentalRequest.Status.REJECTED
    req.note = note
    req.decided_at = now()
    req.decided_by = librarian
    req.save(update_fields=['status', 'note', 'decided_at', 'decided_by'])

    from notifications.models import Notification
    from notifications.services import notify
    notify(req.student.user, "So'rovingiz rad etildi",
           f"«{req.book.title}» so'rovi rad etildi." + (f" Sabab: {note}" if note else ""),
           type=Notification.Type.REQUEST_REJECTED, link=f'/books/{req.book_id}/')
    return True, "So'rov rad etildi."


@transaction.atomic
def return_rental(rental):
    """Ijarani qaytarish: nusxani bo'shatadi va navbatdagi 1-talabaga ushlab turadi."""
    if rental.return_date is not None:
        return False, "Bu ijara allaqachon qaytarilgan."

    today = now().date()
    rental.return_date = today
    rental.save(update_fields=['return_date'])

    copy = rental.copy
    copy.is_available = True
    copy.save(update_fields=['is_available'])

    # Navbatdagi 1-talabaga kitobni ushlab turamiz
    settings = LibrarySettings.load()
    nxt = (Reservation.objects
           .filter(book=copy.book, status=Reservation.Status.WAITING)
           .order_by('created_at')
           .first())
    if nxt:
        nxt.status = Reservation.Status.AVAILABLE
        nxt.hold_until = now() + timedelta(days=settings.reservation_hold_days)
        nxt.save(update_fields=['status', 'hold_until'])

        from notifications.models import Notification
        from notifications.services import notify
        notify(nxt.student.user, "Navbatdagi kitob bo'shadi",
               f"«{copy.book.title}» bo'shadi — {settings.reservation_hold_days} kun ichida ijaraga so'rang.",
               type=Notification.Type.RESERVATION_AVAILABLE, link=f'/books/{copy.book_id}/')

    return True, "Kitob qaytarildi."


def mark_fine_paid(fine):
    if fine.is_paid:
        return False, "Bu jarima allaqachon to'langan."
    fine.is_paid = True
    fine.paid_at = now()
    fine.save(update_fields=['is_paid', 'paid_at'])
    return True, "Jarima to'langan deb belgilandi."
