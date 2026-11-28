"""
Sirkulyatsiya testlari.

P1-B dan boshlab qarz oluvchi — `Patron`: talaba ham, xodim/o'qituvchi ham.
Shuning uchun eski "faqat talaba" qoidasini tekshiruvchi testlar yangi qoidaga
moslandi.
"""
from datetime import timedelta

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils.timezone import now

from book_app.models import Book, Genre, Item, Rental
from core.testing import make_employee, make_librarian, make_student
from user_app.models import PatronCategory, User
from user_app.roles import Roles
from user_app.services import get_or_create_patron, sync_patron

from . import services
from .models import Fine, LibrarySettings, RentalRequest, Reservation


class MyRentalsAccessTests(TestCase):
    """«Mening ijaralarim» sahifasiga kirish — endi a'zolikka asoslangan."""

    def test_student_can_open(self):
        user = make_student(password='x')
        self.client.login(username=user.username, password='x')
        self.assertEqual(self.client.get('/circulation/my-rentals/').status_code, 200)

    def test_employee_can_open(self):
        """Yangi qoida: xodim ham kitob oladi, demak sahifa unga ham ochiq."""
        user = make_employee(password='x')
        self.client.login(username=user.username, password='x')
        self.assertEqual(self.client.get('/circulation/my-rentals/').status_code, 200)

    def test_librarian_is_sent_to_panel(self):
        """Kutubxona xodimi kitob olmaydi — uning ish joyi panel."""
        user = make_librarian(password='x')
        self.client.login(username=user.username, password='x')
        self.assertRedirects(self.client.get('/circulation/my-rentals/'), '/panel/',
                             fetch_redirect_response=False)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get('/circulation/my-rentals/').status_code, 302)


class MyRentalsPageTests(TestCase):
    """Yangi dizayndagi sahifa barcha bo'limlardagi ma'lumotni ko'rsatadi."""

    def setUp(self):
        self.user = make_student()
        self.patron = get_or_create_patron(self.user)
        genre = Genre.objects.create(name='G')
        today = now().date()

        def book_with_item(title, number):
            book = Book.objects.create(title=title, category=genre)
            return book, Item.objects.create(book=book, inventory_number=number)

        _, current = book_with_item("Joriy kitob", "INV-1")
        Rental.objects.create(copy=current, patron=self.patron,
                              borrowed_date=today - timedelta(days=30),
                              due_date=today - timedelta(days=2))
        _, returned = book_with_item("Qaytarilgan kitob", "INV-2")
        old_rental = Rental.objects.create(copy=returned, patron=self.patron,
                                           borrowed_date=today - timedelta(days=60),
                                           return_date=today - timedelta(days=40))
        Fine.objects.create(rental=old_rental, patron=self.patron, days_overdue=4, amount=4000)
        wanted, _ = book_with_item("So'ralgan kitob", "INV-3")
        RentalRequest.objects.create(patron=self.patron, book=wanted)
        queued, _ = book_with_item("Navbatdagi kitob", "INV-4")
        Reservation.objects.create(patron=self.patron, book=queued,
                                   status=Reservation.Status.AVAILABLE,
                                   hold_until=now() + timedelta(days=2))

    def test_all_sections_rendered(self):
        self.client.force_login(self.user)
        response = self.client.get('/circulation/my-rentals/')

        self.assertTemplateUsed(response, 'opac/my_rentals.html')
        for text in ("Joriy kitob", "Qaytarilgan kitob", "So&#x27;ralgan kitob",
                     "Navbatdagi kitob", "INV-1", "4 kun", "4000 so'm",
                     "Muddat o'tgan", "Sizni kutmoqda", self.patron.card_number):
            with self.subTest(text):
                self.assertContains(response, text)


