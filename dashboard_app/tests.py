"""Bosh sahifa va profil testlari."""
from django.test import TestCase
from django.urls import reverse

from core.testing import make_book, make_employee, make_genre, make_student


class HomePageTests(TestCase):
    """Bosh sahifa mehmonga ham ochiq va fonddagi haqiqiy ma'lumotni ko'rsatadi."""

    def setUp(self):
        genre = make_genre("Dasturlash")
        self.book = make_book("Algoritmlar asoslari", genre=genre,
                              electronic_version='ebooks/x.pdf')
        make_book("Yashirin yozuv", genre=genre, is_active=False)

    def test_guest_sees_books_and_login_choices(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Algoritmlar asoslari")
        self.assertNotContains(response, "Yashirin yozuv")
        # Talaba ham, xodim ham kira olishi kerak
        self.assertContains(response, reverse('student_login'))
        self.assertContains(response, reverse('employee_login'))
        # Mehmon kitobni bossa kirish oynasi ochiladi
        self.assertContains(response, 'data-login')

    def test_counts_come_from_catalogue(self):
        stats = self.client.get('/').context['stats']
        self.assertEqual((stats['total'], stats['digital'], stats['audio'], stats['genres']),
                         (1, 1, 0, 1))

    def test_empty_library_still_renders(self):
        self.book.delete()
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_signed_in_user_gets_no_login_modal(self):
        self.client.force_login(make_student())
        response = self.client.get('/')
        self.assertNotContains(response, 'id="login-title"')
        self.assertNotContains(response, 'data-login')

    def test_theme_is_applied_before_styles(self):
        """Mavzu skripti CSS'dan oldin turmasa tungi rejimda sahifa miltillaydi."""
        html = self.client.get('/').content.decode()
        self.assertLess(html.index("localStorage.getItem('xiu-theme')"),
                        html.index('css/app.css'))


class ProfilePageTests(TestCase):
    def test_student_and_employee_see_card_number(self):
        for factory in (make_student, make_employee):
            with self.subTest(factory.__name__):
                user = factory()
                self.client.force_login(user)
                response = self.client.get('/profil/')
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, response.context['patron'].card_number)
