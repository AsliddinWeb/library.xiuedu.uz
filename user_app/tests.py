from datetime import date, timedelta

from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import TestCase

from .models import Patron, PatronCategory, Role, User
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
        # Eski muallif sahifasi endi kutubxonachi paneliga yo'naltiradi
        self.assertRedirects(self.client.get('/books/authors/list/'), '/panel/authors/')


# =============================================================================
#  P1 — A'zolik (Patron) va ruxsatlar
# =============================================================================

class PatronSyncTests(TestCase):
    """HEMIS kirishida a'zolik ochilishi va toifaning to'g'ri aniqlanishi."""

    def test_student_gets_patron(self):
        from .services import sync_patron
        user = User.objects.create(username='t1', user_type='STUDENT')
        patron = sync_patron(user)

        self.assertEqual(patron.category.code, PatronCategory.Code.STUDENT)
        self.assertEqual(patron.status, Patron.Status.ACTIVE)
        self.assertTrue(patron.card_number.startswith('XIU-'))

    def test_employee_gets_patron(self):
        """Asosiy talab: xodim ham kutubxona a'zosi bo'ladi."""
        from .services import sync_patron
        user = User.objects.create(username='x1', user_type='EMPLOYE')
        user.employe_profile.position = "Katta ilmiy xodim"
        user.employe_profile.save()

        patron = sync_patron(user)
        self.assertEqual(patron.category.code, PatronCategory.Code.STAFF)
        can, reason = patron.can_borrow()
        self.assertTrue(can, reason)

    def test_teacher_detected_from_position(self):
        from .services import sync_patron
        user = User.objects.create(username='x2', user_type='EMPLOYE')
        user.employe_profile.position = "Dotsent, Axborot texnologiyalari kafedrasi"
        user.employe_profile.save()

        self.assertEqual(sync_patron(user).category.code, PatronCategory.Code.TEACHER)

    def test_master_student_detected(self):
        from .services import sync_patron
        user = User.objects.create(username='m1', user_type='STUDENT')
        user.student_profile.education_type = "Magistratura"
        user.student_profile.save()

        patron = sync_patron(user)
        self.assertEqual(patron.category.code, PatronCategory.Code.MASTER)
        self.assertEqual(patron.category.default_loan_days, 21)

    def test_card_numbers_are_unique_and_sequential(self):
        from .services import sync_patron
        numbers = [sync_patron(User.objects.create(username=f'u{i}', user_type='STUDENT')).card_number
                   for i in range(3)]
        self.assertEqual(len(set(numbers)), 3)
        self.assertEqual(numbers, sorted(numbers))

    def test_sync_is_idempotent(self):
        from .services import sync_patron
        user = User.objects.create(username='t2', user_type='STUDENT')
        first = sync_patron(user)
        again = sync_patron(user)

        self.assertEqual(first.pk, again.pk)
        self.assertEqual(Patron.objects.filter(user=user).count(), 1)

    def test_category_updates_when_student_becomes_master(self):
        from .services import sync_patron
        user = User.objects.create(username='t3', user_type='STUDENT')
        patron = sync_patron(user)
        self.assertEqual(patron.category.code, PatronCategory.Code.STUDENT)

        user.student_profile.education_type = "Magistratura"
        user.student_profile.save()
        patron = sync_patron(user)

        self.assertEqual(patron.category.code, PatronCategory.Code.MASTER)

    def test_blocked_patron_stays_blocked_after_login(self):
        from .services import sync_patron
        user = User.objects.create(username='t4', user_type='STUDENT')
        patron = sync_patron(user)
        patron.status = Patron.Status.BLOCKED
        patron.block_reason = "Kitob yo'qotgan"
        patron.save()

        patron = sync_patron(user)
        self.assertEqual(patron.status, Patron.Status.BLOCKED)

    def test_external_category_has_membership_expiry(self):
        from .services import get_category, membership_expiry
        category = get_category(PatronCategory.Code.EXTERNAL)
        start = date(2026, 1, 31)

        self.assertEqual(category.membership_months, 12)
        self.assertEqual(membership_expiry(category, start), date(2027, 1, 31))


