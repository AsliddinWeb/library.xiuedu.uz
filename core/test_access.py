"""
Kirish matritsasi: qaysi hisob turi qaysi sahifani ochadi va qanday.

Bu fayl `claude-files/11-ROLES.md` dagi jadvalning bajariladigan nusxasi.
Yangi sahifa qo'shilsa — shu yerga ham qo'shiladi.

Belgilar:
    OK      — sahifa ochiladi (200)
    LOGIN   — kirish tanlovi sahifasiga yo'naltiradi
    DENY    — 403
    PANEL   — kutubxona paneliga yo'naltiradi
    ADMIN   — admin panelga yo'naltiradi
    A_LOGIN — Django admin'ning o'z parol sahifasi
"""
import re
from datetime import timedelta

from django.test import TestCase
from django.urls import URLPattern, reverse
from django.utils.timezone import now

from book_app.models import Rental
from circulation.models import RentalRequest
from core.testing import (
    make_admin,
    make_book,
    make_copies,
    make_employee,
    make_librarian,
    make_student,
    make_teacher,
)
from panel import urls as panel_urls
from user_app.models import Patron, Role
from user_app.permissions import ROLE_PRESETS, Perms, user_permissions
from user_app.roles import AccountKind, Roles, account_kind
from user_app.services import get_or_create_patron, sync_patron

OK, LOGIN, DENY, PANEL, ADMIN, A_LOGIN = 'OK', 'LOGIN', 'DENY', 'PANEL', 'ADMIN', 'A_LOGIN'

ACTORS = ('guest', 'student', 'employee', 'librarian', 'admin')

#: manzil: (mehmon, talaba, HEMIS xodimi, kutubxona xodimi, admin)
PAGES = {
    # --- Umumiy ---
    '/':                          (OK,    OK,   OK,   OK,    OK),
    '/books/':                    (LOGIN, OK,   OK,   OK,    OK),
    '/books/{book}/':             (LOGIN, OK,   OK,   OK,    OK),
    '/books/courses/':            (LOGIN, OK,   OK,   OK,    OK),
    '/engagement/lists/':         (LOGIN, OK,   OK,   OK,    OK),
    # --- Faqat o'quvchi ---
    '/dashboard/':                (LOGIN, OK,   OK,   PANEL, ADMIN),
    '/circulation/my-rentals/':   (LOGIN, OK,   OK,   PANEL, ADMIN),
    '/engagement/my-library/':    (LOGIN, OK,   OK,   PANEL, ADMIN),
    '/profil/':                   (LOGIN, OK,   OK,   PANEL, PANEL),
    '/notifications/':            (LOGIN, OK,   OK,   PANEL, PANEL),
    # --- Fan adabiyoti yaratish: o'qituvchi va katalog xodimi ---
    '/books/courses/new/':        (LOGIN, DENY, DENY, OK,    OK),
    # --- Kutubxona paneli ---
    '/panel/':                    (LOGIN, DENY, DENY, OK,    OK),
    '/panel/desk/':               (LOGIN, DENY, DENY, OK,    OK),
    '/panel/books/':              (LOGIN, DENY, DENY, OK,    OK),
    '/panel/books/{book}/':       (LOGIN, DENY, DENY, OK,    OK),
    '/panel/items/':              (LOGIN, DENY, DENY, OK,    OK),
    '/panel/items/{item}/':       (LOGIN, DENY, DENY, OK,    OK),
    '/panel/genres/':             (LOGIN, DENY, DENY, OK,    OK),
    '/panel/authors/':            (LOGIN, DENY, DENY, OK,    OK),
    '/panel/publishers/':         (LOGIN, DENY, DENY, OK,    OK),
    '/panel/series/':             (LOGIN, DENY, DENY, OK,    OK),
    '/panel/subjects/':           (LOGIN, DENY, DENY, OK,    OK),
    '/panel/categories/':         (LOGIN, DENY, DENY, OK,    OK),
    '/panel/reservations/':       (LOGIN, DENY, DENY, OK,    OK),
    '/panel/fines/':              (LOGIN, DENY, DENY, OK,    OK),
    '/panel/requests/':           (LOGIN, DENY, DENY, OK,    OK),
    '/panel/rentals/':            (LOGIN, DENY, DENY, OK,    OK),
    '/panel/members/':            (LOGIN, DENY, DENY, OK,    OK),
    '/panel/members/{patron}/':   (LOGIN, DENY, DENY, OK,    OK),
    '/panel/members/hemis/':      (LOGIN, DENY, DENY, OK,    OK),
    '/panel/labels/':             (LOGIN, DENY, DENY, OK,    OK),
    '/panel/labels/copies/':      (LOGIN, DENY, DENY, OK,    OK),
    '/panel/labels/cards/':       (LOGIN, DENY, DENY, OK,    OK),
    '/panel/analytics/':          (LOGIN, DENY, DENY, OK,    OK),
    '/panel/settings/':           (LOGIN, DENY, DENY, OK,    OK),
    '/panel/profile/':            (LOGIN, DENY, DENY, OK,    OK),
    '/panel/notifications/':      (LOGIN, DENY, DENY, OK,    OK),
    '/_design/':                  (LOGIN, DENY, DENY, OK,    OK),
    # --- Tizim administratori ---
    '/admin/':                    (A_LOGIN, A_LOGIN, A_LOGIN, A_LOGIN, OK),
}

