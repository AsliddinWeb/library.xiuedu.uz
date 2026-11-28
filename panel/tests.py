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


# =============================================================================
#  P2-B — kataloglash formasi, nusxa boshqaruvi, tezkor qidiruv, fond tuzilmasi
# =============================================================================

class QuickSearchTests(TestCase):
    """Topbardagi qidiruv skaner bilan ishlashi kerak."""

    def setUp(self):
        from book_app.services import create_items
        from core.testing import make_book

        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')
        self.book = make_book("Qidiruv kitobi")
        self.item = create_items(self.book, 1)[0]
        self.patron = get_or_create_patron(make_student(username='talaba-qidiruv'))

    def test_barcode_opens_item(self):
        response = self.client.get('/panel/search/', {'q': self.item.barcode})
        self.assertRedirects(response, f'/panel/items/{self.item.pk}/')

    def test_card_number_opens_desk(self):
        """Abonement xodimi biletni skanerlasa — darrov kitob berish oynasi."""
        response = self.client.get('/panel/search/', {'q': self.patron.card_number})
        self.assertRedirects(response, f'/panel/desk/?patron={self.patron.pk}')

    def test_card_number_opens_card_without_checkout(self):
        from core.testing import make_employee
        from user_app.models import Role

        user = make_employee()
        role = Role.objects.create(name="A'zo ko'ruvchi",
                                   permissions=['catalog.view', 'patrons.view'])
        user.employe_profile.roles.add(role)
        self.client.force_login(user)
        response = self.client.get('/panel/search/', {'q': self.patron.card_number})
        self.assertRedirects(response, f'/panel/members/{self.patron.pk}/')

    def test_inventory_number_opens_item(self):
        response = self.client.get('/panel/search/', {'q': self.item.inventory_number})
        self.assertRedirects(response, f'/panel/items/{self.item.pk}/')

    def test_free_text_goes_to_catalog(self):
        response = self.client.get('/panel/search/', {'q': 'algoritm'})
        self.assertRedirects(response, '/panel/books/?q=algoritm', fetch_redirect_response=False)


class ItemManagementTests(TestCase):
    def setUp(self):
        from book_app.services import create_items
        from core.testing import make_book

        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')
        self.book = make_book("Nusxa kitobi")
        self.items = create_items(self.book, 3)
        self.item = self.items[0]

    def test_item_list_and_filter(self):
        from book_app.models import Item
        from book_app.services import change_item_status

        change_item_status(self.item, Item.Status.DAMAGED, reason="Sinov")

        response = self.client.get('/panel/items/', {'status': Item.Status.DAMAGED})
        self.assertContains(response, self.item.barcode)
        self.assertNotContains(response, self.items[1].barcode)

    def test_item_detail_renders(self):
        response = self.client.get(f'/panel/items/{self.item.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.barcode)

    def test_item_edit_saves_and_logs(self):
        from holdings.models import ShelfLocation

        shelf = ShelfLocation.objects.create(library=self.item.library, code='C-7',
                                             name="7-javon", zone="C-zona")
        response = self.client.post(f'/panel/items/{self.item.pk}/', {
            'barcode': self.item.barcode,
            'inventory_number': self.item.inventory_number,
            'call_number': '004.4 A-12',
            'item_type': self.item.item_type_id,
            'library': self.item.library_id,
            'shelf_location': shelf.pk,
            'condition': 'GOOD',
            'acquisition_source': 'PURCHASE',
            'price': '50000',
            'replacement_price': '0',
        })
        self.assertEqual(response.status_code, 302)

        self.item.refresh_from_db()
        self.assertEqual(self.item.shelf_location, shelf)
        self.assertEqual(self.item.call_number, '004.4 A-12')
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.ITEM_EDIT).exists())

    def test_status_change_with_reason(self):
        from book_app.models import Item, ItemStatusLog

        self.client.post(f'/panel/items/{self.item.pk}/status/',
                         {'status': Item.Status.DAMAGED, 'reason': "Muqovasi yirtilgan"})
        self.item.refresh_from_db()

        self.assertEqual(self.item.status, Item.Status.DAMAGED)
        self.assertTrue(ItemStatusLog.objects.filter(item=self.item,
                                                     reason="Muqovasi yirtilgan").exists())

    def test_loaned_item_status_is_protected(self):
        from book_app.models import Item
        from book_app.services import change_item_status

        change_item_status(self.item, Item.Status.ON_LOAN, reason="Sinov")
        self.client.post(f'/panel/items/{self.item.pk}/status/',
                         {'status': Item.Status.AVAILABLE, 'reason': ''})

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ON_LOAN)

    def test_bulk_status_change(self):
        from book_app.models import Item

        ids = ",".join(str(item.pk) for item in self.items[:2])
        self.client.post(f'/panel/books/{self.book.pk}/items/bulk/', {
            'action': 'status', 'status': Item.Status.NOT_FOR_LOAN,
            'items': ids, 'reason': "Zalga o'tkazildi",
        })

        statuses = list(Item.objects.filter(pk__in=[i.pk for i in self.items[:2]])
                        .values_list('status', flat=True))
        self.assertEqual(statuses, [Item.Status.NOT_FOR_LOAN] * 2)
        self.items[2].refresh_from_db()
        self.assertEqual(self.items[2].status, Item.Status.AVAILABLE)

    def test_bulk_move_to_shelf(self):
        from holdings.models import ShelfLocation

        shelf = ShelfLocation.objects.create(library=self.item.library, code='D-1')
        self.client.post(f'/panel/books/{self.book.pk}/items/bulk/', {
            'action': 'move', 'shelf_location': shelf.pk,
            'items': ",".join(str(item.pk) for item in self.items),
        })

        self.item.refresh_from_db()
        self.assertEqual(self.item.shelf_location, shelf)

    def test_item_edit_requires_items_manage(self):
        """`catalog.view` bor xodim nusxani ko'radi, lekin saqlay olmaydi."""
        from user_app.models import Role
        from user_app.permissions import Perms

        viewer = make_employee(username='kuzatuvchi', password='x')
        role = Role.objects.create(name="Kuzatuvchi", permissions=[Perms.CATALOG_VIEW])
        viewer.employe_profile.current_role = role
        viewer.employe_profile.save()

        self.client.login(username=viewer.username, password='x')
        self.assertEqual(self.client.get(f'/panel/items/{self.item.pk}/').status_code, 200)
        self.assertEqual(
            self.client.post(f'/panel/items/{self.item.pk}/', {'barcode': 'X'}).status_code, 403)


