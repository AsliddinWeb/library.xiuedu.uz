"""
Sirkulyatsiya davriy vazifalari.

Har biri mustaqil: alohida ishga tushadi va `audit.JobRun`ga yoziladi.

    python manage.py run_jobs --schedule daily
    python manage.py run_jobs fines_accrual
"""
import logging
from datetime import timedelta

from django.utils.timezone import now

from book_app.models import Rental
from core.jobs import job
from notifications.models import Notification

from .models import Fine, LibrarySettings, Reservation
from .services import notify_patron, recalc_patron_counters, student_of

logger = logging.getLogger('circulation')


def _fine_rate(patron):
    """Kuniga jarima: avval a'zo toifasidan, bo'lmasa umumiy sozlamadan."""
    if patron is not None and patron.category.fine_per_day:
        return patron.category.fine_per_day
    return LibrarySettings.load().fine_per_day


@job('due_soon_notices', "Ertaga muddati tugaydigan ijaralar uchun ogohlantirish", schedule='daily')
def due_soon_notices():
    tomorrow = now().date() + timedelta(days=1)
    sent = 0
    for rental in (Rental.objects
                   .filter(return_date__isnull=True, due_date=tomorrow)
                   .select_related('patron__user', 'copy__book')):
        notify_patron(rental.patron, "Qaytarish muddati yaqin",
                      f"«{rental.copy.book.title}» kitobini ertaga ({rental.due_date}) qaytaring.",
                      type=Notification.Type.DUE_SOON, link='/circulation/my-rentals/')
        sent += 1
    return {'notices': sent}


@job('fines_accrual', "Muddati o'tgan ijaralarga jarima hisoblaydi", schedule='daily')
def fines_accrual():
    today = now().date()
    touched = created_count = 0
    patrons = set()

    overdue = (Rental.objects
               .filter(return_date__isnull=True, due_date__lt=today)
               .select_related('patron__category', 'patron__user', 'copy__book'))

    for rental in overdue:
        days = (today - rental.due_date).days
        amount = days * _fine_rate(rental.patron)

        fine, created = Fine.objects.get_or_create(
            rental=rental,
            defaults={
                'patron': rental.patron,
                'student': rental.student or student_of(rental.patron),
                'days_overdue': days,
                'amount': amount,
            },
        )
        if not created and not fine.is_paid:
            fine.days_overdue = days
            fine.amount = amount
            if fine.patron_id is None and rental.patron_id:
                fine.patron = rental.patron
                fine.save(update_fields=['days_overdue', 'amount', 'patron'])
            else:
                fine.save(update_fields=['days_overdue', 'amount'])

        if created:
            created_count += 1
            notify_patron(rental.patron, "Qaytarish muddati o'tdi",
                          f"«{rental.copy.book.title}» muddati o'tgan." +
                          (f" Jarima: {amount} so'm." if amount else ""),
                          type=Notification.Type.OVERDUE, link='/circulation/my-rentals/')

        touched += 1
        if rental.patron_id:
            patrons.add(rental.patron)

    # A'zo kartasidagi "kechikkanlar" va "qarz" ko'rsatkichlari yangilanadi
    for patron in patrons:
        recalc_patron_counters(patron)

    return {'overdue': touched, 'new_fines': created_count, 'patrons': len(patrons)}


@job('reservation_expiry', "Ushlash muddati o'tgan navbatlarni keyingisiga o'tkazadi",
     schedule='daily')
def reservation_expiry():
    settings_obj = LibrarySettings.load()
    expired_count = promoted = 0

    expired = (Reservation.objects
               .filter(status=Reservation.Status.AVAILABLE, hold_until__lt=now())
               .select_related('book'))

    for reservation in expired:
        reservation.status = Reservation.Status.EXPIRED
        reservation.save(update_fields=['status'])
        expired_count += 1

        nxt = (Reservation.objects
               .filter(book=reservation.book, status=Reservation.Status.WAITING)
               .order_by('created_at')
               .select_related('patron__user')
               .first())
        if nxt:
            nxt.status = Reservation.Status.AVAILABLE
            nxt.hold_until = now() + timedelta(days=settings_obj.reservation_hold_days)
            nxt.save(update_fields=['status', 'hold_until'])
            promoted += 1

            notify_patron(nxt.patron, "Navbatdagi kitob bo'shadi",
                          f"«{nxt.book.title}» bo'shadi — "
                          f"{settings_obj.reservation_hold_days} kun ichida ijaraga so'rang.",
                          type=Notification.Type.RESERVATION_AVAILABLE,
                          link=f'/books/{nxt.book_id}/')

    return {'expired': expired_count, 'promoted': promoted}
