"""
Sirkulyatsiya (ijara) biznes mantig'i — view'lar yupqa, mantiq shu yerda.

P1-B dan boshlab qarz oluvchi — **`Patron`** (kutubxona a'zosi), ya'ni talaba ham,
xodim/o'qituvchi ham, tashqi o'quvchi ham. Eski `student` (StudentProfile) maydoni
yozuvlarda vaqtincha to'ldirilib boriladi (eski hisobotlar uchun) va P3'da
`Loan` modeliga ko'chishda olib tashlanadi.

Muddat va limitlar a'zo TOIFASIDAN olinadi (`PatronCategory`); toifada qiymat
berilmagan bo'lsa — umumiy `LibrarySettings` zaxira sifatida ishlatiladi.
"""

from django.db import transaction
from django.utils.timezone import now

from book_app.models import Item, Rental

from .models import Fine, LibrarySettings, RentalRequest, Reservation

# --- Yordamchilar ---------------------------------------------------------


def student_of(patron):
    """A'zoga bog'langan StudentProfile (bo'lsa) — eski maydonni to'ldirish uchun."""
    if patron is None or not patron.user_id:
        return None
    return getattr(patron.user, 'student_profile', None)


def notify_patron(patron, title, message, **kwargs):
    """A'zoga bildirishnoma (HEMIS'siz a'zoda foydalanuvchi bo'lmasligi mumkin)."""
    if patron is None or not patron.user_id:
        return
    from notifications.services import notify
    notify(patron.user, title, message, **kwargs)


def loan_days_for(patron):
    settings = LibrarySettings.load()
    if patron is not None and patron.category.default_loan_days:
        return patron.category.default_loan_days
    return settings.rental_days


def loan_limit_for(patron):
    settings = LibrarySettings.load()
    if patron is not None and patron.category.loan_limit:
        return patron.category.loan_limit
    return settings.max_active_rentals


def fine_rate_for(patron):
    """Kuniga jarima: avval a'zo toifasidan, bo'lmasa umumiy sozlamadan."""
    if patron is not None and patron.category.fine_per_day:
        return patron.category.fine_per_day
    return LibrarySettings.load().fine_per_day


def hold_limit_for(patron):
    if patron is not None and patron.category.hold_limit:
        return patron.category.hold_limit
    return 0


# --- So'rovlar (queries) --------------------------------------------------

def available_copies(book):
    """Hozir ijaraga berilishi mumkin bo'lgan nusxalar soni."""
    return Item.objects.filter(book=book, status=Item.Status.AVAILABLE).count()


def patron_active_rental(patron, book):
    return (Rental.objects
            .filter(patron=patron, copy__book=book, return_date__isnull=True)
            .first())


def patron_pending_request(patron, book):
    return (RentalRequest.objects
            .filter(patron=patron, book=book, status=RentalRequest.Status.PENDING)
            .first())


def patron_reservation(patron, book):
    return (Reservation.objects
            .filter(patron=patron, book=book,
                    status__in=[Reservation.Status.WAITING, Reservation.Status.AVAILABLE])
            .first())


def active_loans_count(patron):
    return Rental.objects.filter(patron=patron, return_date__isnull=True).count()


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


def book_action_context(patron, book):
    """Kitob sahifasidagi amallar uchun a'zoning shu kitobga nisbatan holati."""
    reservation = patron_reservation(patron, book) if patron else None
    can_borrow, borrow_block_reason = (patron.can_borrow() if patron else (False, ""))
    return {
        'book': book,
        'patron': patron,
        # Shablonlarda eski nom ham ishlatiladi — ikkalasi bir xil ma'noda
        'is_student': patron is not None,
        'can_borrow': can_borrow,
        'borrow_block_reason': borrow_block_reason,
        'avail': available_copies(book),
        'active_rental': patron_active_rental(patron, book) if patron else None,
        'pending_request': patron_pending_request(patron, book) if patron else None,
        'reservation': reservation,
        'reservation_pos': reservation_position(reservation) if reservation else None,
    }


# --- A'zo amallari --------------------------------------------------------

def create_rental_request(patron, book):
    if patron is None:
        return None, "Kutubxona a'zoligi topilmadi."

    allowed, reason = patron.can_borrow()
    if not allowed:
        return None, reason

    if patron_pending_request(patron, book):
        return None, "Bu kitobga so'rovingiz allaqachon yuborilgan."
    if patron_active_rental(patron, book):
        return None, "Bu kitob hozir sizda ijarada."
    if available_copies(book) == 0:
        return None, "Mavjud nusxa yo'q — navbatga yozilishingiz mumkin."

    limit = loan_limit_for(patron)
    if limit and active_loans_count(patron) >= limit:
        return None, f"Bir vaqtda {limit} tadan ortiq kitob olib bo'lmaydi."

    req = RentalRequest.objects.create(patron=patron, student=student_of(patron), book=book)
    return req, "So'rov yuborildi. Kutubxonachi tasdiqlashini kuting."


