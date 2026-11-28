"""CSV orqali kitob import qilish."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from audit.models import ActionLog
from book_app.models import Book, Item
from core.testing import make_book, make_employee, make_librarian
from user_app.models import Role
from user_app.permissions import Perms

HEADER = "Sarlavha;Mualliflar;Katalog;Nashriyot;Yil;ISBN;Nusxa soni;Narx\n"


class ImportTests(TestCase):
    def setUp(self):
        self.client.force_login(make_librarian())

    def upload(self, text, *, encoding='utf-8-sig', name='kitoblar.csv'):
        data = text if isinstance(text, bytes) else text.encode(encoding)
        return self.client.post('/panel/import/csv/',
                                {'file': SimpleUploadedFile(name, data, 'text/csv')})

    def confirm(self, **data):
        return self.client.post('/panel/import/csv/confirm/', data)

    def test_template_download(self):
        response = self.client.get('/panel/import/', {'template': '1'})
        body = response.content.decode('utf-8-sig')
        self.assertTrue(body.startswith("Sarlavha;Mualliflar;Katalog"))
        # Namuna o'zi ham import qilinadigan bo'lsin
        self.assertContains(self.upload(response.content), "Qo'shiladi")

    def test_preview_writes_nothing(self):
        response = self.upload(HEADER + "Yangi;A. Muallif;Fan;Sharq;2020;;2;1000\n")
        self.assertEqual(response.context['counts']['new'], 1)
        self.assertFalse(Book.objects.exists())

    def test_confirm_creates_books_authors_and_copies(self):
        self.upload(HEADER + "Fizika;Aliyev A., Valiyev B.;Aniq fanlar;Sharq;2020;"
                             "978-9943-00-000-1;3;45 000\n")
        self.confirm()

        book = Book.objects.get()
        self.assertEqual(book.authors.count(), 2)
        self.assertEqual((book.category.name, book.publisher.name, book.isbn),
                         ('Aniq fanlar', 'Sharq', '9789943000001'))
        self.assertEqual(Item.objects.filter(book=book, price=45000).count(), 3)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.IMPORT).exists())

    def test_bad_rows_are_skipped(self):
        response = self.upload(
            HEADER + ";x;Fan;;;;;\nTo'g'ri;;Fan;;;;;\nYomon yil;;Fan;;abc;123;500;qimmat\n")
        self.assertEqual(response.context['counts']['broken'], 2)
        self.confirm()
        self.assertEqual(list(Book.objects.values_list('title', flat=True)), ["To'g'ri"])

    def test_existing_book_gets_copies_only_when_asked(self):
        book = make_book("Bor kitob", published_year=2019)
        row = HEADER + "Bor kitob;;Fan;;2019;;2;\n"

        self.upload(row)
        self.confirm()
        self.assertEqual(Item.objects.count(), 0)

        self.upload(row)
        self.confirm(add_copies='1')
        self.assertEqual(Item.objects.filter(book=book).count(), 2)
        self.assertEqual(Book.objects.count(), 1)

    def test_duplicate_rows_inside_file(self):
        response = self.upload(HEADER + "Takror;;Fan;;2000;;1;\n" * 2)
        self.assertEqual(response.context['counts'], {
            'total': 2, 'new': 1, 'existing': 0, 'broken': 1})

    def test_comma_separated_cyrillic_excel(self):
        text = "Sarlavha,Katalog\nЎтган кунлар,Адабиёт\n"
        self.upload(text)
        self.confirm()
        self.assertEqual(Book.objects.get().title, "Ўтган кунлар")

    def test_unreadable_files(self):
        for data, message in ((b'', "bo&#x27;sh"), (b'PK\x03\x04xlsx', "xlsx"),
                              (b'Ism;Familiya\nA;B\n', "majburiy ustun"),
                              (HEADER.encode(), "boshqa ma")):
            with self.subTest(message):
                self.assertContains(self.upload(data), message)

    def test_confirm_twice_imports_once(self):
        self.upload(HEADER + "Bir marta;;Fan;;;;1;\n")
        self.confirm()
        self.confirm()
        self.assertEqual(Item.objects.count(), 1)

    def test_importer_without_item_permission_adds_no_copies(self):
        user = make_employee()
        role = Role.objects.create(name="Import",
                                   permissions=[Perms.CATALOG_VIEW, Perms.CATALOG_IMPORT])
        user.employe_profile.roles.add(role)
        self.client.force_login(user)

        self.upload(HEADER + "Nusxasiz;;Fan;;;;5;\n")
        self.confirm()

        self.assertEqual((Book.objects.count(), Item.objects.count()), (1, 0))
