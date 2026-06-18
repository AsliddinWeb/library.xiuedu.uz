from datetime import timedelta

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils.timezone import now

from book_app.models import Book, Copy, Genre, Rental
from user_app.models import Role, StudentProfile, User
from user_app.roles import Roles

from . import services
from .models import Fine, LibrarySettings, Reservation


class LibrarianAccessTests(TestCase):
    """Xodim (qoldiq student profil bo'lsa ham) talaba sahifalariga kira olmaydi."""

    def test_employee_with_stray_profile_forbidden(self):
        lib = User.objects.create_user(username='lib', password='x', user_type='EMPLOYE')
        # qoldiq student profil (eski create_user ssenariysi)
        StudentProfile.objects.create(user=lib)
        lib.employe_profile.current_role = Role.objects.get(name=Roles.LIBRARIAN)
        lib.employe_profile.save()
        self.client.login(username='lib', password='x')
        self.assertEqual(self.client.get('/circulation/my-rentals/').status_code, 403)


class RentalFlowTests(TestCase):
    def setUp(self):
        g = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=g)
        self.copy = Copy.objects.create(book=self.book, inventory_number='1', is_available=True)
        self.s1 = User.objects.create(username='s1', user_type='STUDENT').student_profile
        self.s2 = User.objects.create(username='s2', user_type='STUDENT').student_profile

    def test_request_and_approve(self):
        req, _ = services.create_rental_request(self.s1, self.book)
        self.assertIsNotNone(req)
        rental, _ = services.approve_request(req)
        self.assertIsNotNone(rental)
        self.copy.refresh_from_db()
        self.assertFalse(self.copy.is_available)
        expected_due = now().date() + timedelta(days=LibrarySettings.load().rental_days)
        self.assertEqual(rental.due_date, expected_due)

    def test_duplicate_request_blocked(self):
        services.create_rental_request(self.s1, self.book)
        req, _ = services.create_rental_request(self.s1, self.book)
        self.assertIsNone(req)

    def test_reserve_when_unavailable(self):
        self.copy.is_available = False
        self.copy.save()
        res, _ = services.create_reservation(self.s2, self.book)
        self.assertIsNotNone(res)

    def test_return_fulfills_next_reservation(self):
        req, _ = services.create_rental_request(self.s1, self.book)
        rental, _ = services.approve_request(req)
        Reservation.objects.create(book=self.book, student=self.s2)
        services.return_rental(rental)
        self.copy.refresh_from_db()
        self.assertTrue(self.copy.is_available)
        res = Reservation.objects.get(book=self.book, student=self.s2)
        self.assertEqual(res.status, Reservation.Status.AVAILABLE)

    def test_active_rental_constraint(self):
        Rental.objects.create(copy=self.copy, student=self.s1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rental.objects.create(copy=self.copy, student=self.s2)


class FineTests(TestCase):
    def test_overdue_creates_fine(self):
        s = LibrarySettings.load()
        s.fine_per_day = 1000
        s.save()
        g = Genre.objects.create(name='G')
        book = Book.objects.create(title='B', category=g)
        copy = Copy.objects.create(book=book, inventory_number='1', is_available=False)
        student = User.objects.create(username='s', user_type='STUDENT').student_profile
        Rental.objects.create(copy=copy, student=student,
                              borrowed_date=now().date() - timedelta(days=20),
                              due_date=now().date() - timedelta(days=3))
        call_command('circulation_tick')
        fine = Fine.objects.get(student=student)
        self.assertEqual(fine.days_overdue, 3)
        self.assertEqual(fine.amount, 3000)
