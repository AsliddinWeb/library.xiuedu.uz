"""`delete_all_books` buyrug'i."""
import shutil
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils.timezone import now

from audit.models import ActionLog
from book_app.management.commands import delete_all_books as command
from book_app.models import Author, Book, ExternalRecord, Genre, Item, Rental
from circulation.models import Fine, Reservation
from circulation.services import recalc_patron_counters
from core.testing import make_author, make_book, make_student
from engagement.models import Favorite, Review
from user_app.models import Patron, User
from user_app.services import get_or_create_patron

BACKUP = 'book_app.management.commands.delete_all_books.backup_database'


class DeleteAllBooksTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        settings = override_settings(MEDIA_ROOT=media)
        settings.enable()
        self.addCleanup(settings.disable)

        self.book = make_book("Bir", authors=[make_author("Muallif")], copies=2)
        self.book.electronic_version.save('bir.pdf', ContentFile(b'%PDF-1.4'))
        self.file = Path(self.book.electronic_version.path)
        make_book("Ikki")
        self.reader = make_student()
        self.patron = get_or_create_patron(self.reader)
        self.rental = Rental.objects.create(
            copy=Item.objects.filter(book=self.book).first(), patron=self.patron,
            borrowed_date=now().date() - timedelta(days=30),
            due_date=now().date() - timedelta(days=5),
            return_date=now().date())
        Fine.objects.create(rental=self.rental, patron=self.patron, days_overdue=5, amount=5000)
        recalc_patron_counters(self.patron)
        Reservation.objects.create(book=self.book, patron=self.patron)
        Review.objects.create(user=self.reader, book=self.book, rating=5)
        Favorite.objects.create(user=self.reader, book=self.book)
        ExternalRecord.objects.create(book=self.book, source='arm', external_id='1')

        backup = Path(media) / 'zaxira.sql.gz'
        backup.write_bytes(b'x')
        patcher = mock.patch(BACKUP, return_value=backup)
        self.backup = patcher.start()
        self.addCleanup(patcher.stop)

    def run_command(self, *args, answer='OCHIRISH 2'):
        out = StringIO()
        with mock.patch('builtins.input', return_value=answer):
            call_command('delete_all_books', *args, stdout=out)
        return out.getvalue()

    def test_without_apply_only_reports(self):
        text = self.run_command()

        self.assertIn('Hech narsa o\'chirilmadi', text)
        self.assertEqual(Book.objects.count(), 2)
        self.backup.assert_not_called()

    def test_deletes_books_and_everything_attached_but_keeps_people(self):
        text = self.run_command('--apply')

        for model in (Book, Item, Rental, Fine, Reservation, Review, Favorite, ExternalRecord):
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.reader.pk).exists())
        self.assertEqual(Patron.objects.get().balance, 0)
        self.assertTrue(Author.objects.exists() and Genre.objects.exists())
        self.assertTrue(self.file.exists())
        self.assertIn('psql', text)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.BIBLIO_DELETE,
                                                 note__contains='Barcha kitoblar').exists())

    def test_optional_flags_remove_files_and_reference_data(self):
        self.run_command('--apply', '--delete-files', '--delete-references', '--delete-catalogs')

        self.assertFalse(self.file.exists())
        self.assertFalse(Author.objects.exists() or Genre.objects.exists())

    def test_wrong_confirmation_deletes_nothing(self):
        for answer in ('', 'ha', 'OCHIRISH', 'OCHIRISH 1', 'ochirish 2'):
            with self.subTest(answer=answer), self.assertRaises(CommandError):
                self.run_command('--apply', answer=answer)
        self.assertEqual(Book.objects.count(), 2)

    def test_failed_backup_deletes_nothing(self):
        self.backup.side_effect = CommandError('Zaxira olinmadi')

        with self.assertRaises(CommandError):
            self.run_command('--apply', '--delete-files')

        self.assertEqual(Book.objects.count(), 2)
        self.assertTrue(self.file.exists())

    def test_active_loan_needs_explicit_permission(self):
        Rental.objects.filter(pk=self.rental.pk).update(return_date=None)

        with self.assertRaisesMessage(CommandError, '--with-active-loans'):
            self.run_command('--apply')
        self.assertEqual(Book.objects.count(), 2)

        self.run_command('--apply', '--with-active-loans')
        self.assertFalse(Book.objects.exists())

    def test_error_during_deletion_rolls_everything_back(self):
        with mock.patch.object(command, 'recalc_patron_counters', side_effect=RuntimeError), \
                self.assertRaises(RuntimeError):
            self.run_command('--apply', '--delete-files')

        self.assertEqual((Book.objects.count(), Rental.objects.count()), (2, 1))
        self.assertTrue(self.file.exists())
