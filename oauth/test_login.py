"""HEMIS kirish: talaba va xodim o'z tizimidan, ikkalasi o'quvchi bo'lib kiradi."""
from unittest import mock

from django.test import TestCase, override_settings

from core.testing import make_librarian, make_student
from user_app.models import EmployeProfile, Patron, Role, StudentProfile, User
from user_app.roles import AccountKind, Roles, account_kind

HEMIS = dict(
    CLIENT_ID='1', CLIENT_SECRET='s', REDIRECT_URI='http://testserver/auth/callback/',
    AUTHORIZE_URL='https://student.xiuedu.uz/oauth/authorize',
    ACCESS_TOKEN_URL='https://student.xiuedu.uz/oauth/access-token',
    RESOURCE_OWNER_URL='https://student.xiuedu.uz/oauth/api/user',
    EMPLOYE_CLIENT_ID='2', EMPLOYE_CLIENT_SECRET='e',
    EMPLOYE_REDIRECT_URI='http://testserver/auth/callback/',
    EMPLOYE_AUTHORIZE_URL='https://hemis.xiuedu.uz/oauth/authorize',
    EMPLOYE_ACCESS_TOKEN_URL='https://hemis.xiuedu.uz/oauth/access-token',
    EMPLOYE_RESOURCE_OWNER_URL='https://hemis.xiuedu.uz/oauth/api/user',
)


def employee_data(number='900001', position="Bosh mutaxassis"):
    return {'employee_id_number': number, 'firstname': 'Anvar', 'surname': 'Karimov',
            'departments': [{'department': {'name': "Moliya"},
                             'staffPosition': {'name': position}}]}


@override_settings(**HEMIS)
class LoginChoiceTests(TestCase):
    def test_protected_page_offers_both_logins(self):
        response = self.client.get('/books/')
        self.assertEqual(response.headers['Location'], '/auth/login/?next=/books/')

        page = self.client.get(response.headers['Location'])
        self.assertContains(page, '/auth/student-login/')
        self.assertContains(page, '/auth/employee-login/')

    def test_employee_login_goes_to_employee_hemis(self):
        response = self.client.get('/auth/employee-login/')
        self.assertTrue(response.headers['Location'].startswith(
            'https://hemis.xiuedu.uz/oauth/authorize'))
        self.assertIn('client_id=2', response.headers['Location'])

    def test_signed_in_user_skips_choice(self):
        self.client.force_login(make_librarian())
        self.assertRedirects(self.client.get('/auth/login/'), '/panel/',
                             fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        self.client.get('/auth/login/?next=https://yomon.example/')
        self.assertNotIn('login_next', self.client.session)


@override_settings(**HEMIS)
class CallbackTests(TestCase):
    def callback(self, user_type, data):
        self.client.cookies['user_type'] = user_type
        with mock.patch('oauth.client.oAuth2Client.get_access_token',
                        return_value={'access_token': 't'}), \
             mock.patch('oauth.client.oAuth2Client.get_user_details', return_value=data):
            return self.client.get('/auth/callback/?code=abc')

    def test_employee_enters_as_reader_stored_separately(self):
        response = self.callback('employee', employee_data())

        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        user = User.objects.get(username='900001')
        self.assertEqual(user.user_type, User.UserType.EMPLOYE)
        self.assertEqual(account_kind(user), AccountKind.READER)
        self.assertTrue(EmployeProfile.objects.filter(user=user).exists())
        self.assertFalse(StudentProfile.objects.filter(user=user).exists())
        self.assertEqual(Patron.objects.get(user=user).category.code, 'XODIM')
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)
        self.assertEqual(self.client.get('/panel/').status_code, 403)

    def test_teacher_gets_teacher_category(self):
        self.callback('employee', employee_data(position="Dotsent"))
        self.assertEqual(Patron.objects.get(user__username='900001').category.code,
                         'PROF_OQITUVCHI')

    def test_master_student_gets_master_category_on_first_login(self):
        self.callback('student', {'data': {
            'student_id_number': '700001', 'first_name': 'Lola',
            'educationType': {'name': 'Magistr'}, 'level': {'name': '1-kurs'}}})

        self.assertEqual(Patron.objects.get(user__username='700001').category.code, 'MAGISTR')

    def test_librarian_keeps_role_and_gets_panel(self):
        self.callback('employee', employee_data())
        user = User.objects.get(username='900001')
        role, _ = Role.objects.get_or_create(name=Roles.LIBRARIAN,
                                             defaults={'permissions': ['catalog.view']})
        user.employe_profile.current_role = role
        user.employe_profile.save()
        user.employe_profile.roles.add(role)
        Patron.objects.filter(user=user).delete()
        self.client.logout()

        response = self.callback('employee', employee_data())

        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/dashboard/'), '/panel/',
                             fetch_redirect_response=False)
        self.assertFalse(Patron.objects.filter(user=user).exists())

    def test_returns_to_requested_page(self):
        self.client.get('/auth/login/?next=/books/')
        self.assertRedirects(self.callback('employee', employee_data()), '/books/',
                             fetch_redirect_response=False)

    def test_same_number_does_not_take_over_student_account(self):
        student = make_student(username='900001', first_name='Talaba')

        self.callback('employee', employee_data())

        student.refresh_from_db()
        self.assertEqual(student.user_type, User.UserType.STUDENT)
        self.assertEqual(student.first_name, 'Talaba')
        self.assertTrue(User.objects.filter(username='emp-900001',
                                            user_type=User.UserType.EMPLOYE).exists())
        # Qayta kirishda o'sha hisob ishlatiladi
        self.client.logout()
        self.callback('employee', employee_data())
        self.assertEqual(User.objects.filter(username__endswith='900001').count(), 2)
