"""
Katalog va fond testlari (P2).

Asosiy e'tibor: nusxa (`Item`) holat mashinasi, shtrix-kod, fond ko'rsatkichlari
va hissadorlar (rol bilan).
"""
from django.test import TestCase

from audit.models import ActionLog
from core.testing import make_book, make_genre, make_librarian, make_student
from holdings.models import ItemType, Library, ShelfLocation
from user_app.services import get_or_create_patron

from .models import Author, Book, Contributor, Item, ItemStatusLog, Publisher, Series, Subject
from .services import (
    change_item_status,
    create_items,
    next_barcode,
    recalc_book_counters,
    withdraw_item,
)


class HoldingsSeedTests(TestCase):
    """Migratsiya seed qilgan ma'lumotnomalar testda ham mavjud bo'lishi kerak."""

    def test_default_library_and_types_exist(self):
        self.assertIsNotNone(Library.default())
        self.assertIsNotNone(ItemType.default())
        self.assertTrue(ItemType.objects.filter(code='DARSLIK').exists())

    def test_shelf_directions(self):
        shelf = ShelfLocation.objects.create(
            library=Library.default(), code='B-14', name="14-javon",
            floor="2-qavat", zone="B-zona")
        self.assertIn("2-qavat", shelf.directions)

        shelf.navigation_hint = "Kirishdan o'ngda, 3-qator"
        self.assertEqual(shelf.directions, "Kirishdan o'ngda, 3-qator")


class ItemCreationTests(TestCase):
    def setUp(self):
        self.book = make_book("Algoritmlar")

    def test_create_items_assigns_barcode_and_location(self):
        items = create_items(self.book, 3)

        self.assertEqual(len(items), 3)
        for item in items:
            self.assertTrue(item.barcode.startswith('XIU'))
            self.assertIsNotNone(item.library_id)
            self.assertIsNotNone(item.item_type_id)
            self.assertEqual(item.status, Item.Status.AVAILABLE)
            self.assertTrue(item.is_available)

        # Shtrix-kodlar takrorlanmaydi
        self.assertEqual(len({i.barcode for i in items}), 3)

    def test_inventory_numbers_increment_per_book(self):
        create_items(self.book, 2)
        numbers = list(Item.objects.filter(book=self.book)
                       .values_list('inventory_number', flat=True))
        self.assertEqual(sorted(numbers), ['INV-1', 'INV-2'])

    def test_next_barcode_continues_sequence(self):
        create_items(self.book, 1)
        first = Item.objects.get(book=self.book).barcode
        self.assertEqual(int(next_barcode()[3:]), int(first[3:]) + 1)

    def test_counters_updated_on_create(self):
        create_items(self.book, 4)
        self.book.refresh_from_db()
        self.assertEqual(self.book.items_count, 4)
        self.assertEqual(self.book.available_count, 4)

    def test_call_number_suggested_from_udc(self):
        self.book.udc = "004.42"
        self.book.author_sign = "A-56"
        self.book.save()

        item = create_items(self.book, 1)[0]
        self.assertEqual(item.call_number, "004.42 A-56")


class ItemStatusTests(TestCase):
    def setUp(self):
        self.book = make_book("Fond kitobi")
        self.item = create_items(self.book, 1)[0]
        self.librarian = make_librarian()

    def test_status_change_logs_and_syncs_availability(self):
        changed, _ = change_item_status(self.item, Item.Status.DAMAGED,
                                        reason="Muqovasi yirtilgan", by=self.librarian)
        self.item.refresh_from_db()

        self.assertTrue(changed)
        self.assertEqual(self.item.status, Item.Status.DAMAGED)
        self.assertFalse(self.item.is_available)

        log = ItemStatusLog.objects.filter(item=self.item).first()
        self.assertEqual(log.to_status, Item.Status.DAMAGED)
        self.assertEqual(log.changed_by, self.librarian)
        self.assertIn("yirtilgan", log.reason)

    def test_status_change_updates_book_counters(self):
        create_items(self.book, 2)
        change_item_status(self.item, Item.Status.LOST, reason="Yo'qolgan")

        self.book.refresh_from_db()
        self.assertEqual(self.book.items_count, 3)
        self.assertEqual(self.book.available_count, 2)

    def test_same_status_is_noop(self):
        changed, _ = change_item_status(self.item, Item.Status.AVAILABLE)
        self.assertFalse(changed)
        self.assertEqual(ItemStatusLog.objects.filter(item=self.item).count(), 1)  # faqat yaratilish

    def test_withdraw_sets_date_and_audit(self):
        withdraw_item(self.item, reason="Eskirgan", by=self.librarian)
        self.item.refresh_from_db()

        self.assertEqual(self.item.status, Item.Status.WITHDRAWN)
        self.assertIsNotNone(self.item.withdrawn_on)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.ITEM_WITHDRAW).exists())

    def test_not_loanable_item_type_blocks_loan(self):
        davriy = ItemType.objects.get(code='DAVRIY')
        self.item.item_type = davriy
        self.item.save()
        self.assertFalse(self.item.is_loanable)

    def test_location_text(self):
        self.assertIn("Asosiy fond", self.item.location_text)


