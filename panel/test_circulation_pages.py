"""So'rov, ijara, navbat va jarima sahifalari: amallar, ruxsatlar, eksport."""
import json
from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now

from audit.models import ActionLog
from book_app.models import Item, Rental
from circulation.models import Fine, RentalRequest, Reservation
from core.testing import make_book, make_copies, make_employee, make_librarian, make_student
from user_app.models import Role
from user_app.permissions import Perms
from user_app.services import get_or_create_patron


class PagesFixture(TestCase):
    def setUp(self):
        self.librarian = make_librarian()
        self.patron = get_or_create_patron(
            make_student(first_name='Dilnoza', second_name='Karimova'))
        self.other = get_or_create_patron(
            make_student(first_name='Sardor', second_name='Aliyev'))
        self.book = make_book("Mikroiqtisodiyot")
        self.item = make_copies(self.book, 1)[0]
        self.client.force_login(self.librarian)

    def hx(self, url, data=None):
        return self.client.post(url, data or {}, HTTP_HX_REQUEST='true')

    def toast(self, response):
        return json.loads(response.headers['HX-Trigger'])['toast']

    def rental(self, *, late=0, returned=False):
        today = now().date()
        self.item.status = Item.Status.AVAILABLE if returned else Item.Status.ON_LOAN
        self.item.save()
        return Rental.objects.create(
            copy=self.item, patron=self.patron, borrowed_date=today - timedelta(days=20),
            due_date=today - timedelta(days=late) if late else today + timedelta(days=5),
            return_date=today if returned else None)

    def fine(self, **kwargs):
        rental = self.rental(returned=kwargs.pop('returned', True))
        return Fine.objects.create(rental=rental, patron=self.patron, days_overdue=2, amount=2000)

    def staff(self, *permissions):
        user = make_employee()
        role = Role.objects.create(name=f"Rol {user.pk}", permissions=list(permissions))
        user.employe_profile.roles.add(role)
        self.client.force_login(user)


class ListTests(PagesFixture):
    def test_tabs_count_and_search(self):
        self.rental(late=3)
        response = self.client.get('/panel/rentals/', {'view': 'overdue'})
        self.assertEqual(response.context['tabs'][1][2], 1)
        self.assertContains(response, 'KARIMOVA')
        found = self.client.get('/panel/rentals/', {'q': 'karimova mikro'})
        self.assertEqual(found.context['page_obj'].paginator.count, 1)
        empty = self.client.get('/panel/rentals/', {'q': 'yoqbunday'})
        self.assertContains(empty, "Ijara topilmadi")

    def test_every_view_renders_with_rows(self):
        self.fine()
        RentalRequest.objects.create(patron=self.patron, book=self.book)
        Reservation.objects.create(patron=self.other, book=self.book)
        for url in ('/panel/requests/', '/panel/rentals/', '/panel/reservations/',
                    '/panel/fines/'):
            for view in ('all', 'closed', ''):
                with self.subTest(url=url, view=view):
                    self.assertEqual(self.client.get(url, {'view': view}).status_code, 200)

    def test_htmx_returns_only_the_table(self):
        response = self.client.get('/panel/requests/', HTTP_HX_REQUEST='true')
        self.assertNotContains(response, '<html')