def cancel_rental_request(patron, book):
    req = patron_pending_request(patron, book)
    if not req:
        return False, "Bekor qilinadigan so'rov topilmadi."
    req.status = RentalRequest.Status.CANCELLED
    req.decided_at = now()
    req.save(update_fields=['status', 'decided_at'])
    return True, "So'rov bekor qilindi."


def create_reservation(patron, book):
    if patron is None:
        return None, "Kutubxona a'zoligi topilmadi."

    allowed, reason = patron.can_borrow()
    if not allowed:
        return None, reason

    if patron_reservation(patron, book):
        return None, "Siz allaqachon navbatdasiz."
    if patron_active_rental(patron, book):
        return None, "Bu kitob hozir sizda ijarada."

    limit = hold_limit_for(patron)
    if limit:
        active = Reservation.objects.filter(
            patron=patron,
            status__in=[Reservation.Status.WAITING, Reservation.Status.AVAILABLE]).count()
        if active >= limit:
            return None, f"Bir vaqtda {limit} tadan ortiq navbatga yozilib bo'lmaydi."

    res = Reservation.objects.create(patron=patron, student=student_of(patron), book=book)
    return res, "Navbatga yozildingiz. Kitob bo'shaganda xabar olasiz."


def cancel_reservation(patron, book):
    res = patron_reservation(patron, book)
    if not res:
        return False, "Bekor qilinadigan navbat topilmadi."
    res.status = Reservation.Status.CANCELLED
    res.save(update_fields=['status'])
    return True, "Navbat bekor qilindi."


# --- Kutubxonachi amallari ------------------------------------------------

@transaction.atomic
def approve_request(req, librarian=None):
    """So'rovni tasdiqlaydi: bo'sh nusxa biriktiradi va ijara yaratadi.

    Berish qoidalari (blok, qarz, limit, navbat) deskdagi bilan bir xil —
    `loans.checkout` ichida tekshiriladi.
    """
    from .loans import checkout

    if req.status != RentalRequest.Status.PENDING:
        return None, "Bu so'rov allaqachon hal qilingan."

    if req.patron is None and req.student_id:
        from user_app.services import get_or_create_patron
        req.patron = get_or_create_patron(req.student.user)
        if req.patron:
            req.save(update_fields=['patron'])
    if req.patron is None:
        return None, "Kutubxona a'zoligi topilmadi."

    free = Item.objects.filter(book=req.book, status=Item.Status.AVAILABLE).order_by('pk')
    copy = free.exclude(item_type__is_loanable=False).first() or free.first()
    if copy is None:
        return None, "Mavjud nusxa yo'q. Tasdiqlab bo'lmaydi."

    result = checkout(req.patron, copy, librarian, request=req)
    if not result.ok:
        return None, result.message
    return result.rental, "So'rov tasdiqlandi."


def reject_request(req, librarian=None, note=""):
    if req.status != RentalRequest.Status.PENDING:
        return False, "Bu so'rov allaqachon hal qilingan."
    req.status = RentalRequest.Status.REJECTED
    req.note = note
    req.decided_at = now()
    req.decided_by = librarian
    req.save(update_fields=['status', 'note', 'decided_at', 'decided_by'])

    from notifications.models import Notification
    notify_patron(req.patron, "So'rovingiz rad etildi",
                  f"«{req.book.title}» so'rovi rad etildi." + (f" Sabab: {note}" if note else ""),
                  type=Notification.Type.REQUEST_REJECTED, link=f'/books/{req.book_id}/')
    return True, "So'rov rad etildi."


def return_rental(rental, librarian=None):
    """Ijarani qaytarish (batafsil natija kerak bo'lsa — `loans.checkin`)."""
    from .loans import checkin

    result = checkin(rental, librarian)
    return result.ok, result.message


def mark_fine_paid(fine, librarian=None):
    if fine.is_paid:
        return False, "Bu jarima allaqachon to'langan."
    fine.is_paid = True
    fine.paid_at = now()
    fine.save(update_fields=['is_paid', 'paid_at'])
    recalc_patron_counters(fine.patron)

    from audit.models import ActionLog
    from audit.services import log_action
    log_action(ActionLog.Action.PAYMENT, obj=fine, actor=librarian,
               note=f"{fine.borrower_name} — {fine.amount:.0f} so'm")
    return True, "Jarima to'langan deb belgilandi."


# --- Hisoblagichlar -------------------------------------------------------

def recalc_patron_counters(patron):
    """A'zo kartasidagi denormalizatsiya maydonlarini qayta hisoblaydi."""
    if patron is None:
        return

    today = now().date()
    active = Rental.objects.filter(patron=patron, return_date__isnull=True)
    overdue = active.filter(due_date__lt=today).count()
    debt = sum(
        (fine.amount for fine in Fine.objects.filter(patron=patron, is_paid=False)),
        start=0,
    )

    patron.active_loans_count = active.count()
    patron.overdue_count = overdue
    patron.balance = debt
    patron.save(update_fields=['active_loans_count', 'overdue_count', 'balance', 'updated_at'])