class CirculationSyncTests(TestCase):
    """Ijara/qaytarish nusxa holatini to'g'ri o'zgartirishi kerak."""

    def setUp(self):
        from circulation import services as circ
        self.circ = circ
        self.book = make_book("Ijara kitobi")
        self.item = create_items(self.book, 1)[0]
        self.patron = get_or_create_patron(make_student(username='talaba-fond'))

    def test_loan_and_return_move_item_status(self):
        req, _ = self.circ.create_rental_request(self.patron, self.book)
        rental, _ = self.circ.approve_request(req)

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ON_LOAN)
        self.assertFalse(self.item.is_available)

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_count, 0)

        self.circ.return_rental(rental)
        self.item.refresh_from_db()
        self.book.refresh_from_db()

        self.assertEqual(self.item.status, Item.Status.AVAILABLE)
        self.assertEqual(self.book.available_count, 1)
        self.assertEqual(self.item.loan_count, 1)

    def test_withdrawn_item_is_not_offered(self):
        withdraw_item(self.item, reason="Yo'qolgan")
        req, msg = self.circ.create_rental_request(self.patron, self.book)
        self.assertIsNone(req)
        self.assertIn("nusxa yo'q", msg.lower())


class CatalogModelTests(TestCase):
    def setUp(self):
        self.book = make_book("Kataloglash")

    def test_contributors_with_roles(self):
        author = Author.objects.create(full_name="Abdulla Qodiriy")
        translator = Author.objects.create(full_name="Ivan Ivanov")

        Contributor.objects.create(book=self.book, author=author,
                                   role=Contributor.Role.AUTHOR, order=0)
        Contributor.objects.create(book=self.book, author=translator,
                                   role=Contributor.Role.TRANSLATOR, order=1)

        grouped = self.book.contributors_by_role
        self.assertEqual([a.full_name for a in grouped["Muallif"]], ["Abdulla Qodiriy"])
        self.assertEqual([a.full_name for a in grouped["Tarjimon"]], ["Ivan Ivanov"])
        # Eski `authors` M2M ham ishlayveradi (through orqali)
        self.assertEqual(self.book.authors.count(), 2)

    def test_authors_set_still_works(self):
        """Eski kod `book.authors.set([...])` qilsa ham ishlashi kerak."""
        author = Author.objects.create(full_name="Test Muallif")
        self.book.authors.set([author])
        self.assertEqual(Contributor.objects.filter(book=self.book).count(), 1)

    def test_bibliographic_fields(self):
        publisher = Publisher.objects.create(name="Yangi asr avlodi", city="Toshkent")
        series = Series.objects.create(name="Jahon adabiyoti")
        subject = Subject.objects.create(name="Dasturlash", kind=Subject.Kind.SUBJECT)

        book = Book.objects.create(
            title="Python dasturlash", category=make_genre(),
            record_type=Book.RecordType.TEXTBOOK, publisher=publisher, series=series,
            udc="004.43", author_sign="P-99", isbn="9789943000001",
            place_of_publication="Toshkent", edition_statement="2-nashr",
            is_textbook=True, faculty="Axborot texnologiyalari",
        )
        book.subjects.add(subject)

        self.assertEqual(book.get_record_type_display(), "Darslik")
        self.assertEqual(book.publisher.name, "Yangi asr avlodi")
        self.assertIn(subject, book.subjects.all())

    def test_author_life_years(self):
        author = Author.objects.create(full_name="A. Qodiriy", birth_year=1894, death_year=1938)
        self.assertEqual(author.life_years, "1894–1938")

    def test_recalc_counters(self):
        create_items(self.book, 2)
        Book.objects.filter(pk=self.book.pk).update(items_count=0, available_count=0)

        recalc_book_counters(self.book)
        self.book.refresh_from_db()
        self.assertEqual(self.book.items_count, 2)


