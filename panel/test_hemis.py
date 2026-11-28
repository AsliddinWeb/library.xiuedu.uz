"""Paneldagi «HEMIS'dan yuklash» sahifasi."""
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from audit.models import ActionLog, JobRun
from core.testing import make_librarian
from user_app.hemis import sync
from user_app.hemis.client import HemisError

TOKEN = 'maxfiy-token-123'


@override_settings(HEMIS_API_TOKEN='')
class HemisPageTests(TestCase):
    def setUp(self):
        self.client.force_login(make_librarian())
        preview = mock.patch.object(sync, 'preview', return_value={'students': 4312, 'employees': 210})
        start = mock.patch.object(sync, 'start', return_value=object())
        self.preview, self.start = preview.start(), start.start()
        self.addCleanup(mock.patch.stopall)

    def post(self, name, **data):
        data.setdefault('kinds', ['students', 'employees'])
        return self.client.post(reverse(f'panel:{name}'), data, HTTP_HX_REQUEST='true')

    def test_page_and_link_from_members(self):
        self.assertContains(self.client.get(reverse('panel:hemis')), 'name="token"')
        self.assertContains(self.client.get(reverse('panel:members')), reverse('panel:hemis'))

    def test_check_shows_counts_and_writes_nothing(self):
        response = self.post('hemis_check', token=TOKEN)

        self.assertContains(response, '4\xa0312')
        self.assertNotContains(response, TOKEN)
        self.start.assert_not_called()

    def test_start_runs_in_background_and_is_audited(self):
        response = self.post('hemis_start', token=TOKEN, kinds=['students'])

        self.assertContains(response, 'Yuklash boshlandi')
        self.assertEqual(response['HX-Trigger'], 'hemis-started')
        self.start.assert_called_once_with(TOKEN, ['students'])
        entry = ActionLog.objects.get(action=ActionLog.Action.IMPORT)
        self.assertNotIn(TOKEN, entry.note + str(entry.changes) + entry.object_repr)

    def test_bad_token_does_not_start(self):
        self.preview.side_effect = HemisError("HEMIS tokenni qabul qilmadi (401).")

        response = self.post('hemis_start', token=TOKEN)

        self.assertContains(response, 'qabul qilmadi')
        self.start.assert_not_called()

    def test_missing_token_or_choice(self):
        self.assertContains(self.post('hemis_check'), 'tokeni kiritilmagan')
        self.assertContains(self.post('hemis_check', token=TOKEN, kinds=[]), 'Kamida bittasini')

    @override_settings(HEMIS_API_TOKEN='server-token')
    def test_server_token_is_used_when_field_is_empty_and_not_shown(self):
        self.post('hemis_start', kinds=['employees'])

        self.start.assert_called_once_with('server-token', ['employees'])
        self.assertNotContains(self.client.get(reverse('panel:hemis')), 'server-token')

    def test_already_running(self):
        self.start.return_value = None

        self.assertContains(self.post('hemis_start', token=TOKEN), 'allaqachon ishlayapti')

    def test_status_polls_only_while_running(self):
        run = JobRun.objects.create(name=sync.JOB_NAME, status=JobRun.Status.RUNNING,
                                    stats={'students_total': 200, 'students_done': 50,
                                           'beat': '2999-01-01T00:00:00+00:00'})
        running = self.client.get(reverse('panel:hemis_status'))
        self.assertContains(running, 'every 2s')
        self.assertContains(running, 'width: 25%')

        run.status = JobRun.Status.SUCCESS
        run.save()
        self.assertNotContains(self.client.get(reverse('panel:hemis_status')), 'every 2s')
