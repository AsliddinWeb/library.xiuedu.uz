"""`convert_db_utf8` buyrug'i va fon ishining natijani saqlashi."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import TestCase

from audit.management.commands import convert_db_utf8 as command
from audit.models import JobRun
from core import background

ASCII = {'encoding': 'SQL_ASCII', 'owner': 'library_user', 'user': 'library_user',
         'can_create': True, 'others': 0}


class ConvertDatabaseTests(TestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest("faqat PostgreSQL")

    def run_command(self, *args, **info):
        out = StringIO()
        with mock.patch.object(command, 'inspect', return_value={**ASCII, **info}), \
                mock.patch.object(command.Command, '_convert') as convert:
            call_command('convert_db_utf8', *args, stdout=out)
        return out.getvalue(), convert

    def test_utf8_database_is_left_alone(self):
        out = StringIO()

        call_command('convert_db_utf8', '--apply', stdout=out)

        self.assertIn('allaqachon UTF8', out.getvalue())

    def test_without_apply_only_reports(self):
        text, convert = self.run_command()

        self.assertIn('Hech narsa o\'zgarmadi', text)
        convert.assert_not_called()

    def test_missing_rights_show_the_exact_commands(self):
        text, _ = self.run_command(can_create=False, owner='postgres')

        self.assertIn('ALTER ROLE "library_user" CREATEDB', text)
        self.assertIn('OWNER TO "library_user"', text)
        with self.assertRaisesMessage(CommandError, 'Ruxsat yetmaydi'):
            self.run_command('--apply', can_create=False)

    def test_open_connections_block_the_conversion(self):
        with self.assertRaisesMessage(CommandError, 'systemctl stop library'):
            self.run_command('--apply', others=3)

    def test_apply_converts_when_everything_is_ready(self):
        with mock.patch.object(command.shutil, 'which', return_value='/usr/bin/tool'):
            _, convert = self.run_command('--apply')

        convert.assert_called_once()


class FinishTests(TestCase):
    def test_result_is_saved_even_if_counters_cannot_be(self):
        record = JobRun.objects.create(name='t', status=JobRun.Status.RUNNING)
        real = JobRun.save

        def save(instance, *args, **kwargs):
            if 'stats' in kwargs.get('update_fields', ()):
                raise DatabaseError('unsupported Unicode escape sequence')
            return real(instance, *args, **kwargs)

        with mock.patch.object(JobRun, 'save', save), self.assertLogs('jobs', 'ERROR'):
            background.finish(record, JobRun.Status.FAILED, 'Xato matni')

        record.refresh_from_db()
        self.assertEqual((record.status, record.message), (JobRun.Status.FAILED, 'Xato matni'))
