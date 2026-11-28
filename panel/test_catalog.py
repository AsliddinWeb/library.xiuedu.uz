"""Katalog CRUD'lari: ma'lumotnomalar, birlashtirish, kitob o'chirish, nusxa qo'shish."""
from datetime import timedelta

from django.test import TestCase
from django.utils.html import escape
from django.utils.timezone import now

from audit.models import ActionLog
from book_app.models import (
    Author,
    Book,
    Contributor,
    Genre,
    Item,
    Publisher,
    Rental,
    Series,
    Subject,
)
from core.testing import (
    make_author,
    make_book,
    make_copies,
    make_employee,
    make_genre,
    make_librarian,
    make_student,
)
from holdings.models import Library, ShelfLocation
from user_app.models import PatronCategory, Role
from user_app.permissions import Perms
from user_app.services import get_category, get_or_create_patron

from .resources import RESOURCES


class CatalogFixture(TestCase):
    def setUp(self):
        self.client.force_login(make_librarian())

    def staff(self, *permissions):
        user = make_employee()
        role = Role.objects.create(name=f"Rol {user.pk}", permissions=list(permissions))
        user.employe_profile.roles.add(role)
        self.client.force_login(user)


class ResourcePagesTests(CatalogFixture):
    def setUp(self):
        super().setUp()
        publisher = Publisher.objects.create(name="Fan")
        self.objects = {
            'genres': make_genre("Huquq"),
            'authors': make_author("Cho'lpon"),
            'publishers': publisher,
            'series': Series.objects.create(name="Durdonalar", publisher=publisher),
            'subjects': Subject.objects.create(name="Algoritm"),
            'categories': get_category(PatronCategory.Code.STUDENT),
        }

    def test_all_pages_open(self):
        for resource in RESOURCES:
            pk = self.objects[resource.name].pk
            urls = [resource.url(), resource.url('create'), resource.url('edit', pk),
                    resource.url('delete', pk)]
            if resource.merge:
                urls.append(resource.url('merge', pk))
            for url in urls:
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
            self.assertContains(self.client.get(resource.url()),
                                escape(str(self.objects[resource.name])))

    def test_search_and_export(self):
        for resource in RESOURCES:
            with self.subTest(resource.name):
                empty = self.client.get(resource.url(), {'q': 'zzzz-yoq'}, HTTP_HX_REQUEST='true')
                self.assertContains(empty, "topilmadi")
                export = self.client.get(resource.url(), {'export': 'csv'})
                self.assertEqual(export['Content-Type'], 'text/csv; charset=utf-8')

    def test_create(self):
        payloads = {
            'genres': {'name': 'Tibbiyot', 'order': 1, 'is_active': 'on'},
            'authors': {'full_name': 'Oybek', 'variants_text': 'Ойбек, Oibek'},
            'publishers': {'name': 'Sharq', 'city': 'Toshkent'},
            'series': {'name': 'Klassika'},
            'subjects': {'name': 'Fizika', 'kind': 'SUBJECT'},
        }
        for name, data in payloads.items():
            with self.subTest(name):
                response = self.client.post(f'/panel/{name}/new/', data)
                self.assertRedirects(response, f'/panel/{name}/', fetch_redirect_response=False)
        self.assertEqual(Author.objects.get(full_name='Oybek').name_variants, ['Ойбек', 'Oibek'])
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.BIBLIO_CREATE).exists())

    def test_save_and_add_another(self):
        response = self.client.post('/panel/publishers/new/',
                                    {'name': 'Yangi', 'save_and_new': '1'})
        self.assertRedirects(response, '/panel/publishers/new/', fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        response = self.client.post('/panel/publishers/new/',
                                    {'name': 'Boshqa', 'next': 'https://example.com/'})
        self.assertRedirects(response, '/panel/publishers/', fetch_redirect_response=False)

    def test_duplicate_genre_refused(self):
        response = self.client.post('/panel/genres/new/', {'name': ' huquq ', 'order': 0})
        self.assertContains(response, "allaqachon bor")

    def test_author_years(self):
        response = self.client.post('/panel/authors/new/', {
            'full_name': 'X', 'birth_year': 1990, 'death_year': 1900})
        self.assertFalse(Author.objects.filter(full_name='X').exists())
        self.assertContains(response, "oldin")

    def test_edit_category_rules(self):
        category = self.objects['categories']
        data = {'code': category.code, 'name': category.name, 'default_loan_days': 21,
                'loan_limit': 7, 'hold_limit': 2, 'renewals_allowed': 3, 'fine_per_day': 700,
                'debt_block_amount': 0, 'membership_months': 0, 'order': 0, 'is_active': 'on'}
        self.client.post(f'/panel/categories/{category.pk}/edit/', data)
        category.refresh_from_db()
        self.assertEqual((category.default_loan_days, category.renewals_allowed), (21, 3))
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.SETTINGS).exists())

    def test_toggle(self):
        genre = self.objects['genres']
        self.client.post(f'/panel/genres/{genre.pk}/toggle/', HTTP_HX_REQUEST='true')
        genre.refresh_from_db()
        self.assertFalse(genre.is_active)

    def test_used_record_cannot_be_deleted(self):
        author = self.objects['authors']
        make_book("Kecha va kunduz", authors=[author])
        page = self.client.get(f'/panel/authors/{author.pk}/delete/')
        self.assertContains(page, "Birlashtirish")

        self.client.post(f'/panel/authors/{author.pk}/delete/')
        self.assertTrue(Author.objects.filter(pk=author.pk).exists())

    def test_unused_record_is_deleted(self):
        author = self.objects['authors']
        self.client.post(f'/panel/authors/{author.pk}/delete/')
        self.assertFalse(Author.objects.filter(pk=author.pk).exists())

    def test_subject_cannot_become_its_own_child(self):
        parent = self.objects['subjects']
        child = Subject.objects.create(name="Saralash", parent=parent)
        self.client.post(f'/panel/subjects/{parent.pk}/edit/',
                         {'name': parent.name, 'kind': parent.kind, 'parent': child.pk})
        parent.refresh_from_db()
        self.assertIsNone(parent.parent_id)