#: O'quvchi amallari (POST): kutubxona xodimi va admin bajara olmaydi
READER_ACTIONS = (
    '/circulation/books/{book}/request/',
    '/circulation/books/{book}/request/cancel/',
    '/circulation/books/{book}/reserve/',
    '/circulation/books/{book}/reserve/cancel/',
    '/engagement/books/{book}/favorite/',
    '/engagement/books/{book}/review/',
)


class AccessFixture(TestCase):
    def setUp(self):
        self.users = {
            'guest': None,
            'student': make_student(first_name='Qurbon', second_name='Talabayev'),
            'employee': make_employee(role=Roles.EMPLOYEE),
            'librarian': make_librarian(),
            'admin': make_admin(),
        }
        victim = make_student(first_name='Maxfiy', second_name='Odamov')
        self.patron = get_or_create_patron(victim)
        self.book = make_book("Sinov kitobi")
        self.item = make_copies(self.book, 1)[0]
        Rental.objects.create(copy=self.item, patron=self.patron,
                              borrowed_date=now().date() - timedelta(days=30),
                              due_date=now().date() - timedelta(days=3))
        RentalRequest.objects.create(patron=self.patron, book=make_book("So'ralgan"))

    def url(self, pattern):
        return pattern.format(book=self.book.pk, item=self.item.pk, patron=self.patron.pk)

    def login(self, actor):
        self.client.logout()
        if self.users[actor] is not None:
            self.client.force_login(self.users[actor])

    def outcome(self, response):
        if response.status_code == 200:
            return OK
        if response.status_code == 403:
            return DENY
        location = response.headers.get('Location', '')
        if location.startswith('/auth/login/'):
            return LOGIN
        if location.startswith('/admin/login/'):
            return A_LOGIN
        if location.startswith('/panel/'):
            return PANEL
        if location == '/admin/':
            return ADMIN
        return f'{response.status_code} {location}'


