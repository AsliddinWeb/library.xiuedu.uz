"""Abonement qoidalari: berish, qabul qilish, uzaytirish, navbat."""
from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now

from audit.models import ActionLog
from book_app.models import Item, Rental
from core.testing import make_book, make_copies, make_librarian, make_student
from notifications.models import Notification
from user_app.models import Patron
from user_app.services import get_or_create_patron

from . import loans, services
from .models import Fine, LibrarySettings, RentalRequest, Reservation


class LoanFixture(TestCase):
    def setUp(self):
        self.librarian = make_librarian()
        self.patron = get_or_create_patron(make_student())
        self.other = get_or_create_patron(make_student())
        self.book = make_book("Fizika")
        self.item = make_copies(self.book, 1)[0]
        category = self.patron.category
        category.default_loan_days = 10
        category.loan_limit = 2
        category.renewals_allowed = 1
        category.fine_per_day = 500
        category.save()

    def lend(self, patron=None, item=None, **kwargs):
        return loans.checkout(patron or self.patron, item or self.item, self.librarian, **kwargs)

    def codes(self, result):
        return {block.code for block in result.blocks}

    def hold(self, patron, status=Reservation.Status.WAITING):
        return Reservation.objects.create(patron=patron, book=self.book, status=status)


class CheckoutTests(LoanFixture):
    def test_lends_free_copy(self):
        result = self.lend()

        self.assertTrue(result.ok, result.message)
        self.item.refresh_from_db()
        self.patron.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ON_LOAN)
        self.assertEqual(result.rental.due_date, now().date() + timedelta(days=10))
        self.assertEqual(self.patron.active_loans_count, 1)
        self.assertTrue(Notification.objects.filter(user=self.patron.user).exists())
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.CHECKOUT).exists())

    def test_custom_due_date_cannot_be_in_the_past(self):
        yesterday = now().date() - timedelta(days=1)
        self.assertFalse(self.lend(due_date=yesterday).ok)
        later = now().date() + timedelta(days=3)
        self.assertEqual(self.lend(due_date=later).rental.due_date, later)

    def test_blocked_patron_needs_override_with_reason(self):
        self.patron.status = Patron.Status.BLOCKED
        self.patron.save(update_fields=['status'])

        refused = self.lend()
        self.assertFalse(refused.ok)
        self.assertTrue(refused.can_override)
        self.assertFalse(self.lend(override=True, reason='  ').ok)
        self.assertFalse(Rental.objects.exists())

        self.assertTrue(self.lend(override=True, reason="Dekan ruxsati").ok)
        entry = ActionLog.objects.get(action=ActionLog.Action.OVERRIDE)
        self.assertIn("Dekan ruxsati", entry.note)

    def test_staff_account_can_never_borrow(self):
        staff = make_librarian()
        patron = Patron.objects.create(user=staff, card_number='XODIM-1',
                                       category=self.patron.category)

        result = self.lend(patron, override=True, reason="sinab ko'rish")

        self.assertFalse(result.ok)
        self.assertFalse(result.can_override)
        self.assertIn('staff', self.codes(result))

    def test_copy_in_someone_elses_hands(self):
        self.lend(self.other)
        result = self.lend(override=True, reason="x")
        self.assertFalse(result.ok)
        self.assertEqual(self.codes(result), {'on_loan'})

    def test_lost_copy_is_refused(self):
        self.item.status = Item.Status.LOST
        self.item.save()
        result = self.lend(override=True, reason="x")
        self.assertEqual(self.codes(result), {'unavailable'})

    def test_loan_limit_falls_back_to_library_settings(self):
        category = self.patron.category
        category.loan_limit = 0
        category.save()
        settings = LibrarySettings.load()
        settings.max_active_rentals = 1
        settings.save()
        self.lend()
        second = make_copies(make_book("Kimyo"), 1)[0]
        self.assertIn('limit', self.codes(self.lend(item=second)))

    def test_second_copy_of_same_book_warns(self):
        second = make_copies(self.book, 1)[0]
        self.lend()
        self.assertEqual(self.codes(self.lend(item=second)), {'same_book'})

    def test_reading_room_copy_stays_reading_room_after_return(self):
        self.item.status = Item.Status.NOT_FOR_LOAN
        self.item.save()
        self.assertEqual(self.codes(self.lend()), {'reading_room'})

        result = self.lend(override=True, reason="Bir kechaga")
        loans.checkin(result.rental, self.librarian)

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.NOT_FOR_LOAN)

    def test_held_copy_goes_only_to_the_holder(self):
        hold = self.hold(self.other, Reservation.Status.AVAILABLE)

        refused = self.lend()
        self.assertEqual(self.codes(refused), {'held'})
        self.assertIn(self.other.display_name, refused.message)

        self.assertTrue(self.lend(self.other).ok)
        hold.refresh_from_db()
        self.assertEqual(hold.status, Reservation.Status.FULFILLED)

    def test_queue_does_not_block_when_enough_copies(self):
        make_copies(self.book, 1)
        self.hold(self.other)
        self.assertTrue(self.lend().ok)

    def test_pending_request_is_closed_by_desk_checkout(self):
        request = RentalRequest.objects.create(patron=self.patron, book=self.book)
        result = self.lend()
        request.refresh_from_db()
        self.assertEqual(request.status, RentalRequest.Status.APPROVED)
        self.assertEqual(request.rental, result.rental)

    def test_approving_request_respects_block(self):
        """Ilgari bloklangan a'zoning so'rovini ham tasdiqlab yuborish mumkin edi."""
        request = RentalRequest.objects.create(patron=self.patron, book=self.book)
        self.patron.status = Patron.Status.BLOCKED
        self.patron.block_reason = "Kitob yo'qotgan"
        self.patron.save()

        rental, message = services.approve_request(request, librarian=self.librarian)

        self.assertIsNone(rental)
        self.assertEqual(message, "Kitob yo'qotgan")
        request.refresh_from_db()
        self.assertEqual(request.status, RentalRequest.Status.PENDING)


