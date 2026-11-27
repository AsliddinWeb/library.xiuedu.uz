"""Xodim paneli testlari — a'zolar moduli (P1-B)."""
from django.test import TestCase
from django.utils.timezone import now

from audit.models import ActionLog
from core.testing import make_employee, make_librarian, make_student
from user_app.models import Patron, PatronCategory
from user_app.services import get_category, get_or_create_patron, sync_patron


class MembersAccessTests(TestCase):
    def setUp(self):
        self.patron = get_or_create_patron(make_student(username='talaba-p'))

    def test_librarian_sees_list(self):
        user = make_librarian(password='x')
        self.client.login(username=user.username, password='x')
        response = self.client.get('/panel/members/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patron.card_number)

    def test_student_forbidden(self):
        user = make_student(username='oddiy-p', password='x')
        self.client.login(username=user.username, password='x')
        self.assertEqual(self.client.get('/panel/members/').status_code, 403)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get('/panel/members/').status_code, 302)


class MembersListTests(TestCase):
    def setUp(self):
        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')

        self.student = get_or_create_patron(make_student(username='talaba-list'))
        employee = make_employee(username='xodim-list')
        employee.employe_profile.position = "Dotsent"
        employee.employe_profile.save()
        self.teacher = sync_patron(employee)

    def test_list_shows_students_and_employees(self):
        """A'zolar ro'yxatida talaba ham, xodim ham bo'ladi."""
        response = self.client.get('/panel/members/')
        self.assertContains(response, self.student.card_number)
        self.assertContains(response, self.teacher.card_number)

    def test_search_by_card_number(self):
        response = self.client.get('/panel/members/', {'q': self.teacher.card_number})
        self.assertContains(response, self.teacher.card_number)
        self.assertNotContains(response, self.student.card_number)

    def test_filter_by_category(self):
        response = self.client.get('/panel/members/',
                                   {'category': PatronCategory.Code.TEACHER})
        self.assertContains(response, self.teacher.card_number)
        self.assertNotContains(response, self.student.card_number)

    def test_filter_by_status(self):
        self.student.status = Patron.Status.BLOCKED
        self.student.save()

        response = self.client.get('/panel/members/', {'status': Patron.Status.BLOCKED})
        self.assertContains(response, self.student.card_number)
        self.assertNotContains(response, self.teacher.card_number)


class MemberDetailTests(TestCase):
    def setUp(self):
        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')
        self.patron = get_or_create_patron(make_student(username='talaba-d'))

    def test_detail_renders(self):
        response = self.client.get(f'/panel/members/{self.patron.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patron.card_number)
        self.assertContains(response, self.patron.category.name)

    def test_block_and_unblock(self):
        response = self.client.post(f'/panel/members/{self.patron.pk}/block/',
                                    {'reason': "Kitob qaytarilmadi"})
        self.assertEqual(response.status_code, 302)

        self.patron.refresh_from_db()
        self.assertEqual(self.patron.status, Patron.Status.BLOCKED)
        self.assertTrue(self.patron.is_blocked)
        can, reason = self.patron.can_borrow()
        self.assertFalse(can)
        self.assertIn("qaytarilmadi", reason)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.PATRON_BLOCK).exists())

        self.client.post(f'/panel/members/{self.patron.pk}/unblock/')
        self.patron.refresh_from_db()
        self.assertEqual(self.patron.status, Patron.Status.ACTIVE)

    def test_renew_sets_expiry_for_limited_category(self):
        self.patron.category = get_category(PatronCategory.Code.EXTERNAL)
        self.patron.save()

        self.client.post(f'/panel/members/{self.patron.pk}/renew/')
        self.patron.refresh_from_db()

        self.assertIsNotNone(self.patron.expires_on)
        self.assertGreater(self.patron.expires_on, now().date())

    def test_block_requires_permission(self):
        user = make_student(username='talaba-x', password='x')
        self.client.login(username=user.username, password='x')
        response = self.client.post(f'/panel/members/{self.patron.pk}/block/', {'reason': 'x'})
        self.assertEqual(response.status_code, 403)


