"""
Sirkulyatsiya (ijara) biznes mantig'i — view'lar yupqa, mantiq shu yerda.

P1-B dan boshlab qarz oluvchi — **`Patron`** (kutubxona a'zosi), ya'ni talaba ham,
xodim/o'qituvchi ham, tashqi o'quvchi ham. Eski `student` (StudentProfile) maydoni
yozuvlarda vaqtincha to'ldirilib boriladi (eski hisobotlar uchun) va P3'da
`Loan` modeliga ko'chishda olib tashlanadi.

Muddat va limitlar a'zo TOIFASIDAN olinadi (`PatronCategory`); toifada qiymat
berilmagan bo'lsa — umumiy `LibrarySettings` zaxira sifatida ishlatiladi.
"""
from datetime import timedelta

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
    """So'rovni tasdiqlaydi: bo'sh nusxa biriktiradi va ijara yaratadi."""
    if req.status != RentalRequest.Status.PENDING:
        return None, "Bu so'rov allaqachon hal qilingan."

    copy = (Item.objects
            .select_for_update()
            .filter(book=req.book, status=Item.Status.AVAILABLE)
            .first())
    if copy is None:
        return None, "Mavjud nusxa yo'q. Tasdiqlab bo'lmaydi."

    today = now().date()
    rental = Rental.objects.create(
        copy=copy,
        patron=req.patron,
        student=req.student or student_of(req.patron),
        library_admin_checked=True,
        borrowed_date=today,
        due_date=today + timedelta(days=loan_days_for(req.patron)),
    )
    # Nusxa holati yagona joydan o'zgaradi: jurnal + audit + ko'rsatkichlar
    from book_app.services import change_item_status
    change_item_status(copy, Item.Status.ON_LOAN,
                       reason=f"Ijaraga berildi — {rental.borrower_name}", by=librarian)

    req.status = RentalRequest.Status.APPROVED
    req.rental = rental
    req.decided_at = now()
    req.decided_by = librarian
    req.save(update_fields=['status', 'rental', 'decided_at', 'decided_by'])

    recalc_patron_counters(req.patron)

    from notifications.models import Notification
    notify_patron(req.patron, "So'rovingiz tasdiqlandi",
                  f"«{req.book.title}» — kutubxonadan olishingiz mumkin. "
                  f"Qaytarish: {rental.due_date}.",
                  type=Notification.Type.REQUEST_APPROVED, link='/circulation/my-rentals/')

    from audit.models import ActionLog
    from audit.services import log_action
    log_action(ActionLog.Action.CHECKOUT, obj=rental,
               note=f"{req.book.title} — {rental.borrower_name}")
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
    notify_patron(req.patron, "So'rovingiz rad etildi",
                  f"«{req.book.title}» so'rovi rad etildi." + (f" Sabab: {note}" if note else ""),
                  type=Notification.Type.REQUEST_REJECTED, link=f'/books/{req.book_id}/')
    return True, "So'rov rad etildi."


@transaction.atomic
def return_rental(rental):
    """Ijarani qaytarish: nusxani bo'shatadi va navbatdagi 1-a'zoga ushlab turadi."""
    if rental.return_date is not None:
        return False, "Bu ijara allaqachon qaytarilgan."

    rental.return_date = now().date()
    rental.save(update_fields=['return_date'])

    copy = rental.copy
    from book_app.services import change_item_status
    change_item_status(copy, Item.Status.AVAILABLE,
                       reason=f"Qaytarildi — {rental.borrower_name}")
    copy.loan_count = (copy.loan_count or 0) + 1
    copy.save(update_fields=['loan_count'])

    recalc_patron_counters(rental.patron)

    # Navbatdagi 1-a'zoga kitobni ushlab turamiz
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
        notify_patron(nxt.patron, "Navbatdagi kitob bo'shadi",
                      f"«{copy.book.title}» bo'shadi — {settings.reservation_hold_days} kun "
                      f"ichida ijaraga so'rang.",
                      type=Notification.Type.RESERVATION_AVAILABLE,
                      link=f'/books/{copy.book_id}/')

    from audit.models import ActionLog
    from audit.services import log_action
    log_action(ActionLog.Action.CHECKIN, obj=rental,
               note=f"{copy.book.title} — {rental.borrower_name}")
    return True, "Kitob qaytarildi."


def mark_fine_paid(fine):
    if fine.is_paid:
        return False, "Bu jarima allaqachon to'langan."
    fine.is_paid = True
    fine.paid_at = now()
    fine.save(update_fields=['is_paid', 'paid_at'])
    recalc_patron_counters(fine.patron)

    from audit.models import ActionLog
    from audit.services import log_action
    log_action(ActionLog.Action.PAYMENT, obj=fine,
               note=f"{fine.borrower_name} — {fine.amount} so'm")
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
