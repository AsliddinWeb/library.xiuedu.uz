"""Kunlik vazifalarning sayt ichidan ishga tushishi (`core/autojobs.py`)."""
from datetime import datetime, timedelta
from unittest import mock

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from audit.models import JobRun
from core import autojobs
from core.jobs import _REGISTRY, discover

DAILY = {'due_soon_notices', 'fines_accrual', 'reservation_expiry'}


def _at(hour):
    """Bugungi kunning berilgan soati (Toshkent vaqti)."""
    today = timezone.localdate()
    return timezone.make_aware(datetime(today.year, today.month, today.day, hour, 0))


class DueJobsTests(TestCase):
    def test_first_run_executes_every_daily_job(self):
        runs = autojobs.run_due_jobs()

        self.assertEqual({run.name for run in runs}, DAILY)
        self.assertTrue(all(run.status == JobRun.Status.SUCCESS for run in runs))

    def test_second_run_same_day_does_nothing(self):
        autojobs.run_due_jobs()

        self.assertEqual(autojobs.run_due_jobs(), [])
        self.assertEqual(JobRun.objects.count(), len(DAILY))

    def test_yesterdays_success_does_not_count(self):
        autojobs.run_due_jobs()
        JobRun.objects.update(started_at=timezone.now() - timedelta(days=1))

        self.assertEqual(set(autojobs.due_jobs()), DAILY)

    def test_failed_job_is_retried_up_to_the_limit(self):
        discover()

        def boom():
            raise ValueError("sinov")

        entry = {'name': 't_boom', 'func': boom, 'description': '', 'schedule': 'daily'}
        with mock.patch.dict(_REGISTRY, {'t_boom': entry}, clear=True):
            for _ in range(autojobs.MAX_ATTEMPTS):
                self.assertEqual([r.status for r in autojobs.run_due_jobs()],
                                 [JobRun.Status.FAILED])
            self.assertEqual(autojobs.run_due_jobs(), [])

    @skipUnlessDBFeature('has_select_for_update')
    def test_another_process_holding_the_lock_blocks_the_run(self):
        if connection.vendor != 'postgresql':
            self.skipTest("advisory lock faqat PostgreSQL'da")
        other = connections.create_connection('default')
        try:
            with other.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_lock(%s)', [autojobs.LOCK_KEY])
            self.assertEqual(autojobs.run_due_jobs(), [])
        finally:
            other.close()
        self.assertEqual(JobRun.objects.count(), 0)


@override_settings(AUTO_JOBS=True, AUTO_JOBS_HOUR=6)
class TriggerTests(TestCase):
    def setUp(self):
        autojobs._next_check = 0.0
        self.addCleanup(setattr, autojobs, '_next_check', 0.0)
        patcher = mock.patch.object(autojobs.threading, 'Thread')
        self.thread = patcher.start()
        self.addCleanup(patcher.stop)

    def _clock(self, hour):
        return mock.patch.object(autojobs.timezone, 'localtime', return_value=_at(hour))

    def test_request_starts_the_worker_once(self):
        with self._clock(9):
            self.client.get('/')
            self.client.get('/')

        self.assertEqual(self.thread.call_count, 1)
        self.thread.return_value.start.assert_called_once_with()

    def test_checks_again_after_the_interval(self):
        with self._clock(9):
            autojobs.maybe_start()
            autojobs._next_check -= autojobs.CHECK_EVERY + 1
            autojobs.maybe_start()

        self.assertEqual(self.thread.call_count, 2)

    def test_nothing_before_the_start_hour(self):
        with self._clock(3):
            self.assertIsNone(autojobs.maybe_start())
        with self._clock(6):
            self.assertIsNotNone(autojobs.maybe_start())

    @override_settings(AUTO_JOBS=False)
    def test_disabled(self):
        with self._clock(9):
            self.client.get('/')

        self.thread.assert_not_called()


@override_settings(AUTO_JOBS=True, AUTO_JOBS_HOUR=0)
class ThreadTests(TransactionTestCase):
    """Haqiqiy fon oqimi: o'z baza ulanishi bilan ishlaydi."""

    def test_thread_runs_the_jobs(self):
        autojobs._next_check = 0.0
        self.addCleanup(setattr, autojobs, '_next_check', 0.0)

        thread = autojobs.maybe_start()
        thread.join(timeout=30)

        self.assertFalse(thread.is_alive())
        self.assertEqual(
            set(JobRun.objects.filter(status=JobRun.Status.SUCCESS)
                .values_list('name', flat=True)),
            DAILY)
