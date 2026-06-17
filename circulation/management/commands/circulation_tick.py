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


class Command(BaseCommand):
    help = "Jarimalarni hisoblaydi va navbat ushlash muddatini tekshiradi."

    def handle(self, *args, **options):
        settings = LibrarySettings.load()
        today = now().date()

        # 1) Muddati o'tgan ijaralar -> jarima
        fines_touched = 0
        overdue = (Rental.objects
                   .filter(return_date__isnull=True, due_date__lt=today)
                   .select_related('student'))
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
            f"Tayyor: {fines_touched} ta jarima, {expired_count} ta navbat muddati o'tdi."
        ))
