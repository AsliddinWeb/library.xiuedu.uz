from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from book_app.models import Book, Genre
from user_app.models import User

from .models import ReadingProgress


class StreamTests(TestCase):
    def setUp(self):
        g = Genre.objects.create(name='G')
        self.book = Book.objects.create(title='B', category=g)
        self.book.electronic_version.save('t.pdf', ContentFile(b'%PDF-1.4 ' + b'x' * 500), save=True)
        User.objects.create_user(username='u', password='x', user_type='STUDENT')
        self.client.login(username='u', password='x')

    def tearDown(self):
        self.book.electronic_version.delete(save=False)

    def test_reader_page(self):
        self.assertEqual(self.client.get(f'/reading/read/{self.book.pk}/').status_code, 200)

    def test_stream_inline_and_range(self):
        url = f'/reading/stream/ebook/{self.book.pk}/'
        full = self.client.get(url)
        self.assertEqual(full.status_code, 200)
        self.assertEqual(full['Content-Disposition'], 'inline')
        self.assertEqual(full['Accept-Ranges'], 'bytes')
        partial = self.client.get(url, HTTP_RANGE='bytes=0-9')
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial['Content-Range'].split('/')[0], 'bytes 0-9')

    @override_settings(USE_X_ACCEL_REDIRECT=True, X_ACCEL_LOCATION='/protected-media')
    def test_x_accel_redirect_in_production(self):
        resp = self.client.get(f'/reading/stream/ebook/{self.book.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['X-Accel-Redirect'].startswith('/protected-media/'))
        self.assertEqual(resp['Content-Disposition'], 'inline')

    def test_save_progress(self):
        r = self.client.post(f'/reading/progress/{self.book.pk}/',
                             {'mode': 'READ', 'position': '7', 'percent': '40'})
        self.assertEqual(r.status_code, 200)
        p = ReadingProgress.objects.get(book=self.book)
        self.assertEqual(p.position, 7)
        self.assertEqual(p.percent, 40)