class PatronRulesTests(TestCase):
    """`can_borrow()` — ijara berishdan oldingi tekshiruvlar."""

    def setUp(self):
        from .services import sync_patron
        self.patron = sync_patron(User.objects.create(username='p1', user_type='STUDENT'))

    def test_active_patron_can_borrow(self):
        can, _ = self.patron.can_borrow()
        self.assertTrue(can)

    def test_loan_limit_blocks(self):
        self.patron.active_loans_count = self.patron.category.loan_limit
        can, reason = self.patron.can_borrow()
        self.assertFalse(can)
        self.assertIn("limit", reason.lower())

    def test_debt_blocks_when_over_threshold(self):
        self.patron.category.debt_block_amount = 50000
        self.patron.category.save()
        self.patron.balance = 60000
        can, reason = self.patron.can_borrow()
        self.assertFalse(can)
        self.assertIn("Qarz", reason)

    def test_expired_membership_blocks(self):
        self.patron.expires_on = date(2020, 1, 1)
        can, reason = self.patron.can_borrow()
        self.assertFalse(can)
        self.assertIn("muddati", reason.lower())

    def test_block_expires_by_date(self):
        from django.utils.timezone import now
        self.patron.status = Patron.Status.BLOCKED
        self.patron.blocked_until = now().date() - timedelta(days=1)
        self.assertFalse(self.patron.is_blocked)

    def test_display_name_for_manual_patron(self):
        from .services import get_category
        patron = Patron.objects.create(
            card_number='XIU-900001', full_name="Tashqi O'quvchi",
            category=get_category(PatronCategory.Code.EXTERNAL))
        self.assertEqual(patron.display_name, "Tashqi O'quvchi")


class GranularPermissionTests(TestCase):
    """Granular ruxsatlar: rol nomi emas, flag tekshiriladi."""

    def setUp(self):
        call_command('migrate', 'user_app', verbosity=0)  # rol ruxsatlari seed qilingan bo'lsin

    def test_librarian_has_circulation_perms(self):
        from core.testing import make_librarian

        from .permissions import Perms, has_perm
        user = make_librarian()
        self.assertTrue(has_perm(user, Perms.CIRC_CHECKOUT))
        self.assertTrue(has_perm(user, Perms.PATRONS_EDIT))
        self.assertFalse(has_perm(user, Perms.ACQ_MANAGE))

    def test_student_has_only_catalog_view(self):
        from core.testing import make_student

        from .permissions import Perms, has_perm
        user = make_student()
        self.assertTrue(has_perm(user, Perms.CATALOG_VIEW))
        self.assertFalse(has_perm(user, Perms.CIRC_CHECKOUT))

    def test_superuser_has_everything(self):
        from .permissions import Perms, has_perm
        root = User.objects.create(username='root', user_type='EMPLOYE', is_superuser=True)
        self.assertTrue(has_perm(root, Perms.SETTINGS_MANAGE))
        self.assertTrue(has_perm(root, Perms.ACQ_MANAGE))

    def test_anonymous_has_nothing(self):
        from .permissions import Perms, has_perm
        self.assertFalse(has_perm(AnonymousUser(), Perms.CATALOG_VIEW))

    def test_multiple_roles_union(self):
        from core.testing import make_employee

        from .permissions import Perms, has_perm
        user = make_employee(role=Roles.EMPLOYEE)
        acq_role = Role.objects.create(name="Ta'minotchi", permissions=[Perms.ACQ_MANAGE])
        user.employe_profile.roles.add(acq_role)

        self.assertTrue(has_perm(user, Perms.ACQ_MANAGE))
        self.assertTrue(has_perm(user, Perms.CATALOG_VIEW))

    def test_require_perm_decorator(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.testing import make_librarian, make_student

        from .permissions import Perms, require_perm

        @require_perm(Perms.CIRC_CHECKOUT)
        def view(request):
            return HttpResponse("ok")

        request = RequestFactory().get('/desk/')
        request.user = make_librarian()
        self.assertEqual(view(request).status_code, 200)

        request.user = make_student()
        self.assertEqual(view(request).status_code, 403)
