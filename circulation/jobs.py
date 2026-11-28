"""
Sirkulyatsiya davriy vazifalari.

Har biri mustaqil: alohida ishga tushadi va `audit.JobRun`ga yoziladi.
Har biri qayta ishga tushsa ham xavfsiz — takroriy xabar yoki yozuv yaratmaydi.

    python manage.py run_jobs --schedule daily
    python manage.py run_jobs fines_accrual
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils.text import Truncator
from django.utils.timezone import now

from book_app.models import Rental
from core.jobs import job
from notifications.models import Notification

from .loans import MY_LOANS_LINK, promote_next_hold, settle_fine
from .models import Reservation
from .services import notify_patron, recalc_patron_counters

logger = logging.getLogger('circulation')


def _title(rental):
    """Bildirishnoma matniga sig'adigan kitob nomi."""
    return Truncator(rental.copy.book.title).chars(200)


def _notify_once(patron, title, message, *, type, key=None):
    """Xabar ilgari yuborilmagan bo'lsa yuboradi.

    `key` — takrorlikni aniqlaydigan matn boshi (berilmasa butun matn).
    """
    if patron is None or not patron.user_id:
        return False
    sent = Notification.objects.filter(user_id=patron.user_id, type=type)
    if sent.filter(message__startswith=key or message).exists():
        return False
    notify_patron(patron, title, message, type=type, link=MY_LOANS_LINK)
    return True


@job('due_soon_notices', "Ertaga muddati tugaydigan ijaralar uchun ogohlantirish", schedule='daily')
def due_soon_notices():
    tomorrow = now().date() + timedelta(days=1)
    sent = 0
    for rental in (Rental.objects
                   .filter(return_date__isnull=True, due_date=tomorrow)
                   .select_related('patron__user', 'copy__book')):
        message = f"«{_title(rental)}» kitobini ertaga ({tomorrow:%d.%m.%Y}) qaytaring."
        sent += _notify_once(rental.patron, "Qaytarish muddati yaqin", message,
                             type=Notification.Type.DUE_SOON)
    return {'notices': sent}


@job('fines_accrual', "Muddati o'tgan ijaralarga jarima hisoblaydi", schedule='daily')
def fines_accrual():
    today = now().date()
    overdue_ids = list(Rental.objects
                       .filter(return_date__isnull=True, due_date__lt=today)
                       .values_list('pk', flat=True))
    touched = created = notices = 0
    patrons = {}

    for pk in overdue_ids:
        # Xodim ayni damda qabul qilayotgan bo'lishi mumkin — qatorni qulflaymiz
        with transaction.atomic():
            rental = (Rental.objects.select_for_update(of=('self',))
                      .select_related('patron__category', 'patron__user', 'copy__book')
                      .filter(pk=pk, return_date__isnull=True, due_date__lt=today)
                      .first())
            if rental is None:
                continue

            had_fine = hasattr(rental, 'fine')
            # Qaytarishdagi bilan bitta qoida: stavka 0 bo'lsa yozuv yaratilmaydi
            fine = settle_fine(rental, today)
            if fine and not had_fine:
                created += 1

            key = f"«{_title(rental)}» — qaytarish muddati {rental.due_date:%d.%m.%Y} edi."
            message = f"{key} Kitobni kutubxonaga qaytaring."
            if fine and not fine.is_paid:
                message += " Kechikkan har bir kun uchun jarima hisoblanadi."
            notices += _notify_once(rental.patron, "Qaytarish muddati o'tdi", message,
                                    type=Notification.Type.OVERDUE, key=key)

            touched += 1
            if rental.patron_id:
                patrons[rental.patron_id] = rental.patron

    # A'zo kartasidagi "kechikkanlar" va "qarz" ko'rsatkichlari yangilanadi
    for patron in patrons.values():
        recalc_patron_counters(patron)

    return {'overdue': touched, 'new_fines': created, 'notices': notices,
            'patrons': len(patrons)}


@job('reservation_expiry', "Ushlash muddati o'tgan navbatlarni keyingisiga o'tkazadi",
     schedule='daily')
def reservation_expiry():
    expired_count = promoted = 0

    expired = (Reservation.objects
               .filter(status=Reservation.Status.AVAILABLE, hold_until__lt=now())
               .select_related('book'))

    for reservation in expired:
        # Yopish va keyingisini ko'tarish birga bajariladi yoki birga bekor bo'ladi
        with transaction.atomic():
            reservation.status = Reservation.Status.EXPIRED
            reservation.save(update_fields=['status'])
            expired_count += 1

            if promote_next_hold(reservation.book):
                promoted += 1

    return {'expired': expired_count, 'promoted': promoted}