class SeedItemsCommandTests(TestCase):
    """`seed_items` — nusxasi yo'q kitoblarga fond yaratish (bir martalik ko'chirish)."""

    def setUp(self):
        from django.core.management import call_command
        self.call = call_command
        self.physical = make_book("Qog'oz kitob")                       # nusxasiz
        self.with_items = make_book("Nusxasi bor kitob")
        create_items(self.with_items, 2)
        self.digital = make_book("Raqamli kitob", reading_mode=Book.ReadingMode.DIGITAL)

    def test_creates_one_item_per_book_by_default(self):
        self.call('seed_items', verbosity=0)

        self.assertEqual(Item.objects.filter(book=self.physical).count(), 1)
        item = Item.objects.get(book=self.physical)
        self.assertTrue(item.barcode.startswith('XIU'))
        self.assertEqual(item.status, Item.Status.AVAILABLE)
        self.assertIsNotNone(item.library_id)
        self.assertIsNotNone(item.item_type_id)

    def test_skips_books_that_already_have_items(self):
        self.call('seed_items', verbosity=0)
        self.assertEqual(Item.objects.filter(book=self.with_items).count(), 2)

    def test_skips_digital_books_by_default(self):
        self.call('seed_items', verbosity=0)
        self.assertEqual(Item.objects.filter(book=self.digital).count(), 0)

    def test_modes_all_includes_digital(self):
        self.call('seed_items', modes='ALL', verbosity=0)
        self.assertEqual(Item.objects.filter(book=self.digital).count(), 1)

    def test_per_book_option(self):
        self.call('seed_items', per_book=3, verbosity=0)

        items = Item.objects.filter(book=self.physical)
        self.assertEqual(items.count(), 3)
        self.assertEqual(sorted(items.values_list('inventory_number', flat=True)),
                         ['INV-1', 'INV-2', 'INV-3'])

    def test_counters_updated(self):
        self.call('seed_items', per_book=2, verbosity=0)
        self.physical.refresh_from_db()
        self.assertEqual(self.physical.items_count, 2)
        self.assertEqual(self.physical.available_count, 2)

    def test_barcodes_are_unique_and_continue_sequence(self):
        before = set(Item.objects.values_list('barcode', flat=True))
        self.call('seed_items', verbosity=0)
        after = set(Item.objects.values_list('barcode', flat=True))

        self.assertEqual(len(after), Item.objects.count())   # dublikat yo'q
        self.assertTrue(after > before)

    def test_idempotent(self):
        self.call('seed_items', verbosity=0)
        count = Item.objects.count()
        self.call('seed_items', verbosity=0)
        self.assertEqual(Item.objects.count(), count)

    def test_dry_run_writes_nothing(self):
        count = Item.objects.count()
        self.call('seed_items', dry_run=True, verbosity=0)
        self.assertEqual(Item.objects.count(), count)


# =============================================================================
#  P5 — Transliteratsiya va qidiruv
# =============================================================================