class RentalFlowTests(TestCase):
    def setUp(self):
        genre = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=genre)
        self.copy = Item.objects.create(book=self.book, inventory_number='1', is_available=True)
        self.p1 = get_or_create_patron(make_student(username='s1'))
        self.p2 = get_or_create_patron(make_student(username='s2'))

    def test_request_and_approve(self):
        req, _ = services.create_rental_request(self.p1, self.book)
        self.assertIsNotNone(req)

        rental, _ = services.approve_request(req)
        self.assertIsNotNone(rental)
        self.assertEqual(rental.patron, self.p1)

        self.copy.refresh_from_db()
        self.assertFalse(self.copy.is_available)

        # Muddat a'zo TOIFASIDAN olinadi (talaba — 14 kun)
        expected_due = now().date() + timedelta(days=self.p1.category.default_loan_days)
        self.assertEqual(rental.due_date, expected_due)

        # A'zo kartasidagi hisoblagich yangilanadi
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.active_loans_count, 1)

    def test_employee_can_borrow(self):
        """Asosiy talab: xodim ham kitob so'ray oladi."""
        employee = make_employee(username='xodim-1')
        employee.employe_profile.position = "Bosh mutaxassis"
        employee.employe_profile.save()
        patron = sync_patron(employee)

        req, msg = services.create_rental_request(patron, self.book)
        self.assertIsNotNone(req, msg)

        rental, _ = services.approve_request(req)
        self.assertEqual(rental.patron.category.code, PatronCategory.Code.STAFF)
        # Xodim toifasida muddat uzunroq (21 kun)
        self.assertEqual(rental.due_date, now().date() + timedelta(days=21))

    def test_teacher_gets_longer_loan(self):
        teacher = make_employee(username='dotsent-1')
        teacher.employe_profile.position = "Dotsent"
        teacher.employe_profile.save()
        patron = sync_patron(teacher)

        req, _ = services.create_rental_request(patron, self.book)
        rental, _ = services.approve_request(req)
        self.assertEqual(rental.due_date, now().date() + timedelta(days=30))

    def test_duplicate_request_blocked(self):
        services.create_rental_request(self.p1, self.book)
        req, msg = services.create_rental_request(self.p1, self.book)
        self.assertIsNone(req)
        self.assertIn("allaqachon", msg)

    def test_blocked_patron_cannot_request(self):
        self.p1.status = self.p1.Status.BLOCKED
        self.p1.block_reason = "Kitob yo'qotgan"
        self.p1.save()

        req, msg = services.create_rental_request(self.p1, self.book)
        self.assertIsNone(req)
        self.assertIn("yo'qotgan", msg)

    def test_loan_limit_from_category(self):
        self.p1.category.loan_limit = 1
        self.p1.category.save()

        req, _ = services.create_rental_request(self.p1, self.book)
        services.approve_request(req)

        other = Book.objects.create(title='B2', category=self.book.category)
        Item.objects.create(book=other, inventory_number='2', is_available=True)
        self.p1.refresh_from_db()

        req2, msg = services.create_rental_request(self.p1, other)
        self.assertIsNone(req2)
        self.assertIn("limit", msg.lower())

    def test_reserve_when_unavailable(self):
        self.copy.is_available = False
        self.copy.save()
        res, _ = services.create_reservation(self.p2, self.book)
        self.assertIsNotNone(res)

    def test_return_fulfills_next_reservation(self):
        req, _ = services.create_rental_request(self.p1, self.book)
        rental, _ = services.approve_request(req)
        Reservation.objects.create(book=self.book, patron=self.p2)

        services.return_rental(rental)

        self.copy.refresh_from_db()
        self.assertTrue(self.copy.is_available)
        res = Reservation.objects.get(book=self.book, patron=self.p2)
        self.assertEqual(res.status, Reservation.Status.AVAILABLE)

    def test_active_rental_constraint(self):
        Rental.objects.create(copy=self.copy, patron=self.p1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rental.objects.create(copy=self.copy, patron=self.p2)

    def test_pending_request_constraint(self):
        RentalRequest.objects.create(patron=self.p1, book=self.book)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RentalRequest.objects.create(patron=self.p1, book=self.book)

    def test_student_field_still_filled(self):
        """Ikki yozuvli davr: eski `student` maydoni ham to'ldiriladi."""
        req, _ = services.create_rental_request(self.p1, self.book)
        self.assertIsNotNone(req.student)
        self.assertEqual(req.student.user, self.p1.user)


class FineTests(TestCase):
    def setUp(self):
        settings_obj = LibrarySettings.load()
        settings_obj.fine_per_day = 1000
        settings_obj.save()

        genre = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=genre)
        self.copy = Item.objects.create(book=self.book, inventory_number='1', is_available=False)
        self.patron = get_or_create_patron(User.objects.create(username='s', user_type='STUDENT'))

    def _overdue_rental(self, days=3):
        return Rental.objects.create(
            copy=self.copy, patron=self.patron,
            borrowed_date=now().date() - timedelta(days=20),
            due_date=now().date() - timedelta(days=days))

    def test_overdue_creates_fine(self):
        self._overdue_rental(days=3)
        call_command('run_jobs', 'fines_accrual')

        fine = Fine.objects.get(patron=self.patron)
        self.assertEqual(fine.days_overdue, 3)
        self.assertEqual(fine.amount, 3000)

    def test_fine_rate_from_category(self):
        """Toifada stavka berilgan bo'lsa, u umumiy sozlamadan ustun turadi."""
        self.patron.category.fine_per_day = 2500
        self.patron.category.save()
        self._overdue_rental(days=2)

        call_command('run_jobs', 'fines_accrual')
        self.assertEqual(Fine.objects.get(patron=self.patron).amount, 5000)

    def test_patron_counters_updated(self):
        self._overdue_rental(days=4)
        call_command('run_jobs', 'fines_accrual')

        self.patron.refresh_from_db()
        self.assertEqual(self.patron.active_loans_count, 1)
        self.assertEqual(self.patron.overdue_count, 1)
        self.assertEqual(self.patron.balance, 4000)

    def test_mark_paid_clears_balance(self):
        self._overdue_rental(days=4)
        call_command('run_jobs', 'fines_accrual')
        fine = Fine.objects.get(patron=self.patron)

        ok, _ = services.mark_fine_paid(fine)
        self.assertTrue(ok)

        self.patron.refresh_from_db()
        self.assertEqual(self.patron.balance, 0)


class LibrarianPermissionTests(TestCase):
    """Kutubxonachi amallari endi ruxsat flagi bilan himoyalangan."""

    def setUp(self):
        genre = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=genre)
        Item.objects.create(book=self.book, inventory_number='1', is_available=True)
        self.patron = get_or_create_patron(make_student(username='talaba-9'))
        self.req, _ = services.create_rental_request(self.patron, self.book)

    def test_student_cannot_approve(self):
        user = make_student(username='oddiy', password='x')
        self.client.login(username=user.username, password='x')
        response = self.client.post(f'/circulation/manage/request/{self.req.pk}/approve/')
        self.assertEqual(response.status_code, 403)

    def test_librarian_can_approve(self):
        user = make_librarian(username='kutubxonachi-1', password='x')
        self.client.login(username=user.username, password='x')
        response = self.client.post(f'/circulation/manage/request/{self.req.pk}/approve/')
        self.assertEqual(response.status_code, 200)

        self.req.refresh_from_db()
        self.assertEqual(self.req.status, RentalRequest.Status.APPROVED)

    def test_role_still_resolves(self):
        self.assertEqual(
            make_librarian(username='kutubxonachi-2').employe_profile.current_role.name,
            Roles.LIBRARIAN)
