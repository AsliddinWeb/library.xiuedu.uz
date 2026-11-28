from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from book_app.models import Book, Genre
from core.testing import make_book, make_employee, make_librarian, make_student, make_teacher
from reading.models import ReadingHistory
from user_app.models import User

from . import services
from .models import Favorite, Review, Shelf


class ReviewTests(TestCase):
    def setUp(self):
        g = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=g)
        self.user = User.objects.create(username='u', user_type='STUDENT')

    def test_submit_review_pending(self):
        ok, _ = services.submit_review(self.user, self.book, 4, 'yaxshi')
        self.assertTrue(ok)
        review = Review.objects.get(user=self.user, book=self.book)
        self.assertFalse(review.is_approved)
        self.book.refresh_from_db()
        self.assertEqual(self.book.rating_count, 0)  # hali tasdiqlanmagan

    def test_approve_updates_rating(self):
        services.submit_review(self.user, self.book, 4, '')
        review = Review.objects.get(user=self.user, book=self.book)
        services.approve_review(review)
        self.book.refresh_from_db()
        self.assertEqual(float(self.book.avg_rating), 4.0)
        self.assertEqual(self.book.rating_count, 1)

    def test_invalid_rating(self):
        ok, _ = services.submit_review(self.user, self.book, 9, '')
        self.assertIsNone(ok)

    def test_favorite_toggle(self):
        self.assertTrue(services.toggle_favorite(self.user, self.book))
        self.assertTrue(Favorite.objects.filter(user=self.user, book=self.book).exists())
        self.assertFalse(services.toggle_favorite(self.user, self.book))
        self.assertFalse(Favorite.objects.filter(user=self.user, book=self.book).exists())


class HtmlAssertsMixin:
    """Bazadan kelgan apostrofli matn HTML-escape qilinadi (shablon literali — yo'q)."""

    def assertShows(self, response, text):
        self.assertContains(response, escape(text))

    def assertHides(self, response, text):
        self.assertNotContains(response, escape(text))


class ShelfServiceTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.teacher = make_teacher()
        self.staff = make_employee()
        self.librarian = make_librarian()
        self.book = make_book("Algoritmlar")

    def _shelf(self, owner, name="Ro'yxat", **fields):
        shelf, message = services.create_shelf(owner, name, **fields)
        self.assertIsNotNone(shelf, message)
        return shelf

    def test_student_shelf_is_always_private(self):
        shelf = self._shelf(self.student, visibility=Shelf.Visibility.PUBLIC, is_official=True)
        self.assertEqual(shelf.visibility, Shelf.Visibility.PRIVATE)
        self.assertFalse(shelf.is_official)

    def test_teacher_can_publish_but_not_mark_official(self):
        shelf = self._shelf(self.teacher, visibility=Shelf.Visibility.PUBLIC, is_official=True)
        self.assertEqual(shelf.visibility, Shelf.Visibility.PUBLIC)
        self.assertFalse(shelf.is_official)

    def test_librarian_can_mark_official(self):
        shelf = self._shelf(self.librarian, visibility=Shelf.Visibility.PUBLIC, is_official=True)
        self.assertTrue(shelf.is_official)

    def test_duplicate_and_empty_names_rejected(self):
        self._shelf(self.student, "Kurs ishi")
        self.assertIsNone(services.create_shelf(self.student, "kurs ISHI")[0])
        self.assertIsNone(services.create_shelf(self.student, "   ")[0])
        # Boshqa foydalanuvchida shu nom bo'lishi mumkin
        self._shelf(self.teacher, "Kurs ishi")

    def test_shelf_limit(self):
        with mock.patch.object(services, 'MAX_SHELVES_PER_USER', 1):
            self._shelf(self.student, "Birinchi")
            self.assertIsNone(services.create_shelf(self.student, "Ikkinchi")[0])

    def test_cyrillic_name_gets_latin_slug(self):
        shelf = self._shelf(self.student, "Курс иши")
        self.assertTrue(shelf.slug.startswith('kurs-ishi-'), shelf.slug)

    def test_toggle_item(self):
        shelf = self._shelf(self.student)
        self.assertTrue(services.toggle_shelf_item(shelf, self.book)[0])
        self.assertEqual(shelf.items.count(), 1)
        self.assertFalse(services.toggle_shelf_item(shelf, self.book)[0])
        self.assertEqual(shelf.items.count(), 0)

    def test_items_keep_order_of_adding(self):
        shelf = self._shelf(self.student)
        second = make_book("Ikkinchi")
        services.add_to_shelf(shelf, self.book)
        services.add_to_shelf(shelf, second)
        self.assertEqual([i.book for i in shelf.items.all()], [self.book, second])

    def test_private_shelf_is_owner_only(self):
        shelf = self._shelf(self.student)
        self.assertTrue(services.can_view_shelf(self.student, shelf))
        for other in (self.teacher, self.librarian):
            self.assertFalse(services.can_view_shelf(other, shelf))
            self.assertFalse(services.can_edit_shelf(other, shelf))

    def test_staff_shelf_hidden_from_students(self):
        shelf = self._shelf(self.teacher, visibility=Shelf.Visibility.STAFF)
        self.assertTrue(services.can_view_shelf(self.staff, shelf))
        self.assertFalse(services.can_view_shelf(self.student, shelf))
        self.assertIn(shelf, services.public_shelves(self.staff))
        self.assertNotIn(shelf, services.public_shelves(self.student))

    def test_curator_edits_published_shelf_only_others_cannot(self):
        shelf = self._shelf(self.teacher, visibility=Shelf.Visibility.PUBLIC)
        self.assertTrue(services.can_edit_shelf(self.librarian, shelf))
        self.assertFalse(services.can_edit_shelf(self.student, shelf))
        self.assertFalse(services.can_edit_shelf(self.staff, shelf))