class CatalogingFormTests(TestCase):
    def setUp(self):
        from core.testing import make_genre

        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')
        self.genre = make_genre("Ilmiy")

    def _payload(self, **overrides):
        data = {
            'record_type': 'TEXTBOOK',
            'title': "Diskret matematika",
            'category': self.genre.pk,
            'language': "O'zbekcha",
            'reading_mode': 'PHYSICAL',
            'publisher_name': "Fan va texnologiya",
            'series_name': "Oliy ta'lim",
            'subjects_text': "matematika, diskret tuzilmalar",
            'udc': "519.1",
            'published_year': 2023,
            'faculty': "Axborot texnologiyalari",
            'is_textbook': 'on',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_create_book_with_references(self):
        from book_app.models import Book, Publisher, Series, Subject

        response = self.client.post('/panel/books/new/', self._payload())
        self.assertEqual(response.status_code, 302)

        book = Book.objects.get(title="Diskret matematika")
        self.assertEqual(book.record_type, Book.RecordType.TEXTBOOK)
        self.assertTrue(book.is_textbook)
        self.assertEqual(book.udc, "519.1")
        # Nashriyot va turkum matndan yaratildi
        self.assertTrue(Publisher.objects.filter(name="Fan va texnologiya").exists())
        self.assertTrue(Series.objects.filter(name="Oliy ta'lim").exists())
        # Mavzular vergul bo'yicha ajratildi
        self.assertEqual(book.subjects.count(), 2)
        self.assertTrue(Subject.objects.filter(name="diskret tuzilmalar").exists())
        self.assertTrue(book.slug)

    def test_invalid_isbn_rejected(self):
        response = self.client.post('/panel/books/new/', self._payload(isbn="123"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ISBN")

    def test_valid_isbn_normalized(self):
        from book_app.models import Book

        self.client.post('/panel/books/new/', self._payload(isbn="978-9943-00-000-1"))
        self.assertEqual(Book.objects.get(title="Diskret matematika").isbn, "9789943000001")

    def test_edit_prefills_reference_names(self):
        from book_app.models import Book

        self.client.post('/panel/books/new/', self._payload())
        book = Book.objects.get(title="Diskret matematika")

        response = self.client.get(f'/panel/books/{book.pk}/edit/')
        self.assertContains(response, "Fan va texnologiya")
        self.assertContains(response, "matematika")


class HoldingsPanelTests(TestCase):
    def setUp(self):
        self.librarian = make_librarian(password='x')
        self.client.login(username=self.librarian.username, password='x')

    def test_overview_lists_references(self):
        response = self.client.get('/panel/holdings/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asosiy fond")
        self.assertContains(response, "Darslik")

    def test_add_library(self):
        from holdings.models import Library

        # `form_kind` — bo'lim diskriminatori; `kind` esa filialning turi
        self.client.post('/panel/holdings/', {
            'form_kind': 'library', 'code': 'ZAL', 'name': "O'quv zali",
            'kind': 'READING_ROOM', 'order': 20, 'is_active': 'on',
        })
        library = Library.objects.get(code='ZAL')
        self.assertEqual(library.kind, Library.Kind.READING_ROOM)

    def test_add_shelf_and_toggle(self):
        from holdings.models import Library, ShelfLocation

        library = Library.default()
        self.client.post('/panel/holdings/', {
            'form_kind': 'shelf', 'library': library.pk, 'code': 'A-1',
            'name': "1-javon", 'floor': "1-qavat", 'zone': "A", 'is_active': 'on',
        })
        shelf = ShelfLocation.objects.get(code='A-1')
        self.assertTrue(shelf.is_active)

        self.client.post(f'/panel/holdings/shelf/{shelf.pk}/toggle/')
        shelf.refresh_from_db()
        self.assertFalse(shelf.is_active)

    def test_edit_item_type(self):
        from holdings.models import ItemType

        item_type = ItemType.objects.get(code='DARSLIK')
        self.client.post(f'/panel/holdings/type/{item_type.pk}/edit/', {
            'code': 'DARSLIK', 'name': "Darslik (yangilandi)", 'description': '',
            'default_loan_days': 30, 'replacement_cost_default': '0',
            'order': 10, 'is_loanable': 'on', 'is_active': 'on',
        })
        item_type.refresh_from_db()
        self.assertEqual(item_type.name, "Darslik (yangilandi)")
        self.assertEqual(item_type.default_loan_days, 30)
