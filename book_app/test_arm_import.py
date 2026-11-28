"""Universitet kitoblar bazasidan import. Yozuv shakli arm-admin API'sidan olingan."""
import shutil
import tempfile
from io import BytesIO
from unittest import mock

import requests
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from audit.models import ActionLog, JobRun
from core.testing import make_author, make_book, make_genre, make_librarian, make_student

from . import arm_import, remote
from .models import Author, Book, ExternalRecord, Genre

SOURCE = 'https://arm.test/api/v1/books/'


def raw(number=1, title="Mumtoz adabiyot tarixi", author="Dilnavoz Yusupova", **extra):
    return {
        'id': number, 'title': title, 'author': {'id': 5, 'name': author},
        'category': {'id': 2, 'title': "Filologiya"}, 'year': 2013,
        'description': "Qo'llanma", 'photo': f"http://arm.test/media/images/{number}.png",
        'source': f"http://arm.test/media/books/{number}.pdf",
        'updated_at': '2026-11-24T10:59:51+05:00', **extra,
    }


def png():
    buffer = BytesIO()
    Image.new('RGB', (4, 6), 'green').save(buffer, 'PNG')
    return buffer.getvalue()


class FakeSource:
    def __init__(self, *pages):
        self.pages = [list(page) for page in pages]
        self.asked = []

    def page(self, number):
        self.asked.append(number)
        if number > len(self.pages):
            return None
        return {'count': sum(map(len, self.pages)), 'results': self.pages[number - 1],
                'next': 'bor' if number < len(self.pages) else None}