class MergeTests(CatalogFixture):
    def merge(self, name, source, target):
        return self.client.post(f'/panel/{name}/{source.pk}/merge/', {'target': target.pk})

    def test_authors(self):
        keep = make_author("Abdulla Qodiriy")
        extra = make_author("Qodiriy A.", nationality="O'zbek")
        shared = make_book("O'tkan kunlar", authors=[keep, extra])
        other = make_book("Mehrobdan chayon", authors=[extra])

        self.merge('authors', extra, keep)

        self.assertFalse(Author.objects.filter(pk=extra.pk).exists())
        self.assertEqual(Contributor.objects.filter(book=shared).count(), 1)
        self.assertEqual(list(other.authors.all()), [keep])
        keep.refresh_from_db()
        self.assertEqual(keep.name_variants, ["Qodiriy A."])
        self.assertEqual(keep.nationality, "O'zbek")
        other.refresh_from_db()
        self.assertIn('abdulla', other.search_text)

    def test_genres_publishers_series(self):
        old_genre, new_genre = make_genre("Iqtisod"), make_genre("Iqtisodiyot")
        old_pub = Publisher.objects.create(name="Fan nashriyoti")
        new_pub = Publisher.objects.create(name="Fan")
        old_series = Series.objects.create(name="Darsliklar.", publisher=old_pub)
        new_series = Series.objects.create(name="Darsliklar")
        book = make_book("Bozor", genre=old_genre, publisher=old_pub, series=old_series)

        self.merge('genres', old_genre, new_genre)
        self.merge('publishers', old_pub, new_pub)
        old_series.refresh_from_db()
        self.assertEqual(old_series.publisher, new_pub)
        self.merge('series', old_series, new_series)

        book.refresh_from_db()
        self.assertEqual((book.category, book.publisher, book.series),
                         (new_genre, new_pub, new_series))
        self.assertEqual(Genre.objects.filter(pk=old_genre.pk).count(), 0)

    def test_subjects(self):
        old = Subject.objects.create(name="Algoritmlar")
        new = Subject.objects.create(name="Algoritm")
        book = make_book("Saralash usullari")
        book.subjects.add(old, new)

        self.merge('subjects', old, new)

        self.assertEqual(list(book.subjects.all()), [new])

    def test_merge_into_itself_does_nothing(self):
        author = make_author("Yolg'iz")
        self.merge('authors', author, author)
        self.assertTrue(Author.objects.filter(pk=author.pk).exists())


