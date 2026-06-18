"""
Davriy ijara vazifalari (cron orqali ishga tushiriladi):
  - muddati o'tgan ijaralarga jarima yaratish/yangilash
  - navbat ushlash muddati o'tganlarni keyingisiga o'tkazish

Ishga tushirish:  python manage.py circulation_tick
Cron (kuniga 1 marta tavsiya):  0 1 * * *  <venv>/bin/python manage.py circulation_tick
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from book_app.models import Rental
from circulation.models import Reservation, Fine, LibrarySettings
from notifications.services import notify
from notifications.models import Notification


class Command(BaseCommand):
    help = "Jarimalarni hisoblaydi va navbat ushlash muddatini tekshiradi."

    def handle(self, *args, **options):
        settings = LibrarySettings.load()
        today = now().date()

        # 0) Muddat yaqin (ertaga qaytarish) — bir kun oldin ogohlantirish
        soon_count = 0
        tomorrow = today + timedelta(days=1)
        for rental in (Rental.objects.filter(return_date__isnull=True, due_date=tomorrow)
                       .select_related('student__user', 'copy__book')):
            notify(rental.student.user, "Qaytarish muddati yaqin",
                   f"«{rental.copy.book.title}» kitobini ertaga ({rental.due_date}) qaytaring.",
                   type=Notification.Type.DUE_SOON, link='/circulation/my-rentals/')
            soon_count += 1

        # 1) Muddati o'tgan ijaralar -> jarima
        fines_touched = 0
        overdue = (Rental.objects
                   .filter(return_date__isnull=True, due_date__lt=today)
                   .select_related('student__user', 'copy__book'))
        for rental in overdue:
            days = (today - rental.due_date).days
            amount = days * settings.fine_per_day
            fine, created = Fine.objects.get_or_create(
                rental=rental,
                defaults={'student': rental.student, 'days_overdue': days, 'amount': amount},
            )
            if not created and not fine.is_paid:
                fine.days_overdue = days
                fine.amount = amount
                fine.save(update_fields=['days_overdue', 'amount'])
            if created:
                notify(rental.student.user, "Qaytarish muddati o'tdi",
                       f"«{rental.copy.book.title}» muddati o'tgan." +
                       (f" Jarima: {amount} so'm." if amount else ""),
                       type=Notification.Type.OVERDUE, link='/circulation/my-rentals/')
            fines_touched += 1

        # 2) Navbat ushlash muddati o'tganlar -> EXPIRED, keyingisini ko'taramiz
        expired_count = 0
        expired = Reservation.objects.filter(
            status=Reservation.Status.AVAILABLE,
            hold_until__lt=now(),
        ).select_related('book')
        for res in expired:
            res.status = Reservation.Status.EXPIRED
            res.save(update_fields=['status'])
            expired_count += 1

            nxt = (Reservation.objects
                   .filter(book=res.book, status=Reservation.Status.WAITING)
                   .order_by('created_at')
                   .first())
            if nxt:
                nxt.status = Reservation.Status.AVAILABLE
                nxt.hold_until = now() + timedelta(days=settings.reservation_hold_days)
                nxt.save(update_fields=['status', 'hold_until'])

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {soon_count} ta muddat-yaqin, {fines_touched} ta jarima, "
            f"{expired_count} ta navbat muddati o'tdi."
        ))
