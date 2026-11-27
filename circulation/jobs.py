"""
Sirkulyatsiya davriy vazifalari.

Ilgari bularning hammasi bitta `circulation_tick` buyrug'ida edi. Endi uchta mustaqil
vazifa: har biri alohida jurnalga yoziladi (`audit.JobRun`), alohida ishga tushirilishi
va monitoring qilinishi mumkin.

    python manage.py run_jobs --schedule daily
    python manage.py run_jobs fines_accrual
"""
import logging
from datetime import timedelta

from django.utils.timezone import now

from book_app.models import Rental
from core.jobs import job
from notifications.models import Notification
from notifications.services import notify

from .models import Fine, LibrarySettings, Reservation

logger = logging.getLogger('circulation')


@job('due_soon_notices', "Ertaga muddati tugaydigan ijaralar uchun ogohlantirish", schedule='daily')
def due_soon_notices():
    tomorrow = now().date() + timedelta(days=1)
    sent = 0
    for rental in (Rental.objects
                   .filter(return_date__isnull=True, due_date=tomorrow)
                   .select_related('student__user', 'copy__book')):
        notify(rental.student.user, "Qaytarish muddati yaqin",
               f"«{rental.copy.book.title}» kitobini ertaga ({rental.due_date}) qaytaring.",
               type=Notification.Type.DUE_SOON, link='/circulation/my-rentals/')
        sent += 1
    return {'notices': sent}


@job('fines_accrual', "Muddati o'tgan ijaralarga jarima hisoblaydi", schedule='daily')
def fines_accrual():
    settings_obj = LibrarySettings.load()
    today = now().date()
    touched = created_count = 0

    overdue = (Rental.objects
               .filter(return_date__isnull=True, due_date__lt=today)
               .select_related('student__user', 'copy__book'))

    for rental in overdue:
        days = (today - rental.due_date).days
        amount = days * settings_obj.fine_per_day
        fine, created = Fine.objects.get_or_create(
            rental=rental,
            defaults={'student': rental.student, 'days_overdue': days, 'amount': amount},
        )
        if not created and not fine.is_paid:
            fine.days_overdue = days
            fine.amount = amount
            fine.save(update_fields=['days_overdue', 'amount'])
        if created:
            created_count += 1
            notify(rental.student.user, "Qaytarish muddati o'tdi",
                   f"«{rental.copy.book.title}» muddati o'tgan." +
                   (f" Jarima: {amount} so'm." if amount else ""),
                   type=Notification.Type.OVERDUE, link='/circulation/my-rentals/')
        touched += 1

    return {'overdue': touched, 'new_fines': created_count}


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
               .first())
        if nxt:
            nxt.status = Reservation.Status.AVAILABLE
            nxt.hold_until = now() + timedelta(days=settings_obj.reservation_hold_days)
            nxt.save(update_fields=['status', 'hold_until'])
            promoted += 1

    return {'expired': expired_count, 'promoted': promoted}