class ManualPatronTests(TestCase):
    """HEMIS'siz (tashqi) a'zoni qo'lda qo'shish."""

    def setUp(self):
        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')
        self.category = get_category(PatronCategory.Code.EXTERNAL)

    def test_create_form_opens(self):
        response = self.client.get('/panel/members/new/')
        self.assertEqual(response.status_code, 200)
        # Shablon apostrofni HTML-escape qiladi, shuning uchun forma maydonlari tekshiriladi
        self.assertContains(response, 'name="card_number"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="full_name"')

    def test_create_patron(self):
        response = self.client.post('/panel/members/new/', {
            'card_number': 'XIU-800001',
            'category': self.category.pk,
            'status': Patron.Status.ACTIVE,
            'full_name': "Tashqi O'quvchi",
            'phone': '+998901234567',
            'deposit_amount': '0',
        })
        self.assertEqual(response.status_code, 302)

        patron = Patron.objects.get(card_number='XIU-800001')
        self.assertEqual(patron.display_name, "Tashqi O'quvchi")
        self.assertIsNone(patron.user)
        # A'zolik muddati toifadan avtomatik qo'yiladi (12 oy)
        self.assertIsNotNone(patron.expires_on)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.PATRON_CREATE).exists())

    def test_full_name_required_without_user(self):
        response = self.client.post('/panel/members/new/', {
            'card_number': 'XIU-800002',
            'category': self.category.pk,
            'status': Patron.Status.ACTIVE,
            'deposit_amount': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "majburiy")
        self.assertFalse(Patron.objects.filter(card_number='XIU-800002').exists())

    def test_edit_logs_changes(self):
        patron = Patron.objects.create(card_number='XIU-800003', full_name="Eski nom",
                                       category=self.category)
        self.client.post(f'/panel/members/{patron.pk}/edit/', {
            'card_number': patron.card_number,
            'category': self.category.pk,
            'status': Patron.Status.ACTIVE,
            'full_name': "Yangi nom",
            'deposit_amount': '0',
        })

        patron.refresh_from_db()
        self.assertEqual(patron.full_name, "Yangi nom")
        log = ActionLog.objects.filter(action=ActionLog.Action.PATRON_EDIT).first()
        self.assertIn('full_name', log.changes)


class PanelSmokeTests(TestCase):
    """Panelning barcha asosiy sahifasi ochilishi kerak.

    Bu testlar P2'da topilgan xatoni (Book -> Item teskari bog'lanish nomi
    o'zgargach `/panel/books/` ishlamay qolgan edi) qaytib kelmasligi uchun.
    """

    def setUp(self):
        from book_app.services import create_items
        from core.testing import make_book

        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')
        self.book = make_book("Panel kitobi")
        create_items(self.book, 2)

    def test_all_panel_pages_open(self):
        urls = [
            '/panel/', '/panel/books/', f'/panel/books/{self.book.pk}/',
            '/panel/genres/', '/panel/authors/', '/panel/import/',
            '/panel/requests/', '/panel/rentals/', '/panel/reservations/', '/panel/fines/',
            '/panel/members/', '/panel/reviews/', '/panel/analytics/', '/panel/settings/',
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_book_list_shows_copy_counts(self):
        response = self.client.get('/panel/books/')
        self.assertContains(response, "Panel kitobi")

    def test_copy_add_and_withdraw(self):
        from book_app.models import Item

        response = self.client.post(f'/panel/books/{self.book.pk}/copies/add/', {'quantity': 3})
        self.assertEqual(response.status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.items_count, 5)

        item = Item.objects.filter(book=self.book).first()
        self.client.post(f'/panel/copies/{item.pk}/delete/', {'reason': 'Sinov'})

        item.refresh_from_db()
        self.assertEqual(item.status, Item.Status.WITHDRAWN)