class FakeResponse:
    def __init__(self, body=b'', status=200, payload=None):
        self.body, self.status_code, self.payload = body, status, payload

    def iter_content(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start:start + size]

    def json(self):
        if self.payload is None:
            raise ValueError
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ArmCase(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        settings = override_settings(ARM_API_URL=SOURCE, MEDIA_ROOT=media, MEDIA_MIN_FREE_GB=0)
        settings.enable()
        self.addCleanup(settings.disable)
        self.requested = []
        self.files = {}

        def get(url, **kwargs):
            self.requested.append(url)
            if url in self.files:
                return FakeResponse(self.files[url])
            body = png() if url.endswith('.png') else b'%PDF-1.4 sinov'
            return FakeResponse(body)

        patcher = mock.patch.object(remote.requests, 'get', side_effect=get)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_import(self, *pages, **options):
        options.setdefault('covers', False)
        return arm_import.run(client=FakeSource(*pages), **options)


class ImportTests(ArmCase):
    def test_new_book_is_created_with_remote_file(self):
        stats = self.run_import([raw()])

        book = Book.objects.get()
        self.assertEqual((book.title, book.published_year, book.category.name),
                         ("Mumtoz adabiyot tarixi", 2013, "Filologiya"))
        self.assertEqual([a.full_name for a in book.authors.all()], ["Dilnavoz Yusupova"])
        self.assertEqual(book.remote_file_url, 'https://arm.test/media/books/1.pdf')
        self.assertFalse(book.electronic_version)
        self.assertTrue(book.has_ebook)
        self.assertEqual(book.reading_mode, Book.ReadingMode.DIGITAL)
        self.assertTrue(book.slug)
        self.assertEqual((stats['new'], stats['done']), (1, 1))
        self.assertEqual(self.requested, [])                 # PDF hozir olinmaydi

    def test_second_run_creates_nothing(self):
        self.run_import([raw()], [raw(2, title="Boshqa kitob")])

        stats = self.run_import([raw()], [raw(2, title="Boshqa kitob")])

        self.assertEqual((stats['same'], stats['new']), (2, 0))
        self.assertEqual((Book.objects.count(), ExternalRecord.objects.count()), (2, 2))

    def test_existing_book_is_linked_across_scripts_and_name_order(self):
        book = make_book("Мумтоз адабиёт тарихи", published_year=2013, description="O'zim yozgan",
                         authors=[make_author("Юсупова Дилнавоз")])

        stats = self.run_import([raw()])

        book.refresh_from_db()
        self.assertEqual((stats['linked'], stats['new'], Book.objects.count()), (1, 0, 1))
        self.assertEqual(book.description, "O'zim yozgan")
        self.assertEqual(book.title, "Мумтоз адабиёт тарихи")
        self.assertEqual(book.remote_file_url, 'https://arm.test/media/books/1.pdf')
        self.assertEqual(book.external_records.get().external_id, '1')

    def test_several_authors_in_one_field_are_split(self):
        self.run_import([raw(author="Р.Расулов ,С.Атиязов"),
                         raw(2, title="Ikkinchi", author="Qodiriy, Abdulla")])

        names = {book.title: sorted(a.full_name for a in book.authors.all())
                 for book in Book.objects.all()}
        self.assertEqual(names["Mumtoz adabiyot tarixi"], ["Р.Расулов", "С.Атиязов"])
        self.assertEqual(names["Ikkinchi"], ["Qodiriy, Abdulla"])

    def test_old_import_with_joined_authors_is_still_recognised(self):
        make_book("Mumtoz adabiyot tarixi", published_year=2013,
                  authors=[make_author("Р.Расулов ,С.Атиязов")])

        stats = self.run_import([raw(author="Р.Расулов ,С.Атиязов")])

        self.assertEqual((stats['linked'], Book.objects.count()), (1, 1))

    def test_book_with_own_file_keeps_it(self):
        book = make_book("Mumtoz adabiyot tarixi", published_year=2013)
        book.electronic_version.save('meniki.pdf', ContentFile(b'%PDF-1.4'))

        self.run_import([raw()])

        book.refresh_from_db()
        self.assertEqual(book.remote_file_url, '')
        self.assertEqual([a.full_name for a in book.authors.all()], ["Dilnavoz Yusupova"])

    def test_different_author_or_year_is_another_book(self):
        make_book("Mumtoz adabiyot tarixi", published_year=2013,
                  authors=[make_author("Boshqa Odam")])
        make_book("Mumtoz adabiyot tarixi", published_year=1999)

        stats = self.run_import([raw()])

        self.assertEqual((stats['new'], Book.objects.count()), (1, 3))

    def test_same_title_with_another_file_is_a_separate_volume(self):
        stats = self.run_import([raw(1), raw(2)])

        self.assertEqual((stats['new'], Book.objects.count()), (2, 2))

    def test_duplicate_source_record_is_linked_to_one_book(self):
        twin = raw(2, source="http://arm.test/media/books/1.pdf")

        stats = self.run_import([raw(1), twin])

        self.assertEqual((stats['new'], stats['linked'], Book.objects.count()), (1, 1, 1))
        self.assertEqual(Book.objects.get().external_records.count(), 2)

    def test_existing_author_and_catalogue_are_reused(self):
        make_author("Юсупова Дилнавоз")
        make_genre("Филология")

        self.run_import([raw()])

        self.assertEqual((Author.objects.count(), Genre.objects.count()), (1, 1))

    def test_changed_record_updates_only_what_is_safe(self):
        self.run_import([raw()])
        Book.objects.update(title="Kutubxonachi tuzatgan nom")

        stats = self.run_import([raw(source="http://arm.test/media/books/yangi.pdf",
                                     updated_at='2026-11-28T00:00:00+05:00')])

        book = Book.objects.get()
        self.assertEqual(stats['updated'], 1)
        self.assertEqual(book.title, "Kutubxonachi tuzatgan nom")
        self.assertTrue(book.remote_file_url.endswith('yangi.pdf'))

    def test_compare_mode_writes_nothing(self):
        make_book("Mumtoz adabiyot tarixi", published_year=2013)

        stats = self.run_import(
            [raw(1), raw(2, title="Yangi kitob"),
             raw(3, title="Yangi kitob", source="http://arm.test/media/books/2.pdf")],
            dry=True, covers=True, files=True)

        self.assertEqual((stats['linked'], stats['new']), (2, 1))
        self.assertEqual((Book.objects.count(), ExternalRecord.objects.count()), (1, 0))
        self.assertEqual(self.requested, [])
        self.assertEqual(stats['dry'], 1)

    def test_broken_rows_are_counted_and_do_not_stop_the_run(self):
        real = arm_import.Writer.create

        def flaky(writer, record):
            if record.external_id == '1':
                raise RuntimeError('sinov')
            return real(writer, record)

        with mock.patch.object(arm_import.Writer, 'create', flaky), self.assertLogs('arm', 'ERROR'):
            stats = self.run_import([raw(1), {'id': 7, 'title': ''}, 'axlat',
                                     raw(2, title="Ikkinchi")])

        self.assertEqual((stats['failed'], stats['skipped'], stats['new']), (1, 2, 1))
        self.assertEqual(Book.objects.count(), 1)

    def test_covers_are_downloaded_once(self):
        self.run_import([raw()], covers=True)
        self.requested.clear()

        stats = self.run_import([raw()], covers=True)

        self.assertTrue(Book.objects.get().cover_image.name.startswith('book_covers/arm-'))
        self.assertEqual((self.requested, stats.get('covers', 0)), ([], 0))

    def test_a_cover_that_is_not_an_image_is_rejected(self):
        self.files['https://arm.test/media/images/1.png'] = b'<html>xato</html>'

        stats = self.run_import([raw()], covers=True)

        self.assertEqual(stats['cover_failed'], 1)
        self.assertFalse(Book.objects.get().cover_image)

    def test_files_option_saves_pdfs(self):
        stats = self.run_import([raw()], files=True)

        book = Book.objects.get()
        self.assertEqual(stats['files'], 1)
        self.assertEqual(book.electronic_version.read(), b'%PDF-1.4 sinov')

    def test_low_disk_space_stops_files_but_not_books(self):
        with mock.patch.object(remote, 'has_room', return_value=False):
            stats = self.run_import([raw()], covers=True, files=True)

        self.assertEqual((stats['new'], stats['disk_full']), (1, 1))
        self.assertEqual(self.requested, [])

    def test_stop_request_ends_after_the_current_page(self):
        source = FakeSource([raw(1)], [raw(2, title="Ikkinchi")])

        stats = arm_import.run(client=source, covers=False, progress=lambda stats: True)

        self.assertEqual((source.asked, stats['stopped'], Book.objects.count()), ([1], 1, 1))

    def test_foreign_addresses_are_ignored(self):
        self.run_import([raw(source='http://boshqa.example/a.pdf',
                             photo='file:///etc/passwd')], covers=True, files=True)

        book = Book.objects.get()
        self.assertEqual((book.remote_file_url, self.requested), ('', []))
        self.assertEqual(book.reading_mode, Book.ReadingMode.PHYSICAL)


class SourceTests(ArmCase):
    def client_with(self, *responses):
        session = mock.Mock()
        session.get.side_effect = list(responses)
        return arm_import.ArmClient(SOURCE, session=session, sleep=lambda s: None), session

    def test_retries_then_returns_page(self):
        page = {'count': 1, 'next': None, 'results': [raw()]}
        client, session = self.client_with(requests.ConnectionError(), FakeResponse(status=502),
                                           FakeResponse(payload=page))

        self.assertEqual(client.page(1), page)
        self.assertEqual(session.get.call_count, 3)

    def test_missing_page_ends_the_listing(self):
        client, _ = self.client_with(FakeResponse(status=404))

        self.assertIsNone(client.page(5))

    def test_unexpected_answers_become_messages(self):
        for response in (FakeResponse(status=403), FakeResponse(), FakeResponse(payload=[1]),
                         FakeResponse(status=404)):
            client, _ = self.client_with(response)
            with self.subTest(status=response.status_code), self.assertRaises(arm_import.SourceError):
                client.page(1)

    def test_refusal_by_the_source_is_explained_and_not_retried(self):
        client, session = self.client_with(FakeResponse(status=403))

        with self.assertRaisesMessage(arm_import.SourceError, "ruxsat bermadi (403)"):
            client.page(1)
        self.assertEqual(session.get.call_count, 1)

    def test_source_url_allows_only_the_source_host(self):
        self.assertEqual(remote.source_url('http://arm.test:80/a.pdf'), 'https://arm.test/a.pdf')
        for url in ('http://arm.test.evil.example/a', 'https://evil.example/a', 'ftp://arm.test/a',
                    '//arm.test/a', '', None):
            with self.subTest(url=url):
                self.assertEqual(remote.source_url(url), '')

    def test_redirects_and_oversize_files_are_refused(self):
        with mock.patch.object(remote.requests, 'get', return_value=FakeResponse(status=302)), \
                self.assertRaises(remote.FetchError):
            remote.download('https://arm.test/a.pdf', 100)
        with mock.patch.object(remote.requests, 'get', return_value=FakeResponse(b'x' * 200)), \
                self.assertRaises(remote.FetchError):
            remote.download('https://arm.test/a.pdf', 100)


class LazyReadingTests(ArmCase):
    def setUp(self):
        super().setUp()
        self.book = make_book("O'qiladigan", remote_file_url='https://arm.test/media/books/9.pdf')
        self.client.force_login(make_student())
        patcher = mock.patch('reading.views.start_ebook_fetch')
        self.start = patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_open_shows_waiting_page_and_starts_download(self):
        response = self.client.get(reverse('reading:read', args=[self.book.pk]))

        self.assertTemplateUsed(response, 'reading/preparing.html')
        self.assertContains(response, 'every 2s')
        self.start.assert_called_once()

    def test_status_redirects_when_the_file_is_ready(self):
        remote.fetch_ebook(self.book.pk)

        response = self.client.get(reverse('reading:prepare', args=[self.book.pk]))

        self.assertEqual(response['HX-Redirect'], reverse('reading:read', args=[self.book.pk]))
        reader = self.client.get(reverse('reading:read', args=[self.book.pk]))
        self.assertTemplateUsed(reader, 'reading/reader.html')

    def test_failed_download_is_shown_and_can_be_retried(self):
        self.files[self.book.remote_file_url] = b'<html>yo\'q</html>'
        remote.fetch_ebook(self.book.pk)

        response = self.client.get(reverse('reading:prepare', args=[self.book.pk]))

        self.assertContains(response, 'PDF emas')
        self.assertNotContains(response, 'every 2s')
        self.start.assert_not_called()
        self.client.get(reverse('reading:read', args=[self.book.pk]) + '?retry=1')
        self.book.refresh_from_db()
        self.assertEqual(self.book.remote_file_error, '')

    def test_guest_cannot_trigger_a_download(self):
        self.client.logout()

        response = self.client.get(reverse('reading:read', args=[self.book.pk]))

        self.assertEqual(response.status_code, 302)
        self.start.assert_not_called()

    def test_catalogue_offers_online_reading(self):
        response = self.client.get(reverse('book_app:student_book_detail', args=[self.book.pk]))

        self.assertContains(response, reverse('reading:read', args=[self.book.pk]))


@override_settings(ARM_API_URL=SOURCE)
class ImportPageTests(TestCase):
    def setUp(self):
        self.client.force_login(make_librarian())
        patcher = mock.patch.object(arm_import, 'start', return_value=object())
        self.start = patcher.start()
        self.addCleanup(patcher.stop)

    def test_page_has_both_ways_and_no_free_url_field(self):
        response = self.client.get(reverse('panel:import_books'))

        self.assertContains(response, 'Universitet kitoblar bazasi')
        self.assertContains(response, 'name="file"')
        self.assertNotContains(response, 'name="url"')

    def test_compare_is_the_default_and_is_not_audited(self):
        response = self.client.post(reverse('panel:arm_start'), {'mode': 'compare', 'covers': '1'})

        self.assertContains(response, 'Solishtirish boshlandi')
        self.start.assert_called_once_with(dry=True, covers=True, files=False)
        self.assertFalse(ActionLog.objects.filter(action=ActionLog.Action.IMPORT).exists())
        self.client.post(reverse('panel:arm_start'), {})
        self.assertTrue(self.start.call_args.kwargs['dry'])

    def test_import_is_audited(self):
        self.client.post(reverse('panel:arm_start'), {'mode': 'import', 'files': '1'})

        self.start.assert_called_once_with(dry=False, covers=False, files=True)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.IMPORT).exists())

    def test_busy(self):
        self.start.return_value = None

        response = self.client.post(reverse('panel:arm_start'), {'mode': 'import'})

        self.assertContains(response, 'allaqachon ishlayapti')

    def test_status_and_stop(self):
        run = JobRun.objects.create(
            name=arm_import.JOB_NAME, status=JobRun.Status.RUNNING,
            stats={'total': 200, 'done': 50, 'new': 40, 'beat': '2999-01-01T00:00:00+00:00'})

        status = self.client.get(reverse('panel:arm_status'))
        self.assertContains(status, 'every 2s')
        self.assertContains(status, 'width: 25%')

        stopped = self.client.post(reverse('panel:arm_stop'))
        run.refresh_from_db()
        self.assertTrue(run.stats['stop'])
        self.assertContains(stopped, "To'xtatilmoqda")

    def test_execute_records_summary_and_keeps_stop_flag(self):
        record = JobRun.objects.create(name=arm_import.JOB_NAME, status=JobRun.Status.RUNNING,
                                       stats={'stop': True})
        source = FakeSource([raw(1)], [raw(2, title="Ikkinchi")])

        with mock.patch.object(arm_import, 'ArmClient', return_value=source):
            arm_import.execute(record, False, False, False)

        record.refresh_from_db()
        self.assertEqual(record.status, JobRun.Status.SUCCESS)
        self.assertIn("to'xtatildi", record.message)
        self.assertEqual(Book.objects.count(), 1)

    def test_execute_records_source_failure(self):
        record = JobRun.objects.create(name=arm_import.JOB_NAME, status=JobRun.Status.RUNNING)
        broken = mock.Mock()
        broken.page.side_effect = arm_import.SourceError("Manba yopiq")

        with mock.patch.object(arm_import, 'ArmClient', return_value=broken):
            arm_import.execute(record, False, False, False)

        record.refresh_from_db()
        self.assertEqual((record.status, record.message), (JobRun.Status.FAILED, "Manba yopiq"))
