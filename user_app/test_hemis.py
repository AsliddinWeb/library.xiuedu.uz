"""HEMIS ro'yxatlarini yuklash. Javob shakli HEMIS UNIVERSITY API 1.3 hujjati bo'yicha."""
from datetime import date, datetime, timedelta, timezone
from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.utils import timezone as django_timezone

from audit.models import JobRun
from core.jobs import registry, run_job
from core.testing import make_librarian, make_student
from user_app.hemis import sync
from user_app.hemis.client import HemisClient, HemisError
from user_app.models import Patron, PatronCategory, User
from user_app.roles import Roles

TOKEN = 'sinov-token'


def timestamp(year, month, day, hour=0):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp())


def student(number='311221100001', **extra):
    return {
        'id': 1, 'student_id_number': number,
        'first_name': 'DILNOZA', 'second_name': 'KARIMOVA', 'third_name': "ANVAR QIZI",
        'birth_date': timestamp(2004, 3, 15), 'gender': {'code': '12', 'name': 'Ayol'},
        'department': {'id': 3, 'name': 'Iqtisodiyot fakulteti'},
        'group': {'id': 7, 'name': 'IQ-22-01'}, 'level': {'code': '12', 'name': '2-kurs'},
        'semester': {'code': '13', 'name': '3-semestr'},
        'educationForm': {'code': '11', 'name': 'Kunduzgi'},
        'educationType': {'code': '11', 'name': 'Bakalavr'},
        'paymentForm': {'code': '11', 'name': "To'lov-shartnoma"},
        **extra,
    }


def employee(number=3112211, position="Dotsent", form="Asosiy ish joyi", **extra):
    return {
        'id': 5, 'employee_id_number': number, 'first_name': 'ANVAR', 'second_name': 'ALIYEV',
        'third_name': '', 'department': {'name': 'Matematika kafedrasi'},
        'staffPosition': {'code': '11', 'name': position},
        'employmentForm': {'code': '11', 'name': form}, 'active': True, **extra,
    }


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        if self.payload is None:
            raise ValueError('JSON emas')
        return self.payload