class ActionTests(PagesFixture):
    def test_approve_reports_refusal(self):
        req = RentalRequest.objects.create(patron=self.patron, book=make_book("Nusxasiz"))
        response = self.hx(f'/panel/requests/{req.pk}/approve/')
        self.assertEqual(self.toast(response)['level'], 'danger')

    def test_reject_keeps_reason(self):
        req = RentalRequest.objects.create(patron=self.patron, book=self.book)
        self.hx(f'/panel/requests/{req.pk}/reject/', {'note': "Nusxa ta'mirda"})
        req.refresh_from_db()
        self.assertEqual(req.note, "Nusxa ta'mirda")

    def test_return_mentions_queue(self):
        rental = self.rental()
        Reservation.objects.create(patron=self.other, book=self.book)
        response = self.hx(f'/panel/rentals/{rental.pk}/return/')
        self.assertIn('ALIYEV', self.toast(response)['text'])

    def test_lost_book(self):
        rental = self.rental()
        self.hx(f'/panel/rentals/{rental.pk}/lost/', {'amount': '75 000', 'note': 'Avtobusda'})

        rental.refresh_from_db()
        self.item.refresh_from_db()
        self.patron.refresh_from_db()
        self.assertIsNotNone(rental.return_date)
        self.assertEqual(self.item.status, Item.Status.LOST)
        self.assertEqual(self.patron.balance, 75000)

    def test_lost_with_bad_amount_changes_nothing(self):
        rental = self.rental()
        for amount in ('abc', '-5', 'NaN', '1e30'):
            self.hx(f'/panel/rentals/{rental.pk}/lost/', {'amount': amount})
        rental.refresh_from_db()
        self.assertIsNone(rental.return_date)

    def test_charging_needs_billing_permission(self):
        rental = self.rental()
        self.staff(Perms.CIRC_CHECKIN)
        self.hx(f'/panel/rentals/{rental.pk}/lost/', {'amount': '1000'})
        rental.refresh_from_db()
        self.assertIsNone(rental.return_date)

    def test_cancel_reservation_moves_queue(self):
        ready = Reservation.objects.create(patron=self.patron, book=self.book,
                                           status=Reservation.Status.AVAILABLE)
        waiting = Reservation.objects.create(patron=self.other, book=self.book)
        self.hx(f'/panel/reservations/{ready.pk}/cancel/')
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Reservation.Status.AVAILABLE)


class FineActionTests(PagesFixture):
    def test_pay(self):
        fine = self.fine()
        self.hx(f'/panel/fines/{fine.pk}/paid/')
        fine.refresh_from_db()
        self.assertTrue(fine.is_paid)

    def test_open_loan_fine_waits_for_return(self):
        fine = self.fine(returned=False)
        for action, data in (('paid', {}), ('waive', {'note': 'x'}),
                             ('adjust', {'amount': '5', 'note': 'x'})):
            self.assertEqual(self.toast(self.hx(f'/panel/fines/{fine.pk}/{action}/', data))['level'],
                             'danger')
        fine.refresh_from_db()
        self.assertEqual((fine.is_paid, fine.amount), (False, 2000))

    def test_waive_needs_reason(self):
        fine = self.fine()
        self.hx(f'/panel/fines/{fine.pk}/waive/', {'note': ' '})
        fine.refresh_from_db()
        self.assertFalse(fine.is_paid)

        self.hx(f'/panel/fines/{fine.pk}/waive/', {'note': "Kasalxonada bo'lgan"})
        fine.refresh_from_db()
        self.patron.refresh_from_db()
        self.assertTrue(fine.is_waived)
        self.assertEqual(self.patron.balance, 0)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.WAIVE).exists())
        self.assertContains(self.client.get('/panel/fines/', {'view': 'waived'}), "Kasalxonada")

    def test_adjust(self):
        fine = self.fine()
        self.hx(f'/panel/fines/{fine.pk}/adjust/', {'amount': '1500', 'note': 'Kelishildi'})
        fine.refresh_from_db()
        self.assertEqual(fine.amount, 1500)

    def test_collector_cannot_waive(self):
        fine = self.fine()
        self.staff(Perms.BILLING_COLLECT)
        self.assertEqual(self.hx(f'/panel/fines/{fine.pk}/waive/', {'note': 'x'}).status_code, 403)
        page = self.client.get('/panel/fines/')
        self.assertContains(page, f'/panel/fines/{fine.pk}/paid/')
        self.assertNotContains(page, f'/panel/fines/{fine.pk}/waive/')


class ExportTests(PagesFixture):
    def test_csv_is_excel_friendly_and_safe(self):
        self.book.title = '=HYPERLINK("http://x")'
        self.book.save()
        self.rental()

        response = self.client.get('/panel/rentals/', {'view': 'active', 'export': 'csv'})

        body = response.content.decode('utf-8')
        self.assertTrue(body.startswith('﻿'))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn("'=HYPERLINK", body)
        self.assertIn('KARIMOVA', body)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.EXPORT).exists())

    def test_every_list_exports(self):
        self.fine()
        RentalRequest.objects.create(patron=self.patron, book=self.book)
        Reservation.objects.create(patron=self.other, book=self.book)
        for url in ('/panel/requests/', '/panel/rentals/', '/panel/reservations/',
                    '/panel/fines/'):
            with self.subTest(url=url):
                response = self.client.get(url, {'export': 'csv', 'view': 'all'})
                self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

    def test_export_needs_permission(self):
        self.staff(Perms.CIRC_CHECKOUT)
        response = self.client.get('/panel/rentals/', {'export': 'csv'})
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
