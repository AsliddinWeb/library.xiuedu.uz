"""Boshqaruv paneli, xodim profili, analitika, sharh, sozlama, a'zo va fond amallari."""
from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now

from audit.models import ActionLog
from book_app.models import Rental
from circulation import loans
from circulation.models import LibrarySettings, Reservation
from core.testing import make_book, make_copies, make_librarian, make_student
from engagement.models import Review
from holdings.models import ItemType, Library, ShelfLocation
from user_app.models import Patron, PatronCategory
from user_app.services import get_category, get_or_create_patron


class PanelFixture(TestCase):
    def setUp(self):
        self.librarian = make_librarian()
        self.client.force_login(self.librarian)
        self.patron = get_or_create_patron(make_student(second_name='Karimova'))
        self.book = make_book('</script><script>alert(1)</script>')
        self.item = make_copies(self.book, 1)[0]


class DashboardTests(PanelFixture):
    def test_today_numbers_and_own_work(self):
        loans.checkout(self.patron, self.item, self.librarian)

        response = self.client.get('/panel/')

        self.assertEqual(response.context['stats']['issued_today'], 1)
        self.assertEqual(response.context['my_actions'][0].actor, self.librarian)

    def test_profile_shows_work(self):
        loans.checkout(self.patron, self.item, self.librarian)
        response = self.client.get('/panel/profile/')
        issued = response.context['work_stats'][0]
        self.assertEqual((issued['today'], issued['month']), (1, 1))
        self.assertGreater(response.context['history'].paginator.count, 0)

    def test_titles_cannot_break_out_of_chart_data(self):
        """Kitob nomi grafik ma'lumoti orqali sahifaga skript kiritolmaydi."""
        self.book.view_count = 5
        self.book.save(update_fields=['view_count'])
        loans.checkout(self.patron, self.item, self.librarian)
        for url in ('/panel/', '/panel/analytics/'):
            self.assertNotContains(self.client.get(url), '<script>alert(1)')


class AnalyticsTests(PanelFixture):
    def test_period_and_export(self):
        Rental.objects.create(copy=self.item, patron=self.patron,
                              borrowed_date=now().date() - timedelta(days=40))
        short = self.client.get('/panel/analytics/', {'period': 7})
        long = self.client.get('/panel/analytics/', {'period': 90})
        self.assertEqual((short.context['summary']['issued'], long.context['summary']['issued']),
                         (0, 1))
        self.assertEqual(self.client.get('/panel/analytics/', {'period': 'x'}).context['period'], 30)

        export = self.client.get('/panel/analytics/', {'period': 7, 'export': 'csv'})
        self.assertEqual(len(export.content.decode('utf-8-sig').strip().splitlines()), 8)


class ReviewAndSettingsTests(PanelFixture):
    def test_review_moderation(self):
        review = Review.objects.create(user=self.patron.user, book=self.book, rating=4,
                                       text="Yaxshi")
        self.assertContains(self.client.get('/panel/reviews/'), "Yaxshi")
        self.client.post(f'/panel/reviews/{review.pk}/approve/', HTTP_HX_REQUEST='true')
        review.refresh_from_db()
        self.assertTrue(review.is_approved)
        self.client.post(f'/panel/reviews/{review.pk}/reject/', HTTP_HX_REQUEST='true')
        self.assertFalse(Review.objects.exists())
        self.assertEqual(ActionLog.objects.filter(action=ActionLog.Action.MODERATE).count(), 2)

    def test_settings_saved_and_logged(self):
        data = {'rental_days': 21, 'reservation_hold_days': 3, 'fine_per_day': 500,
                'max_active_rentals': 4}
        self.client.post('/panel/settings/', data)
        self.assertEqual(LibrarySettings.load().rental_days, 21)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.SETTINGS).exists())

        self.client.post('/panel/settings/', {**data, 'rental_days': 0})
        self.assertEqual(LibrarySettings.load().rental_days, 21)


class MemberTests(PanelFixture):
    def external(self):
        return Patron.objects.create(card_number='TASHQI-1', full_name="Tashqi O'quvchi",
                                     category=get_category(PatronCategory.Code.EXTERNAL))

    def test_export(self):
        response = self.client.get('/panel/members/', {'export': 'csv'})
        self.assertIn('KARIMOVA', response.content.decode('utf-8-sig'))

    def test_bad_block_date_is_refused(self):
        for until in ('31.12.2030', '2001-01-01'):
            self.client.post(f'/panel/members/{self.patron.pk}/block/',
                             {'reason': 'x', 'until': until})
        self.patron.refresh_from_db()
        self.assertEqual(self.patron.status, Patron.Status.ACTIVE)

    def test_delete_only_manual_member_without_history(self):
        manual = self.external()
        self.client.post(f'/panel/members/{manual.pk}/delete/')
        self.assertFalse(Patron.objects.filter(pk=manual.pk).exists())

        self.client.post(f'/panel/members/{self.patron.pk}/delete/')
        self.assertTrue(Patron.objects.filter(pk=self.patron.pk).exists())

        used = self.external()
        Reservation.objects.create(patron=used, book=self.book)
        self.client.post(f'/panel/members/{used.pk}/delete/')
        self.assertTrue(Patron.objects.filter(pk=used.pk).exists())


class HoldingsAndFundTests(PanelFixture):
    def test_delete_unused_only(self):
        library = Library.objects.create(code='DEL', name="Bo'sh filial")
        shelf = ShelfLocation.objects.create(library=library, code='S1', name="Javon")

        self.client.post(f'/panel/holdings/library/{library.pk}/delete/')
        self.assertTrue(Library.objects.filter(pk=library.pk).exists())

        self.client.post(f'/panel/holdings/shelf/{shelf.pk}/delete/')
        self.client.post(f'/panel/holdings/library/{library.pk}/delete/')
        self.assertFalse(Library.objects.filter(pk=library.pk).exists())

        kind = ItemType.objects.create(code='USED', name="Band tur")
        self.item.item_type = kind
        self.item.save()
        self.client.post(f'/panel/holdings/type/{kind.pk}/delete/')
        self.assertTrue(ItemType.objects.filter(pk=kind.pk).exists())
        self.assertEqual(self.client.get('/panel/holdings/').status_code, 200)

    def test_fund_export(self):
        self.item.barcode = 'FOND-1'
        self.item.save()
        response = self.client.get('/panel/items/', {'export': 'csv'})
        self.assertIn('FOND-1', response.content.decode('utf-8-sig'))