class TransliterationTests(TestCase):
    """Kirill va lotin yozuv bir ko'rinishga kelishi kerak."""

    def test_fold_matches_both_scripts(self):
        from book_app.translit import fold

        pairs = [
            ("Ўткан кунлар", "O'tkan kunlar"),
            ("Алгоритмлар", "Algoritmlar"),
            ("Чўлпон", "Cho'lpon"),
            ("Ғафур Ғулом", "G'afur G'ulom"),
            ("Машина ўрганиш", "Mashina o'rganish"),
            ("Ҳаёт", "Hayot"),
        ]
        for cyrillic, latin in pairs:
            with self.subTest(cyrillic=cyrillic):
                self.assertEqual(fold(cyrillic), fold(latin))

    def test_fold_handles_k_q_confusion(self):
        """Eski kirill yozuvlarda "к" ham k, ham q o'rnida ishlatilgan."""
        from book_app.translit import fold
        self.assertEqual(fold("Кодирий"), fold("Qodiriy"))

    def test_apostrophe_variants_are_unified(self):
        from book_app.translit import fold
        self.assertEqual(fold("O‘tkan"), fold("O'tkan"))
        self.assertEqual(fold("Oʻtkan"), fold("O`tkan"))

    def test_normalize_strips_punctuation(self):
        from book_app.translit import normalize
        self.assertEqual(normalize("Algoritmlar: asoslari!"), "algoritmlar asoslari")

    def test_to_cyrillic(self):
        from book_app.translit import to_cyrillic
        self.assertEqual(to_cyrillic("kitob"), "китоб")

    def test_empty_input(self):
        from book_app.translit import fold, normalize, to_cyrillic, to_latin
        for func in (fold, normalize, to_cyrillic, to_latin):
            self.assertEqual(func(""), "")
            self.assertEqual(func(None), "")


class SearchIndexTests(TestCase):
    """Indeks avtomatik to'ladi va yangilanadi."""

    def test_index_built_on_save(self):
        book = make_book("Algoritmlar asoslari")
        book.refresh_from_db()
        self.assertIn("algoritmlar", book.search_text)

    def test_index_includes_author(self):
        book = make_book("O'tkan kunlar")
        author = Author.objects.create(full_name="Abdulla Qodiriy")
        Contributor.objects.create(book=book, author=author)

        book.refresh_from_db()
        self.assertIn("kodiriy", book.search_text)   # fold: q -> k

    def test_index_includes_subject_and_publisher(self):
        from book_app.models import Publisher

        publisher = Publisher.objects.create(name="Yangi asr avlodi")
        subject = Subject.objects.create(name="Dasturlash")
        book = make_book("Python", publisher=publisher)
        book.subjects.add(subject)

        book.refresh_from_db()
        self.assertIn("dasturlash", book.search_text)
        self.assertIn("yangi asr", book.search_text)

    def test_index_updates_when_title_changes(self):
        book = make_book("Eski sarlavha")
        book.title = "Butunlay boshqa nom"
        book.save()

        book.refresh_from_db()
        # Indeks `fold()` dan o'tgan: "boshqa" -> "boshka" (q va k birlashtiriladi)
        self.assertIn("butunlay boshka", book.search_text)
        self.assertNotIn("eski sarlavha", book.search_text)

    def test_rebuild_command(self):
        from django.core.management import call_command

        book = make_book("Indekssiz kitob")
        Book.objects.filter(pk=book.pk).update(search_text='')

        call_command('rebuild_search', verbosity=0)
        book.refresh_from_db()
        self.assertIn("indekssiz", book.search_text)


class SearchQueryTests(TestCase):
    """Qidiruvning o'zi: kirill, xato yozuv, muallif, mavzu."""

    def setUp(self):
        self.algo = make_book("Algoritmlar asoslari")
        self.ml = make_book("Mashina o'rganish")
        self.novel = make_book("O'tkan kunlar")
        Contributor.objects.create(
            book=self.novel, author=Author.objects.create(full_name="Abdulla Qodiriy"))

    def _titles(self, query):
        from book_app.search import search_books
        return [book.title for book in search_books(Book.objects.all(), query)]

    def test_exact_match(self):
        self.assertIn("Algoritmlar asoslari", self._titles("algoritmlar"))

    def test_cyrillic_query_finds_latin_record(self):
        """Talaba kirillda yozadi — lotincha yozuv topilishi kerak."""
        self.assertIn("Mashina o'rganish", self._titles("Машина"))

    def test_latin_query_finds_record_written_in_cyrillic(self):
        cyrillic_book = make_book("Ўткан кунлар")
        self.assertIn("Ўткан кунлар", self._titles("o'tkan"))
        self.assertIsNotNone(cyrillic_book.pk)

    def test_typo_is_forgiven(self):
        self.assertIn("Algoritmlar asoslari", self._titles("algaritm"))

    def test_search_by_author(self):
        titles = self._titles("qodiriy")
        self.assertIn("O'tkan kunlar", titles)

    def test_author_found_by_cyrillic_spelling(self):
        self.assertIn("O'tkan kunlar", self._titles("Кодирий"))

    def test_empty_query_returns_everything(self):
        from book_app.search import search_books
        self.assertEqual(search_books(Book.objects.all(), "").count(),
                         Book.objects.count())

    def test_nonsense_returns_nothing(self):
        self.assertEqual(self._titles("zzzqqqxxx"), [])

    def test_suggest_limits_results(self):
        from book_app.search import suggest
        self.assertLessEqual(len(list(suggest(Book.objects.all(), "a", limit=2))), 2)


