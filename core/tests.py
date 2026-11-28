"""Loyiha darajasidagi testlar: dizayn tizimi sahifasi va shell shablonlari."""
from django.template.loader import render_to_string
from django.test import TestCase

from core.testing import make_librarian, make_student


class DesignSystemPageTests(TestCase):
    """`/_design/` — xodim uchun, flag bilan boshqariladi."""

    def test_librarian_sees_styleguide(self):
        self.client.force_login(make_librarian())
        response = self.client.get('/_design/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dizayn tizimi')
        # Ikki qiyofa ham sahifada ko'rsatiladi
        self.assertContains(response, 'data-shell="opac"')
        self.assertContains(response, 'data-shell="staff"')

    def test_student_gets_403(self):
        self.client.force_login(make_student())
        self.assertEqual(self.client.get('/_design/').status_code, 403)

    def test_hidden_when_flag_off(self):
        self.client.force_login(make_librarian())
        with self.settings(FEATURE_FLAGS={'design_styleguide': False}):
            self.assertEqual(self.client.get('/_design/').status_code, 404)


class ShellTemplateTests(TestCase):
    """Yangi shell'lar xatosiz render bo'ladi va to'g'ri qiyofani e'lon qiladi."""

    def test_opac_shell_renders(self):
        html = render_to_string('layouts/opac.html', {})
        self.assertIn('data-shell="opac"', html)
        self.assertIn('toast-host', html)

    def test_staff_shell_renders(self):
        html = render_to_string('layouts/staff.html', {'page_title': "Kitoblar"})
        self.assertIn('data-shell="staff"', html)
        self.assertIn("Kitoblar", html)

    def test_ui_partials_render(self):
        self.assertIn('badge-success',
                      render_to_string('ui/_badge.html', {'text': 'Mavjud', 'variant': 'success'}))
        self.assertIn('stat-value',
                      render_to_string('ui/_stat.html', {'label': 'Ijara', 'value': 5}))
        self.assertIn('empty-title', render_to_string('ui/_empty.html', {'title': "Bo'sh"}))
        self.assertIn('<svg', render_to_string('ui/_icon.html', {'name': 'search'}))


class UiFilterTests(TestCase):
    """Interfeys filtrlari (`ui_extras`)."""

    def test_genre_icon_works_for_latin_and_cyrillic(self):
        from book_app.templatetags.ui_extras import genre_icon

        self.assertEqual(genre_icon("Iqtisodiyot"), 'trending')
        self.assertEqual(genre_icon("Иқтисодиёт"), 'trending')
        self.assertEqual(genre_icon("Axborot texnologiyalari"), 'code')
        self.assertEqual(genre_icon("Noma'lum bo'lim"), 'book-open')
        self.assertEqual(genre_icon(""), 'book-open')

    def test_cover_tone_is_stable_and_in_range(self):
        from book_app.templatetags.ui_extras import COVER_TONES, cover_tone
        from core.testing import make_book

        book = make_book()
        self.assertEqual(cover_tone(book), cover_tone(book))
        self.assertIn(cover_tone(book), range(COVER_TONES))

    def test_initials_and_spaced(self):
        from book_app.templatetags.ui_extras import initials, spaced
        from core.testing import make_student

        user = make_student(username='zz-user', first_name='Anvar', second_name='Karimov')
        self.assertEqual(initials(user), 'KA')
        self.assertEqual(initials(make_student(username='qx')), 'QX')
        self.assertEqual(spaced(2392), '2 392')

    def test_every_listed_icon_exists(self):
        """Noma'lum nom bo'sh doira chizadi — ro'yxatdagi hech biri shunday bo'lmasin."""
        from core.views import ICONS

        fallback = render_to_string('ui/_icon.html', {'name': 'yoq-ikonka'})
        for name in ICONS:
            with self.subTest(name):
                self.assertNotEqual(render_to_string('ui/_icon.html', {'name': name}), fallback)


class ErrorPageTests(TestCase):
    def test_custom_404_renders(self):
        with self.settings(DEBUG=False):
            response = self.client.get('/bunday-sahifa-yoq/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "javonda", status_code=404)

    def test_500_template_needs_no_context(self):
        self.assertIn("500", render_to_string('500.html'))
