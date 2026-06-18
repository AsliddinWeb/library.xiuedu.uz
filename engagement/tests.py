from django.test import TestCase

from book_app.models import Book, Genre
from user_app.models import User

from . import services
from .models import Favorite, Review


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