class ShelfViewTests(HtmlAssertsMixin, TestCase):
    def setUp(self):
        self.owner = make_student()
        self.other = make_student()
        self.librarian = make_librarian()
        self.book = make_book("Algoritmlar asoslari")
        self.shelf, _ = services.create_shelf(self.owner, "Shaxsiy to'plam")
        services.add_to_shelf(self.shelf, self.book)
        self.client.force_login(self.owner)

    def _url(self, name, *args):
        return reverse(f'engagement:{name}', args=args)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self._url('shelf_list')).status_code, 302)

    def test_list_shows_own_and_official_but_not_others_private(self):
        official, _ = services.create_shelf(
            self.librarian, "Yil kitoblari", visibility=Shelf.Visibility.PUBLIC, is_official=True)
        services.add_to_shelf(official, self.book)
        services.create_shelf(self.other, "Begona ro'yxat")
        response = self.client.get(self._url('shelf_list'))
        self.assertShows(response, "Shaxsiy to'plam")
        self.assertShows(response, "Yil kitoblari")
        self.assertHides(response, "Begona ro'yxat")

    def test_detail_shows_citation(self):
        response = self.client.get(self.shelf.get_absolute_url())
        self.assertShows(response, "Algoritmlar asoslari")
        self.assertContains(response, "Adabiyotlar ro'yxati")

    def test_private_detail_is_404_for_others(self):
        for user in (self.other, self.librarian):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.shelf.get_absolute_url()).status_code, 404)

    def test_create_ignores_visibility_from_student(self):
        response = self.client.post(self._url('shelf_create'),
                                    {'name': "Yangi", 'visibility': 'PUBLIC', 'is_official': 'on'})
        shelf = Shelf.objects.get(owner=self.owner, name="Yangi")
        self.assertRedirects(response, shelf.get_absolute_url())
        self.assertEqual(shelf.visibility, Shelf.Visibility.PRIVATE)
        self.assertFalse(shelf.is_official)

    def test_edit_rejects_duplicate_name(self):
        services.create_shelf(self.owner, "Band nom")
        response = self.client.post(self._url('shelf_edit', self.shelf.slug), {'name': "Band nom"})
        self.assertShows(response, "Bunday nomli ro'yxat bor.")
        self.shelf.refresh_from_db()
        self.assertEqual(self.shelf.name, "Shaxsiy to'plam")

    def test_curator_edit_keeps_owner(self):
        teacher = make_teacher()
        shelf, _ = services.create_shelf(teacher, "Ochiq", visibility=Shelf.Visibility.PUBLIC)
        self.client.force_login(self.librarian)
        self.client.post(self._url('shelf_edit', shelf.slug),
                         {'name': "Ochiq (tahrir)", 'visibility': 'PUBLIC'})
        shelf.refresh_from_db()
        self.assertEqual((shelf.name, shelf.owner), ("Ochiq (tahrir)", teacher))

    def test_stranger_cannot_change_shelf(self):
        self.client.force_login(self.other)
        for name, args in (('shelf_edit', [self.shelf.slug]),
                           ('shelf_delete', [self.shelf.slug]),
                           ('shelf_remove_item', [self.shelf.slug, self.book.pk]),
                           ('shelf_item_note', [self.shelf.slug, self.book.pk]),
                           ('shelf_toggle', [self.book.pk, self.shelf.slug])):
            with self.subTest(name):
                self.assertEqual(self.client.post(self._url(name, *args)).status_code, 404)
        self.assertEqual(self.shelf.items.count(), 1)

    def test_delete_needs_post(self):
        url = self._url('shelf_delete', self.shelf.slug)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Shelf.objects.filter(pk=self.shelf.pk).exists())

    def test_note_and_remove(self):
        self.client.post(self._url('shelf_item_note', self.shelf.slug, self.book.pk),
                         {'note': "2-bob"})
        self.assertEqual(self.shelf.items.get().note, "2-bob")
        self.client.post(self._url('shelf_remove_item', self.shelf.slug, self.book.pk))
        self.assertEqual(self.shelf.items.count(), 0)

    def test_picker_lists_only_own_shelves(self):
        services.create_shelf(self.other, "Begona ro'yxat")
        response = self.client.get(self._url('shelf_picker', self.book.pk))
        self.assertShows(response, "Shaxsiy to'plam")
        self.assertHides(response, "Begona ro'yxat")
        self.assertContains(response, 'aria-pressed="true"')

    def test_picker_toggle_and_quick_add(self):
        response = self.client.post(self._url('shelf_toggle', self.book.pk, self.shelf.slug))
        self.assertContains(response, 'aria-pressed="false"')
        self.assertEqual(self.shelf.items.count(), 0)

        self.client.post(self._url('shelf_quick_add', self.book.pk), {'name': "Tezkor"})
        self.assertEqual(Shelf.objects.get(owner=self.owner, name="Tezkor").items.count(), 1)

    def test_book_page_has_list_button(self):
        response = self.client.get(f'/books/{self.book.pk}/')
        self.assertContains(response, self._url('shelf_picker', self.book.pk))


class MyLibraryPageTests(HtmlAssertsMixin, TestCase):
    def test_shows_favorites_history_reviews_and_lists(self):
        user = make_student()
        book = make_book("Sevimli kitob")
        services.toggle_favorite(user, book)
        ReadingHistory.objects.create(user=user, book=make_book("O'qilgan kitob"))
        services.submit_review(user, make_book("Baholangan kitob"), 5, "Zo'r")
        services.create_shelf(user, "Mening to'plamim")
        self.client.force_login(user)

        response = self.client.get('/engagement/my-library/')

        self.assertTemplateUsed(response, 'opac/my_library.html')
        for text in ("Sevimli kitob", "O'qilgan kitob", "Baholangan kitob",
                     "Mening to'plamim", "Moderatsiyada"):
            self.assertShows(response, text)

    def test_empty_state(self):
        self.client.force_login(make_employee())
        response = self.client.get('/engagement/my-library/')
        self.assertContains(response, "Sevimli kitob yo'q")