class CheckinTests(LoanFixture):
    def overdue_rental(self, days=3):
        rental = self.lend().rental
        rental.due_date = now().date() - timedelta(days=days)
        rental.save(update_fields=['due_date'])
        return rental

    def test_late_return_charges_fine_at_once(self):
        result = loans.checkin(self.overdue_rental(3), self.librarian)

        self.assertEqual(result.days_late, 3)
        self.assertEqual(result.fine.amount, 1500)
        self.patron.refresh_from_db()
        self.assertEqual(self.patron.balance, 1500)
        self.assertEqual(self.patron.active_loans_count, 0)

    def test_paid_fine_is_not_changed(self):
        rental = self.overdue_rental(5)
        Fine.objects.create(rental=rental, patron=self.patron, days_overdue=1, amount=500,
                            is_paid=True)
        self.assertEqual(loans.checkin(rental, self.librarian).fine.amount, 500)

    def test_on_time_return_has_no_fine(self):
        result = loans.checkin(self.lend().rental, self.librarian)
        self.assertIsNone(result.fine)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.AVAILABLE)
        self.assertEqual(self.item.loan_count, 1)

    def test_next_in_queue_is_told(self):
        rental = self.lend().rental
        hold = self.hold(self.other)

        result = loans.checkin(rental, self.librarian)

        self.assertEqual(result.next_hold, hold)
        hold.refresh_from_db()
        self.assertEqual(hold.status, Reservation.Status.AVAILABLE)
        self.assertTrue(Notification.objects.filter(
            user=self.other.user, type=Notification.Type.RESERVATION_AVAILABLE).exists())

    def test_damaged_copy_is_not_offered_to_queue(self):
        rental = self.lend().rental
        self.hold(self.other)

        result = loans.checkin(rental, self.librarian, damaged=True)

        self.assertIsNone(result.next_hold)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.DAMAGED)

    def test_second_return_is_refused(self):
        rental = self.lend().rental
        loans.checkin(rental, self.librarian)
        self.assertFalse(loans.checkin(rental, self.librarian).ok)


class RenewAndHoldTests(LoanFixture):
    def test_renew_extends_from_current_due_date(self):
        rental = self.lend().rental
        result = loans.renew(rental, self.librarian)

        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.rental.due_date, now().date() + timedelta(days=20))
        self.assertEqual(result.rental.renewals_count, 1)

    def test_renew_limit_can_be_overridden(self):
        rental = self.lend().rental
        loans.renew(rental, self.librarian)

        refused = loans.renew(rental, self.librarian)
        self.assertEqual(self.codes(refused), {'renewals'})
        self.assertTrue(loans.renew(rental, self.librarian, override=True, reason="Sessiya").ok)

    def test_overdue_loan_cannot_be_renewed(self):
        rental = self.lend().rental
        rental.due_date = now().date() - timedelta(days=1)
        rental.save(update_fields=['due_date'])

        result = loans.renew(rental, self.librarian, override=True, reason="x")

        self.assertFalse(result.ok)
        self.assertFalse(result.can_override)

    def test_queue_stops_renewal(self):
        rental = self.lend().rental
        self.hold(self.other)
        self.assertEqual(self.codes(loans.renew(rental, self.librarian)), {'held'})

    def test_cancelling_ready_hold_moves_queue(self):
        ready = self.hold(self.patron, Reservation.Status.AVAILABLE)
        waiting = self.hold(self.other)

        result = loans.cancel_hold(ready, self.librarian)

        self.assertEqual(result.next_hold, waiting)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Reservation.Status.AVAILABLE)
