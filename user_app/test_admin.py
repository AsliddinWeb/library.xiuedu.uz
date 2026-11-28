"""Admin panel: hisob turlari bo'yicha ajratish va rol biriktirish."""
from django.db.models.fields.files import FieldFile
from django.test import TestCase
from django.urls import reverse

from core.testing import make_admin, make_employee, make_librarian, make_student

from .models import Role, User
from .permissions import Perms
from .roles import AccountKind, Roles, account_kind


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = make_admin(username='bosh-admin')
        self.client.force_login(self.admin)
        self.student = make_student(username='t-1')
        self.employee = make_employee(username='x-1')
        self.librarian = make_librarian(username='k-1')
        self.librarian_role = Role.objects.get(name=Roles.LIBRARIAN)

    def _listed(self, kind):
        response = self.client.get(reverse('admin:user_app_user_changelist'), {'kind': kind})
        self.assertEqual(response.status_code, 200)
        return set(response.context['cl'].queryset.values_list('username', flat=True))

    def test_kind_filter_separates_accounts(self):
        self.assertEqual(self._listed('student'), {'t-1'})
        self.assertEqual(self._listed('employee'), {'x-1'})
        self.assertEqual(self._listed('librarian'), {'k-1'})
        self.assertEqual(self._listed('admin'), {'bosh-admin'})

    def test_sidebar_links_render(self):
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, '?kind=librarian')
        self.assertContains(response, '/panel/')

    def _save_with_role(self, user, role):
        """O'zgartirish sahifasidagi formani boshqa rol bilan qayta yuboradi."""
        url = reverse('admin:user_app_user_change', args=[user.pk])
        page = self.client.get(url)
        forms = [page.context['adminform'].form]
        for inline in page.context['inline_admin_formsets']:
            forms.append(inline.formset.management_form)
            forms.extend(inline.formset.forms)
        data = {}
        for form in forms:
            for bound in form:
                value = bound.value()
                if value in (None, False) or bound.name == 'password' or isinstance(value, FieldFile):
                    continue
                if isinstance(value, list):
                    value = [getattr(v, 'pk', v) for v in value]
                data[bound.html_name] = value
        data['assigned_role'] = role.pk if role else ''
        response = self.client.post(url, data)
        errors = response.context['adminform'].form.errors if response.status_code == 200 else None
        self.assertEqual(response.status_code, 302, errors)
        return User.objects.get(pk=user.pk)

    def test_make_librarian_and_back(self):
        librarian = self._save_with_role(self.employee, self.librarian_role)
        self.assertEqual(account_kind(librarian), AccountKind.LIBRARIAN)

        reader_role = Role.objects.get(name=Roles.EMPLOYEE)
        reader = self._save_with_role(librarian, reader_role)
        self.assertEqual(account_kind(reader), AccountKind.READER)
        self.assertEqual(list(reader.employe_profile.roles.all()), [reader_role])


class RoleAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(make_admin())

    def test_permissions_are_chosen_with_checkboxes(self):
        role = Role.objects.get(name="Kataloglovchi")
        url = f'/admin/user_app/role/{role.pk}/change/'
        page = self.client.get(url)
        self.assertContains(page, 'name="flags"')

        self.client.post(url, {'name': role.name, 'description': '',
                               'flags': [Perms.CATALOG_VIEW, Perms.CATALOG_EDIT]})
        role.refresh_from_db()
        self.assertEqual(role.permissions, [Perms.CATALOG_VIEW, Perms.CATALOG_EDIT])

        self.client.post(url, {'name': role.name, 'description': '', 'full_access': 'on'})
        role.refresh_from_db()
        self.assertEqual(role.permissions, ['*'])

    def test_reader_role_cannot_get_permissions_or_be_removed(self):
        role, _ = Role.objects.get_or_create(name=Roles.STUDENT)
        url = f'/admin/user_app/role/{role.pk}/change/'

        self.client.post(url, {'description': '', 'full_access': 'on'})
        role.refresh_from_db()
        self.assertEqual((role.name, role.permissions), (Roles.STUDENT, []))
        self.assertEqual(self.client.post(f'/admin/user_app/role/{role.pk}/delete/',
                                          {'post': 'yes'}).status_code, 403)
