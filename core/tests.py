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