class OpacCatalogViewTests(TestCase):
    """OPAC katalogi: qidiruv, fasetlar, HTMX."""

    def assertShows(self, response, text):
        """Sahifada ko'rinishini tekshiradi (apostrof HTML-escape qilinadi)."""
        from django.utils.html import escape
        self.assertContains(response, escape(text))

    def assertHides(self, response, text):
        from django.utils.html import escape
        self.assertNotContains(response, escape(text))

    def setUp(self):
        self.user = make_student(username='talaba-opac', password='x')
        self.client.login(username=self.user.username, password='x')

        self.digital = make_book("Raqamli kitob", electronic_version='ebooks/x.pdf')
        self.paper = make_book("Qog'oz kitob")
        create_items(self.paper, 2)
        self.hidden = make_book("Nofaol kitob", is_active=False)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get('/books/').status_code, 302)

    def test_lists_active_books_only(self):
        response = self.client.get('/books/')
        self.assertShows(response, "Raqamli kitob")
        self.assertHides(response, "Nofaol kitob")

    def test_search_finds_by_cyrillic(self):
        make_book("Mashina o'rganish")
        response = self.client.get('/books/', {'q': 'Машина'})
        self.assertShows(response, "Mashina o'rganish")

    def test_search_forgives_typo(self):
        make_book("Algoritmlar asoslari")
        response = self.client.get('/books/', {'q': 'algaritm'})
        self.assertShows(response, "Algoritmlar asoslari")

    def test_format_facet_digital(self):
        response = self.client.get('/books/', {'format': 'digital'})
        self.assertShows(response, "Raqamli kitob")
        self.assertHides(response, "Qog'oz kitob")

    def test_format_facet_physical(self):
        response = self.client.get('/books/', {'format': 'physical'})
        self.assertShows(response, "Qog'oz kitob")
        self.assertHides(response, "Raqamli kitob")

    def test_available_facet(self):
        from book_app.models import Item
        from book_app.services import change_item_status

        response = self.client.get('/books/', {'available': '1'})
        self.assertShows(response, "Qog'oz kitob")

        for item in Item.objects.filter(book=self.paper):
            change_item_status(item, Item.Status.ON_LOAN, reason="Sinov")

        response = self.client.get('/books/', {'available': '1'})
        self.assertHides(response, "Qog'oz kitob")

    def test_year_range_facet(self):
        make_book("Eski nashr", published_year=1990)
        make_book("Yangi nashr", published_year=2024)

        response = self.client.get('/books/', {'year_from': '2000'})
        self.assertShows(response, "Yangi nashr")
        self.assertHides(response, "Eski nashr")

    def test_category_facet(self):
        from core.testing import make_genre
        genre = make_genre("Ilmiy-opac")
        make_book("Ilmiy kitob", genre=genre)

        response = self.client.get('/books/', {'category': genre.pk})
        self.assertShows(response, "Ilmiy kitob")
        self.assertHides(response, "Raqamli kitob")

    def test_sorting_by_title(self):
        response = self.client.get('/books/', {'sort': 'title'})
        self.assertEqual(response.status_code, 200)

    def test_htmx_returns_partial(self):
        response = self.client.get('/books/', {'q': 'kitob'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<!doctype html>")
        self.assertShows(response, "Raqamli kitob")

    def test_empty_result_message(self):
        response = self.client.get('/books/', {'q': 'zzzqqqxxx'})
        self.assertShows(response, "topilmadi")