class FakeHemis:
    """`requests.Session` o'rniga: yo'l bo'yicha ro'yxatni sahifalab beradi."""

    def __init__(self, students=(), employees=(), failures=(), wrapped=False):
        self.rows = {'student-list': list(students), 'employee-list': list(employees)}
        self.failures = list(failures)
        self.wrapped = wrapped
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params), dict(headers)))
        if self.failures:
            failure = self.failures.pop(0)
            if isinstance(failure, Exception):
                raise failure
            return failure
        rows = self.rows[url.rsplit('/', 1)[1]]
        page, limit = params['page'], params['limit']
        pages = max(1, -(-len(rows) // limit))
        data = {'items': rows[(page - 1) * limit:page * limit],
                'pagination': {'totalCount': len(rows), 'pageSize': limit,
                               'pageCount': pages, 'page': page}}
        return FakeResponse({'success': True, 'code': 200,
                             'data': [data] if self.wrapped else data})


def client_for(fake):
    return HemisClient(TOKEN, base_url='https://hemis.test/rest', session=fake, sleep=lambda s: None)


class ClientTests(TestCase):
    def test_sends_bearer_token_and_walks_all_pages(self):
        fake = FakeHemis(students=[student(str(n)) for n in range(1, 451)])

        got = [row for rows, _ in client_for(fake).pages('v1/data/student-list') for row in rows]

        self.assertEqual(len(got), 450)
        self.assertEqual([call[1]['page'] for call in fake.calls], [1, 2, 3])
        url, params, headers = fake.calls[0]
        self.assertEqual(url, 'https://hemis.test/rest/v1/data/student-list')
        self.assertEqual(params['limit'], 200)
        self.assertEqual(headers['Authorization'], f'Bearer {TOKEN}')

    def test_accepts_data_wrapped_in_a_list(self):
        fake = FakeHemis(students=[student()], wrapped=True)

        items, pagination = client_for(fake).page('v1/data/student-list')

        self.assertEqual((len(items), pagination['totalCount']), (1, 1))

    def test_retries_temporary_failures(self):
        fake = FakeHemis(students=[student()], failures=[
            requests.ConnectionError(), FakeResponse(status=429), FakeResponse(status=502)])

        items, _ = client_for(fake).page('v1/data/student-list')

        self.assertEqual((len(items), len(fake.calls)), (1, 4))

    def test_bad_token_is_not_retried_and_never_echoed(self):
        fake = FakeHemis(failures=[FakeResponse(status=401)])

        with self.assertRaises(HemisError) as caught:
            client_for(fake).page('v1/data/student-list')

        self.assertEqual(len(fake.calls), 1)
        self.assertIn('401', str(caught.exception))
        self.assertNotIn(TOKEN, str(caught.exception))

    def test_unreadable_answers_become_messages(self):
        for response in (FakeResponse(None), FakeResponse({'success': False, 'error': 'yopiq'}),
                         FakeResponse({'success': True, 'data': {}}), FakeResponse(status=404)):
            with self.subTest(response=response.payload), self.assertRaises(HemisError):
                client_for(FakeHemis(failures=[response])).page('v1/data/student-list')

    def test_token_with_spaces_is_rejected_before_any_request(self):
        for token in ('', '  ', 'a b', 'tok\nen', 'tökën'):
            with self.subTest(token=token), self.assertRaises(HemisError):
                HemisClient(token, base_url='https://hemis.test/rest')


class SyncTests(TestCase):
    def sync(self, **rows):
        return sync.run(TOKEN, client=client_for(FakeHemis(**rows)))

    def test_new_student_gets_account_and_card(self):
        stats = self.sync(students=[student()])

        user = User.objects.get(username='311221100001')
        self.assertEqual((user.user_type, user.second_name, user.gender),
                         ('STUDENT', 'KARIMOVA', 'Ayol'))
        self.assertEqual(user.birth_day, date(2004, 3, 15))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.student_profile.group, 'IQ-22-01')
        self.assertEqual(user.student_profile.faculty, 'Iqtisodiyot fakulteti')
        self.assertEqual(user.patron.category.code, PatronCategory.Code.STUDENT)
        self.assertEqual(stats['students_new'], 1)

    def test_second_run_changes_nothing(self):
        self.sync(students=[student()], employees=[employee()])

        stats = self.sync(students=[student()], employees=[employee()])

        self.assertEqual((stats['students_same'], stats['employees_same']), (1, 1))
        self.assertEqual(Patron.objects.count(), 2)

    def test_update_keeps_contacts_and_card_number(self):
        self.sync(students=[student()])
        user = User.objects.get(username='311221100001')
        User.objects.filter(pk=user.pk).update(phone='+998900000000')
        card = user.patron.card_number

        stats = self.sync(students=[student(group={'name': 'IQ-22-02'}, third_name='',
                                            educationType={'name': 'Magistr'})])

        user = User.objects.get(pk=user.pk)
        self.assertEqual(stats['students_updated'], 1)
        self.assertEqual(user.student_profile.group, 'IQ-22-02')
        self.assertEqual((user.phone, user.third_name), ('+998900000000', 'ANVAR QIZI'))
        self.assertEqual(user.patron.card_number, card)
        self.assertEqual(user.patron.category.code, PatronCategory.Code.MASTER)

    def test_blocked_patron_stays_blocked(self):
        self.sync(students=[student()])
        Patron.objects.update(status=Patron.Status.BLOCKED, block_reason='qarz')

        self.sync(students=[student()])

        self.assertEqual(Patron.objects.get().status, Patron.Status.BLOCKED)

    def test_employee_uses_main_job_and_skips_dismissed(self):
        stats = self.sync(employees=[
            employee(position="Laborant", form="O'rindoshlik"),
            employee(position="Dotsent", form="Asosiy ish joyi"),
            employee(number=999, active=False),
        ])

        user = User.objects.get(username='3112211')
        self.assertEqual(user.employe_profile.position, 'Dotsent')
        self.assertEqual(user.employe_profile.current_role.name, Roles.EMPLOYEE)
        self.assertEqual(user.patron.category.code, PatronCategory.Code.TEACHER)
        self.assertFalse(User.objects.filter(username='999').exists())
        self.assertEqual(stats['employees_total'], 1)

    def test_librarian_keeps_role_and_gets_no_card(self):
        librarian = make_librarian('3112211')

        self.sync(employees=[employee()])

        librarian.employe_profile.refresh_from_db()
        self.assertEqual(librarian.employe_profile.current_role.name, Roles.LIBRARIAN)
        self.assertFalse(Patron.objects.filter(user=librarian).exists())

    def test_same_number_of_another_type_does_not_take_over(self):
        original = make_student('3112211')

        self.sync(employees=[employee()])

        original.refresh_from_db()
        self.assertEqual(original.user_type, 'STUDENT')
        self.assertTrue(User.objects.filter(username='emp-3112211', user_type='EMPLOYE').exists())

    def test_rows_without_id_or_name_are_skipped(self):
        stats = self.sync(students=[student(''), student('2', first_name='', second_name='')])

        self.assertEqual(stats['students_skipped'], 2)
        self.assertFalse(User.objects.exists())

    def test_one_broken_row_does_not_stop_the_rest(self):
        real = sync.sync_patron

        def flaky(user):
            if user.username == '1':
                raise RuntimeError('sinov')
            return real(user)

        with mock.patch.object(sync, 'sync_patron', flaky), self.assertLogs('hemis', 'ERROR'):
            stats = self.sync(students=[student('1'), student('2')])

        self.assertEqual((stats['students_failed'], stats['students_new']), (1, 1))
        self.assertFalse(User.objects.filter(username='1').exists())

    def test_preview_writes_nothing(self):
        client = client_for(FakeHemis(students=[student('1'), student('2')]))

        self.assertEqual(sync.preview(client, [sync.STUDENTS]), {'students': 2})
        self.assertFalse(User.objects.exists())


class RecordTests(TestCase):
    def record(self, **kwargs):
        return JobRun.objects.create(name=sync.JOB_NAME, status=JobRun.Status.RUNNING, **kwargs)

    def test_execute_stores_result(self):
        record = self.record()
        fake = FakeHemis(students=[student()])

        with mock.patch.object(sync, 'HemisClient', lambda token: client_for(fake)):
            sync.execute(record, TOKEN, [sync.STUDENTS])

        record.refresh_from_db()
        self.assertEqual(record.status, JobRun.Status.SUCCESS)
        self.assertIn('1 yangi', record.message)
        self.assertEqual(record.stats['students_done'], 1)

    def test_execute_records_failure_without_token(self):
        record = self.record()
        fake = FakeHemis(failures=[FakeResponse(status=403)])

        with mock.patch.object(sync, 'HemisClient', lambda token: client_for(fake)):
            sync.execute(record, TOKEN, [sync.STUDENTS])

        record.refresh_from_db()
        self.assertEqual(record.status, JobRun.Status.FAILED)
        self.assertNotIn(TOKEN, record.message + str(record.stats) + record.error)

    def test_interrupted_run_is_closed(self):
        record = self.record()
        old = django_timezone.now() - timedelta(hours=1)
        JobRun.objects.filter(pk=record.pk).update(started_at=old)

        self.assertFalse(sync.is_running())
        record.refresh_from_db()
        self.assertEqual(record.status, JobRun.Status.FAILED)

    def test_recent_heartbeat_keeps_it_running(self):
        record = self.record(stats={'beat': django_timezone.now().isoformat()})
        JobRun.objects.filter(pk=record.pk).update(
            started_at=django_timezone.now() - timedelta(hours=1))

        self.assertTrue(sync.is_running())

    def test_daily_sync_is_scheduled_only_with_a_server_token(self):
        def scheduled():
            return {entry['name'] for entry in registry('daily')}

        with override_settings(HEMIS_API_TOKEN=''):
            self.assertNotIn(sync.JOB_NAME, scheduled())
        with override_settings(HEMIS_API_TOKEN=TOKEN):
            self.assertIn(sync.JOB_NAME, scheduled())

    @override_settings(HEMIS_API_TOKEN=TOKEN)
    def test_daily_job_uses_server_token_and_reports_progress(self):
        def fake(token, progress):
            progress({'students_done': 100})
            self.assertEqual(token, TOKEN)
            self.assertIn('beat', JobRun.objects.get().stats)
            return {'students_done': 100}

        with mock.patch.object(sync, 'run', fake):
            record = run_job(sync.JOB_NAME)

        self.assertEqual(record.status, JobRun.Status.SUCCESS, record.message)
