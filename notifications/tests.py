from django.test import TestCase

from book_app.models import Book, Genre, Item
from circulation import services as circ
from circulation.models import RentalRequest
from core.testing import make_employee, make_student
from user_app.models import User
from user_app.services import get_or_create_patron

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
    def setUp(self):
        genre = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=genre)
        Item.objects.create(book=self.book, inventory_number='1', is_available=True)

    def test_approve_request_notifies_patron(self):
        patron = get_or_create_patron(make_student(username='talaba-n'))
        req = RentalRequest.objects.create(patron=patron, book=self.book)

        circ.approve_request(req)

        self.assertTrue(
            Notification.objects.filter(
                user=patron.user, type=Notification.Type.REQUEST_APPROVED).exists())

    def test_employee_also_gets_notification(self):
        patron = get_or_create_patron(make_employee(username='xodim-n'))
        req = RentalRequest.objects.create(patron=patron, book=self.book)

        circ.approve_request(req)

        self.assertTrue(
            Notification.objects.filter(
                user=patron.user, type=Notification.Type.REQUEST_APPROVED).exists())

    def test_manual_patron_without_user_is_skipped(self):
        """HEMIS'siz a'zoda foydalanuvchi yo'q — bildirishnoma yuborilmaydi, xato ham bermaydi."""
        from user_app.models import Patron, PatronCategory
        from user_app.services import get_category
        patron = Patron.objects.create(
            card_number='XIU-990001', full_name="Tashqi a'zo",
            category=get_category(PatronCategory.Code.EXTERNAL))
        req = RentalRequest.objects.create(patron=patron, book=self.book)

        rental, _ = circ.approve_request(req)
        self.assertIsNotNone(rental)
        self.assertEqual(Notification.objects.count(), 0)
