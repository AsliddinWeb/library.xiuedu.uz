"""Kunlik vazifalar qayta ishga tushganda zarar qilmasligi."""
from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now

from book_app.models import Item, Rental
from core.jobs import run_job
from core.testing import make_book
from notifications.models import Notification
from notifications.services import notify
from user_app.models import User
from user_app.services import get_or_create_patron

from .models import Fine, LibrarySettings, Reservation


class JobRepeatTests(TestCase):
    def setUp(self):
        self.book = make_book('Algoritmlar', copies=1)
        self.patron = get_or_create_patron(
            User.objects.create(username='s', user_type='STUDENT'))

    def _rental(self, due_in):
        today = now().date()
        return Rental.objects.create(
            copy=Item.objects.get(book=self.book), patron=self.patron,
            borrowed_date=today - timedelta(days=20),
            due_date=today + timedelta(days=due_in))

    def _set_rate(self, amount):
        library = LibrarySettings.load()
        library.fine_per_day = amount
        library.save()

    def _count(self, kind):
        return Notification.objects.filter(user=self.patron.user, type=kind).count()

    def test_due_soon_notice_is_sent_once(self):
        self._rental(due_in=1)

        first = run_job('due_soon_notices')
        second = run_job('due_soon_notices')

        self.assertEqual(self._count(Notification.Type.DUE_SOON), 1)
        self.assertEqual((first.stats['notices'], second.stats['notices']), (1, 0))

    def test_zero_rate_creates_no_fine_but_still_warns_once(self):
        self._set_rate(0)
        self._rental(due_in=-3)

        run_job('fines_accrual')
        run_job('fines_accrual')

        self.assertFalse(Fine.objects.exists())
        self.assertEqual(self._count(Notification.Type.OVERDUE), 1)

    def test_fine_grows_without_repeating_the_notice(self):
        self._set_rate(1000)
        rental = self._rental(due_in=-2)
        run_job('fines_accrual')
        Fine.objects.update(amount=0, days_overdue=0)

        run = run_job('fines_accrual')

        fine = Fine.objects.get(rental=rental)
        self.assertEqual((fine.days_overdue, fine.amount), (2, 2000))
        self.assertEqual(run.stats['new_fines'], 0)
        self.assertEqual(self._count(Notification.Type.OVERDUE), 1)

    def test_uncollected_hold_expires(self):
        hold = Reservation.objects.create(
            book=self.book, patron=self.patron, status=Reservation.Status.AVAILABLE,
            hold_until=now() - timedelta(hours=1))

        run_job('reservation_expiry')

        hold.refresh_from_db()
        self.assertEqual(hold.status, Reservation.Status.EXPIRED)


class LongTitleTests(TestCase):
    def test_long_text_is_truncated_instead_of_failing(self):
        user = User.objects.create(username='u', user_type='STUDENT')

        item = notify(user, 'T' * 500, 'M' * 900)

        item.refresh_from_db()
        self.assertEqual((len(item.title), len(item.message)), (200, 400))
