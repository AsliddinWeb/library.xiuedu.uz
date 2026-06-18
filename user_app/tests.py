from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from .models import Role, User
from .roles import Roles, effective_role


class EffectiveRoleTests(TestCase):
    def test_anonymous(self):
        self.assertIsNone(effective_role(AnonymousUser()))

    def test_student(self):
        u = User.objects.create(username='s1', user_type='STUDENT')
        self.assertEqual(effective_role(u), Roles.STUDENT)

    def test_employee_default(self):
        u = User.objects.create(username='e1', user_type='EMPLOYE')
        self.assertEqual(effective_role(u), Roles.EMPLOYEE)

    def test_employee_librarian(self):
        u = User.objects.create(username='e2', user_type='EMPLOYE')
        u.employe_profile.current_role = Role.objects.get(name=Roles.LIBRARIAN)
        u.employe_profile.save()
        self.assertEqual(effective_role(User.objects.get(pk=u.pk)), Roles.LIBRARIAN)

    def test_superuser(self):
        u = User.objects.create(username='su', user_type='EMPLOYE', is_superuser=True)
        self.assertEqual(effective_role(u), Roles.ADMIN)


class GetFullNameTests(TestCase):
    def test_none_safe(self):
        self.assertEqual(User(username='x').get_full_name(), 'x')

    def test_full(self):
        u = User(username='x', first_name='Ali', second_name='Valiyev')
        self.assertEqual(u.get_full_name(), 'VALIYEV ALI')


class SeedRolesTests(TestCase):
    def test_default_roles_exist(self):
        for name in Roles.CHOICES:
            self.assertTrue(Role.objects.filter(name=name).exists())


class PermissionTests(TestCase):
    def test_librarian_page_forbidden_for_student(self):
        User.objects.create_user(username='stud', password='x', user_type='STUDENT')
        self.client.login(username='stud', password='x')
        self.assertEqual(self.client.get('/books/authors/list/').status_code, 403)

    def test_librarian_page_ok_for_librarian(self):
        u = User.objects.create_user(username='lib', password='x', user_type='EMPLOYE')
        u.employe_profile.current_role = Role.objects.get(name=Roles.LIBRARIAN)
        u.employe_profile.save()
        self.client.login(username='lib', password='x')
        self.assertEqual(self.client.get('/books/authors/list/').status_code, 200)
