"""Abonement deski (`/panel/desk/`): skaner oqimi va ruxsatlar."""
import json
from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now

from book_app.models import Item, Rental
from circulation.models import Fine, RentalRequest, Reservation
from core.testing import make_book, make_copies, make_employee, make_librarian, make_student
from user_app.models import Patron, Role
from user_app.permissions import Perms
from user_app.services import get_or_create_patron


class DeskFixture(TestCase):
    def setUp(self):
        self.librarian = make_librarian()
        self.patron = get_or_create_patron(
            make_student(first_name='Dilnoza', second_name='Karimova'))
        self.other = get_or_create_patron(
            make_student(first_name='Sardor', second_name='Aliyev'))
        self.book = make_book("Iqtisodiyot nazariyasi")
        self.item = make_copies(self.book, 1)[0]
        self.item.barcode = 'XIU000000901'
        self.item.save()
        self.client.force_login(self.librarian)

    def post(self, name, data):
        return self.client.post(f'/panel/desk/{name}/', data, HTTP_HX_REQUEST='true')

    def toast(self, response):
        return json.loads(response.headers['HX-Trigger'])['toast']

    def lend(self, **extra):
        return self.post('checkout', {'patron': self.patron.pk, 'code': self.item.barcode, **extra})


class DeskPageTests(DeskFixture):
    def test_opens_with_patron_search(self):
        response = self.client.get('/panel/desk/')
        self.assertContains(response, "zoni tanlang")
        self.assertContains(response, 'data-desk-link')

    def test_scanned_card_selects_patron(self):
        response = self.client.get('/panel/desk/', {'q': self.patron.card_number},
                                   HTTP_HX_REQUEST='true')
        self.assertContains(response, 'KARIMOVA DILNOZA')
        self.assertEqual(response.headers['HX-Push-Url'], f'/panel/desk/?patron={self.patron.pk}')

    def test_name_search_lists_matches(self):
        response = self.client.get('/panel/desk/patrons/', {'q': 'karim'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'KARIMOVA')
        self.assertNotContains(response, 'ALIYEV')


class DeskCheckoutTests(DeskFixture):
    def test_barcode_lends_immediately(self):
        response = self.lend()

        self.assertEqual(self.toast(response)['level'], 'success')
        self.assertTrue(Rental.objects.filter(patron=self.patron, copy=self.item,
                                              return_date__isnull=True).exists())

    def test_title_search_asks_which_copy(self):
        response = self.post('checkout', {'patron': self.patron.pk, 'code': 'Iqtisodiyot'})

        self.assertContains(response, 'XIU000000901')
        self.assertFalse(Rental.objects.exists())

        self.post('checkout', {'patron': self.patron.pk, 'item': self.item.pk})
        self.assertEqual(Rental.objects.count(), 1)

    def test_next_patrons_card_switches_patron(self):
        response = self.post('checkout', {'patron': self.patron.pk,
                                          'code': self.other.card_number})
        self.assertContains(response, 'ALIYEV SARDOR')
        self.assertFalse(Rental.objects.exists())

    def test_unknown_code(self):
        response = self.post('checkout', {'patron': self.patron.pk, 'code': 'YOQ-123456'})
        self.assertEqual(self.toast(response)['level'], 'danger')

    def test_bad_date(self):
        response = self.lend(due_date='31-31-2026')
        self.assertEqual(self.toast(response)['level'], 'danger')
        self.assertFalse(Rental.objects.exists())

    def test_blocked_patron_shows_override_form(self):
        self.patron.status = Patron.Status.BLOCKED
        self.patron.save(update_fields=['status'])

        response = self.lend()
        self.assertContains(response, 'name="override"')
        self.assertFalse(Rental.objects.exists())

        self.post('checkout', {'patron': self.patron.pk, 'item': self.item.pk,
                               'override': '1', 'reason': "Rahbar ruxsati"})
        self.assertEqual(Rental.objects.count(), 1)

    def test_pending_request_approved_from_desk(self):
        request = RentalRequest.objects.create(patron=self.patron, book=self.book)
        self.post('request', {'request': request.pk})
        request.refresh_from_db()
        self.assertEqual(request.status, RentalRequest.Status.APPROVED)

    def test_hold_for_busy_book(self):
        self.lend()
        busy = self.post('checkout', {'patron': self.other.pk, 'code': self.item.barcode})
        self.assertContains(busy, 'Shu kitobga navbatga yozish')
        self.assertNotContains(self.lend(), 'Shu kitobga navbatga yozish')
        self.post('hold', {'patron': self.other.pk, 'book': self.book.pk})
        hold = Reservation.objects.get(patron=self.other)

        self.post('hold/cancel', {'reservation': hold.pk})
        hold.refresh_from_db()
        self.assertEqual(hold.status, Reservation.Status.CANCELLED)


class DeskCheckinTests(DeskFixture):
    def setUp(self):
        super().setUp()
        self.lend()
        self.rental = Rental.objects.get()

    def test_barcode_returns_book_and_shows_fine(self):
        category = self.patron.category
        category.fine_per_day = 1000
        category.save()
        self.rental.due_date = now().date() - timedelta(days=2)
        self.rental.save(update_fields=['due_date'])

        response = self.post('checkin', {'mode': 'checkin', 'code': 'xiu000000901'})

        self.rental.refresh_from_db()
        self.assertIsNotNone(self.rental.return_date)
        self.assertContains(response, "2\xa0000 so'm")

        fine = Fine.objects.get()
        self.post('fine', {'fine': fine.pk, 'mode': 'checkin'})
        fine.refresh_from_db()
        self.assertTrue(fine.is_paid)

    def test_title_search_does_not_return_by_itself(self):
        response = self.post('checkin', {'mode': 'checkin', 'code': 'Iqtisodiyot'})

        self.assertContains(response, 'KARIMOVA')
        self.rental.refresh_from_db()
        self.assertIsNone(self.rental.return_date)

    def test_copy_that_is_not_on_loan(self):
        self.post('checkin', {'mode': 'checkin', 'code': self.item.barcode})
        response = self.post('checkin', {'mode': 'checkin', 'code': self.item.barcode})
        self.assertEqual(self.toast(response)['level'], 'warning')

    def test_damaged_flag(self):
        self.post('checkin', {'mode': 'checkin', 'code': self.item.barcode, 'damaged': '1'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.DAMAGED)

    def test_renew(self):
        before = self.rental.due_date
        self.post('renew', {'rental': self.rental.pk})
        self.rental.refresh_from_db()
        self.assertGreater(self.rental.due_date, before)


class DeskPermissionTests(DeskFixture):
    def staff(self, *permissions):
        user = make_employee()
        role = Role.objects.create(name=f"Rol {user.pk}", permissions=list(permissions))
        user.employe_profile.roles.add(role)
        self.client.force_login(user)

    def test_checkout_clerk_cannot_override(self):
        self.staff(Perms.CIRC_CHECKOUT)
        self.patron.status = Patron.Status.BLOCKED
        self.patron.save(update_fields=['status'])

        self.assertNotContains(self.lend(), 'name="override"')
        response = self.lend(override='1', reason='x')

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Rental.objects.exists())

    def test_return_only_clerk(self):
        self.lend()
        self.staff(Perms.CIRC_CHECKIN)

        page = self.client.get('/panel/desk/', {'patron': self.patron.pk})
        self.assertContains(page, 'name="mode" value="checkin"')
        self.assertNotContains(page, 'KARIMOVA')
        self.assertEqual(self.lend().status_code, 403)
        self.post('checkin', {'mode': 'checkin', 'code': self.item.barcode})
        self.assertIsNotNone(Rental.objects.get().return_date)

    def test_cataloguer_has_no_desk(self):
        self.staff(Perms.CATALOG_VIEW)
        self.assertEqual(self.client.get('/panel/desk/').status_code, 403)
        self.assertNotContains(self.client.get('/panel/'), 'data-desk-link')
