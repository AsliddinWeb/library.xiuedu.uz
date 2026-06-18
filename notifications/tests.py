from django.test import TestCase

from book_app.models import Book, Copy, Genre
from circulation import services as circ
from circulation.models import RentalRequest
from user_app.models import User

from .models import Notification
from .services import notify, unread_count


class NotifyTests(TestCase):
    def test_notify_and_unread(self):
        u = User.objects.create(username='u', user_type='STUDENT')
        notify(u, 'Test')
        self.assertEqual(unread_count(u), 1)

    def test_unread_anonymous(self):
        self.assertEqual(unread_count(None), 0)


class EventNotificationTests(TestCase):
    def test_approve_request_notifies_student(self):
        g = Genre.objects.create(name='G')
        book = Book.objects.create(title='B', category=g)
        Copy.objects.create(book=book, inventory_number='1', is_available=True)
        student = User.objects.create(username='s', user_type='STUDENT').student_profile
        req = RentalRequest.objects.create(student=student, book=book)
        circ.approve_request(req)
        self.assertTrue(
            Notification.objects.filter(
                user=student.user, type=Notification.Type.REQUEST_APPROVED).exists())
