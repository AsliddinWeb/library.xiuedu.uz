from datetime import date, datetime

from django.test import TestCase

from oauth.views.student import _parse_birth_date


class ParseBirthDateTests(TestCase):
    def test_string_format(self):
        self.assertEqual(_parse_birth_date('15-08-2000'), date(2000, 8, 15))

    def test_bad_string(self):
        self.assertIsNone(_parse_birth_date('nonsense'))

    def test_none(self):
        self.assertIsNone(_parse_birth_date(None))
        self.assertIsNone(_parse_birth_date(''))

    def test_datetime(self):
        self.assertEqual(_parse_birth_date(datetime(1999, 1, 2, 3, 4)), date(1999, 1, 2))

    def test_int_timestamp(self):
        self.assertIsInstance(_parse_birth_date(946684800), date)