class ResourcePermissionTests(CatalogFixture):
    def test_read_only_cataloguer(self):
        author = make_author("Ko'riladigan")
        self.staff(Perms.CATALOG_VIEW)
        page = self.client.get('/panel/authors/')
        self.assertContains(page, "Ko&#x27;riladigan")
        self.assertNotContains(page, '/panel/authors/new/')
        for url in ('/panel/authors/new/', f'/panel/authors/{author.pk}/edit/',
                    f'/panel/authors/{author.pk}/delete/', f'/panel/authors/{author.pk}/merge/'):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.get('/panel/categories/').status_code, 403)

    def test_editor_without_delete_cannot_merge(self):
        author = make_author()
        self.staff(Perms.CATALOG_VIEW, Perms.CATALOG_EDIT)
        self.assertEqual(self.client.get(f'/panel/authors/{author.pk}/merge/').status_code, 403)


class BookCrudTests(CatalogFixture):
    def test_new_book_with_copies(self):
        genre = make_genre("Fan")
        self.client.post('/panel/books/new/', {
            'title': 'Yangi kitob', 'category': genre.pk, 'record_type': 'MONOGRAPH',
            'reading_mode': 'PHYSICAL', 'language': "O'zbek", 'is_active': 'on',
            'initial_copies': '3'})
        book = Book.objects.get(title='Yangi kitob')
        self.assertEqual(Item.objects.filter(book=book).count(), 3)

    def test_book_with_history_is_kept(self):
        book = make_book("Tarixli")
        item = make_copies(book, 1)[0]
        Rental.objects.create(copy=item, patron=get_or_create_patron(make_student()),
                              borrowed_date=now().date() - timedelta(days=9),
                              return_date=now().date())

        page = self.client.get(f'/panel/books/{book.pk}/delete/')
        self.assertContains(page, "Nofaol qilish")
        self.client.post(f'/panel/books/{book.pk}/delete/')
        self.assertTrue(Book.objects.filter(pk=book.pk).exists())

        self.client.post(f'/panel/books/{book.pk}/delete/', {'deactivate': '1'})
        book.refresh_from_db()
        self.assertFalse(book.is_active)

    def test_book_without_history_is_deleted(self):
        book = make_book("Xato yozuv", copies=2)
        self.client.post(f'/panel/books/{book.pk}/delete/')
        self.assertFalse(Book.objects.filter(pk=book.pk).exists())

    def test_copy_details(self):
        book = make_book("Batafsil")
        library = Library.objects.create(code='F2', name="Ikkinchi filial")
        shelf = ShelfLocation.objects.create(library=library, code='B-1', name="B javon")
        self.client.post(f'/panel/books/{book.pk}/copies/add/', {
            'quantity': 2, 'shelf_location': shelf.pk, 'price': '45 000', 'source': 'GIFT',
            'reading_room': '1'})
        items = Item.objects.filter(book=book)
        self.assertEqual(items.count(), 2)
        item = items.first()
        self.assertEqual((item.library, item.price, item.acquisition_source, item.status),
                         (library, 45000, 'GIFT', Item.Status.NOT_FOR_LOAN))

    def test_bad_copy_input(self):
        book = make_book("Xato narx")
        other = Library.objects.create(code='F3', name="Uchinchi")
        shelf = ShelfLocation.objects.create(
            library=Library.objects.create(code='F4', name="To'rtinchi"), code='C', name="C")
        for data in ({'price': 'qimmat'}, {'price': 'Infinity'},
                     {'library': other.pk, 'shelf_location': shelf.pk}):
            self.client.post(f'/panel/books/{book.pk}/copies/add/', {'quantity': 1, **data})
        self.assertFalse(Item.objects.filter(book=book).exists())

    def test_filters_from_reference_pages(self):
        author = make_author("Saralanadigan")
        make_book("Uniki", authors=[author])
        make_book("Boshqaniki")
        response = self.client.get('/panel/books/', {'author': author.pk})
        self.assertContains(response, "Uniki")
        self.assertNotContains(response, "Boshqaniki")
        self.assertEqual(self.client.get('/panel/books/', {'category': 'x', 'author': "1'"})
                         .status_code, 200)

    def test_book_csv(self):
        make_book("Eksport kitobi", copies=1)
        response = self.client.get('/panel/books/', {'export': 'csv'})
        self.assertIn("Eksport kitobi", response.content.decode('utf-8'))