class AccessMatrixTests(AccessFixture):
    def test_pages(self):
        for pattern, expected in PAGES.items():
            for actor, want in zip(ACTORS, expected, strict=True):
                with self.subTest(page=pattern, actor=actor):
                    self.login(actor)
                    self.assertEqual(self.outcome(self.client.get(self.url(pattern))), want)

    def test_staff_cannot_do_reader_actions(self):
        for actor in ('librarian', 'admin'):
            self.login(actor)
            for pattern in READER_ACTIONS:
                with self.subTest(actor=actor, action=pattern):
                    response = self.client.post(self.url(pattern), HTTP_HX_REQUEST='true')
                    self.assertEqual(response.status_code, 403)
        self.assertFalse(Patron.objects.filter(
            user__in=[self.users['librarian'], self.users['admin']]).exists())

    def test_every_panel_route_is_closed_to_readers(self):
        """Yangi view qo'shilib dekorator unutilsa ham panel yopiq qoladi."""
        patterns = [p for p in panel_urls.urlpatterns if isinstance(p, URLPattern)]
        self.assertGreater(len(patterns), 30)
        for pattern in patterns:
            kwargs = {name: 'library' if name == 'kind' else 1
                      for name in pattern.pattern.converters}
            url = reverse(f'panel:{pattern.name}', kwargs=kwargs)
            for actor in ('student', 'employee'):
                self.login(actor)
                for method in (self.client.get, self.client.post):
                    with self.subTest(url=url, actor=actor, method=method.__name__):
                        self.assertEqual(method(url).status_code, 403)

    def test_borrower_names_never_reach_readers(self):
        for actor in ('student', 'employee'):
            self.login(actor)
            for pattern in ('/panel/', self.url('/panel/items/{item}/')):
                response = self.client.get(self.url(pattern))
                self.assertNotIn(b'ODAMOV', response.content)


