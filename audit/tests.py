from django.core.management import call_command
from django.test import RequestFactory, TestCase

from core.jobs import _REGISTRY, discover, job, registry, run_job
from core.testing import make_book, make_librarian

from .context import clear_context, current_actor, set_context
from .middleware import AuditContextMiddleware
from .models import ActionLog, JobRun
from .services import diff, log_action, log_change, snapshot


class AuditContextTests(TestCase):
    def tearDown(self):
        clear_context()

    def test_middleware_sets_authenticated_actor(self):
        user = make_librarian()
        request = RequestFactory().get('/panel/')
        request.user = user

        seen = {}

        def view(req):
            seen['actor'] = current_actor()
            return 'ok'

        AuditContextMiddleware(view)(request)
        self.assertEqual(seen['actor'], user)
        # So'rov tugagach kontekst tozalanadi
        self.assertIsNone(current_actor())

    def test_anonymous_actor_is_none(self):
        from django.contrib.auth.models import AnonymousUser
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        seen = {}
        AuditContextMiddleware(lambda r: seen.setdefault('actor', current_actor()))(request)
        self.assertIsNone(seen['actor'])


class LogActionTests(TestCase):
    def tearDown(self):
        clear_context()

    def test_log_action_uses_context(self):
        user = make_librarian()
        set_context(actor=user, ip='10.0.0.7', user_agent='pytest', path='/panel/books/')
        book = make_book("Algoritmlar")

        entry = log_action(ActionLog.Action.BIBLIO_CREATE, obj=book, note="test")

        self.assertEqual(entry.actor, user)
        self.assertEqual(entry.ip, '10.0.0.7')
        self.assertEqual(entry.path, '/panel/books/')
        self.assertEqual(entry.object_type, 'book_app.Book')
        self.assertEqual(entry.object_id, str(book.pk))
        self.assertIn("Algoritmlar", entry.object_repr)

    def test_system_actor_when_no_context(self):
        entry = log_action(ActionLog.Action.JOB, note="cron")
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_label, 'tizim')

    def test_snapshot_and_diff(self):
        book = make_book("Eski nom")
        before = snapshot(book)
        book.title = "Yangi nom"
        book.view_count = 5
        book.save()

        changes = diff(before, snapshot(book))
        self.assertEqual(changes['title'], ["Eski nom", "Yangi nom"])
        self.assertEqual(changes['view_count'], [0, 5])
        self.assertNotIn('category', changes)

    def test_log_change_skips_when_nothing_changed(self):
        book = make_book()
        before = snapshot(book)
        self.assertIsNone(log_change(ActionLog.Action.BIBLIO_EDIT, book, before))
        self.assertEqual(ActionLog.objects.count(), 0)

    def test_log_change_records_only_changed_fields(self):
        book = make_book("Nom")
        before = snapshot(book)
        book.title = "Boshqa nom"
        book.save()

        entry = log_change(ActionLog.Action.BIBLIO_EDIT, book, before)
        self.assertEqual(list(entry.changes), ['title'])

    def test_log_action_never_raises(self):
        """Audit xatosi asosiy oqimni buzmasligi kerak."""
        entry = log_action(ActionLog.Action.OTHER, note="x" * 500)
        self.assertIsNotNone(entry)
        self.assertEqual(len(entry.note), 300)


class JobRegistryTests(TestCase):
    """Vazifa reyestri: ro'yxat, natija, xato."""

    def setUp(self):
        # Reyestr global holat — avval app'lardagi `jobs` modullari yuklanadi,
        # keyin nusxa olinadi, test oxirida aynan shu holat tiklanadi.
        discover()
        self._saved = dict(_REGISTRY)

    def tearDown(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._saved)

    def test_successful_job_is_logged(self):
        @job('t_ok', "Test vazifa", schedule='manual')
        def _ok():
            return {'done': 3}

        run = run_job('t_ok')
        self.assertEqual(run.status, JobRun.Status.SUCCESS)
        self.assertEqual(run.stats, {'done': 3})
        self.assertIn('done=3', run.message)
        self.assertIsNotNone(run.finished_at)
        self.assertIsNotNone(run.duration_ms)

    def test_failing_job_is_logged_without_raising(self):
        @job('t_fail', "Xato vazifa", schedule='manual')
        def _fail():
            raise ValueError("sinov xatosi")

        run = run_job('t_fail')
        self.assertEqual(run.status, JobRun.Status.FAILED)
        self.assertIn("sinov xatosi", run.message)
        self.assertIn("ValueError", run.error)

    def test_unknown_job_raises(self):
        with self.assertRaises(KeyError):
            run_job('yoq_bunday_vazifa')

    def test_duplicate_registration_raises(self):
        @job('t_dup', "Birinchi", schedule='manual')
        def _first():
            return {}

        with self.assertRaises(ValueError):
            @job('t_dup', "Ikkinchi", schedule='manual')
            def _second():
                return {}

    def test_circulation_jobs_are_registered(self):
        names = {entry['name'] for entry in registry('daily')}
        self.assertTrue({'due_soon_notices', 'fines_accrual', 'reservation_expiry'} <= names)

    def test_run_jobs_command(self):
        call_command('run_jobs', 'fines_accrual')
        self.assertTrue(JobRun.objects.filter(name='fines_accrual',
                                              status=JobRun.Status.SUCCESS).exists())


class FeatureFlagTests(TestCase):
    def test_settings_override(self):
        from core.flags import all_flags, flag_enabled
        with self.settings(FEATURE_FLAGS={'acquisitions': True}):
            self.assertTrue(flag_enabled('acquisitions'))
            self.assertTrue(all_flags()['acquisitions'])

    def test_env_override_wins(self):
        import os

        from core.flags import flag_enabled
        os.environ['FLAG_ACQUISITIONS'] = '1'
        try:
            self.assertTrue(flag_enabled('acquisitions'))
            os.environ['FLAG_ACQUISITIONS'] = '0'
            with self.settings(FEATURE_FLAGS={'acquisitions': True}):
                self.assertFalse(flag_enabled('acquisitions'))
        finally:
            os.environ.pop('FLAG_ACQUISITIONS', None)

    def test_unknown_flag_is_false(self):
        from core.flags import flag_enabled
        self.assertFalse(flag_enabled('bunday_flag_yoq'))

    def test_flags_in_template_context(self):
        from core.context_processors import feature_flags
        context = feature_flags(RequestFactory().get('/'))
        self.assertIn('flags', context)
        self.assertIn('design_v3', context['flags'])