class AccountKindTests(TestCase):
    def test_kinds(self):
        self.assertEqual(account_kind(make_student()), AccountKind.READER)
        self.assertEqual(account_kind(make_employee()), AccountKind.READER)
        self.assertEqual(account_kind(make_employee(role=Roles.EMPLOYEE)), AccountKind.READER)
        self.assertEqual(account_kind(make_teacher()), AccountKind.READER)
        self.assertEqual(account_kind(make_librarian()), AccountKind.LIBRARIAN)
        self.assertEqual(account_kind(make_admin()), AccountKind.ADMIN)
        self.assertEqual(account_kind(make_employee(role=Roles.ADMIN)), AccountKind.ADMIN)

    def test_reader_roles_grant_nothing_even_if_stored_in_database(self):
        Role.objects.update_or_create(name=Roles.EMPLOYEE,
                                      defaults={'permissions': [Perms.CATALOG_VIEW, '*']})
        user = make_employee(role=Roles.EMPLOYEE)
        self.assertEqual(user_permissions(user), set())
        self.assertEqual(account_kind(user), AccountKind.READER)

    def test_custom_staff_role_sees_only_its_part(self):
        user = make_employee()
        role = Role.objects.create(name="Zal xodimi",
                                   permissions=[Perms.CATALOG_VIEW, Perms.ROOM_DESK])
        user.employe_profile.roles.add(role)

        self.assertEqual(account_kind(user), AccountKind.LIBRARIAN)
        self.client.force_login(user)
        panel = self.client.get('/panel/')
        self.assertEqual(panel.status_code, 200)
        self.assertNotContains(panel, 'href="/panel/members/"')
        self.assertNotContains(panel, 'href="/panel/requests/"')
        self.assertContains(panel, 'href="/panel/books/"')
        self.assertEqual(self.client.get('/panel/members/').status_code, 403)
        self.assertEqual(self.client.get('/panel/requests/').status_code, 403)

    def test_custom_role_without_circulation_does_not_see_names(self):
        victim = get_or_create_patron(make_student(second_name='Odamov', first_name='Maxfiy'))
        book = make_book("Berilgan")
        item = make_copies(book, 1)[0]
        Rental.objects.create(copy=item, patron=victim,
                              borrowed_date=now().date() - timedelta(days=30),
                              due_date=now().date() - timedelta(days=3))
        user = make_employee()
        role = Role.objects.create(name="Ko'ruvchi", permissions=[Perms.CATALOG_VIEW])
        user.employe_profile.roles.add(role)
        self.client.force_login(user)

        for url in ('/panel/', f'/panel/items/{item.pk}/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b'ODAMOV', response.content)


class PresetRoleTests(TestCase):
    """Migratsiya bilan keladigan ish o'rinlari: har biri faqat o'z ishini ko'radi."""

    #: manzil: (Kataloglovchi, Abonement xodimi)
    PAGES = {
        '/panel/':              (200, 200),
        '/panel/desk/':         (403, 200),
        '/panel/books/':        (200, 200),
        '/panel/books/new/':    (200, 403),
        '/panel/items/':        (200, 200),
        '/panel/authors/new/':  (200, 403),
        '/panel/holdings/':     (200, 403),
        '/panel/import/':       (200, 403),
        '/panel/requests/':     (403, 200),
        '/panel/rentals/':      (403, 200),
        '/panel/reservations/': (403, 200),
        '/panel/fines/':        (403, 200),
        '/panel/members/':      (403, 200),
        '/panel/members/new/':  (403, 200),
        '/panel/reviews/':      (403, 403),
        '/panel/analytics/':    (403, 403),
        '/panel/settings/':     (403, 403),
        '/panel/categories/':   (403, 403),
        '/panel/profile/':      (200, 200),
    }

    def test_presets_open_only_their_pages(self):
        for index, name in enumerate(("Kataloglovchi", "Abonement xodimi")):
            role = Role.objects.get(name=name)
            self.assertEqual(sorted(role.permissions), sorted(ROLE_PRESETS[name]))
            user = make_employee()
            user.employe_profile.roles.add(role)
            self.client.force_login(user)
            self.assertEqual(account_kind(user), AccountKind.LIBRARIAN)
            for url, expected in self.PAGES.items():
                with self.subTest(role=name, url=url):
                    self.assertEqual(self.client.get(url).status_code, expected[index])

    def test_menu_never_links_to_a_closed_page(self):
        """Menyudagi har bir panel havolasi shu rol uchun ochiladi."""
        users = [make_librarian()]
        for name in ("Kataloglovchi", "Abonement xodimi"):
            user = make_employee()
            user.employe_profile.roles.add(Role.objects.get(name=name))
            users.append(user)
        for user in users:
            self.client.force_login(user)
            page = self.client.get('/panel/').content.decode()
            links = set(re.findall(r'href="(/panel/[^"#]*)"', page))
            self.assertTrue(links)
            for url in sorted(links):
                with self.subTest(user=user.username, url=url):
                    self.assertIn(self.client.get(url).status_code, (200, 302))


class StaffDoNotBorrowTests(TestCase):
    def test_no_patron_card_for_staff(self):
        for user in (make_librarian(), make_admin()):
            with self.subTest(user.username):
                self.assertIsNone(sync_patron(user))
                self.assertIsNone(get_or_create_patron(user))
                self.assertFalse(Patron.objects.filter(user=user).exists())

    def test_reader_who_became_staff_cannot_borrow(self):
        user = make_employee()
        patron = get_or_create_patron(user)
        self.assertTrue(patron.can_borrow()[0])

        role, _ = Role.objects.get_or_create(name=Roles.LIBRARIAN)
        user.employe_profile.roles.add(role)
        patron = Patron.objects.get(pk=patron.pk)

        allowed, reason = patron.can_borrow()
        self.assertFalse(allowed)
        self.assertIn("Kutubxona xodimi", reason)

    def test_book_page_in_staff_view(self):
        book = make_book("Ko'rinadigan", copies=1)
        self.client.force_login(make_librarian())
        response = self.client.get(f'/books/{book.pk}/')
        self.assertContains(response, "Xodim ko")
        self.assertNotContains(response, f'/circulation/books/{book.pk}/request/')
        self.assertNotContains(response, f'/engagement/books/{book.pk}/favorite/')
        self.assertContains(response, f'/panel/books/{book.pk}/')

    def test_staff_reading_is_not_counted(self):
        book = make_book("Raqamli", electronic_version='ebooks/x.pdf')
        self.client.force_login(make_librarian())
        self.assertEqual(self.client.get(f'/reading/read/{book.pk}/').status_code, 200)
        self.client.post(f'/reading/progress/{book.pk}/', {'position': 3, 'percent': 10})
        book.refresh_from_db()
        self.assertEqual(book.view_count, 0)
        self.assertEqual(book.reading_history.count() + book.reading_progress.count(), 0)
