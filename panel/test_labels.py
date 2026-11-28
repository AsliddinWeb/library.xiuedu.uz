"""Kitob yorlig'i va a'zo kartasini chop etish."""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from audit.models import ActionLog
from book_app.models import Item
from circulation.lookup import exact_items, exact_patrons
from core.testing import make_book, make_employee, make_librarian
from panel.printing import (
    CARD_PAPERS,
    COPY_PAPERS,
    QUIET,
    barcode_modules,
    barcode_svg,
    pick_paper,
    printable,
    sheets,
)
from user_app.models import Patron, Role, User
from user_app.services import get_or_create_patron


class BarcodeTests(SimpleTestCase):
    def test_modules_are_a_complete_code128_symbol(self):
        modules = barcode_modules('XIU000000001')

        self.assertEqual(set(modules), {'0', '1'})
        self.assertTrue(modules.startswith('11010'))          # boshlanish belgisi
        self.assertTrue(modules.endswith('1100011101011'))    # tugash belgisi
        self.assertNotEqual(modules, barcode_modules('XIU000000002'))

    def test_svg_draws_every_bar_with_quiet_zones(self):
        modules = barcode_modules('XIU-000001')

        svg = barcode_svg('XIU-000001')

        self.assertIn(f'viewBox="0 0 {len(modules) + 2 * QUIET} 100"', svg)
        runs = [run for run in modules.split('0') if run]
        self.assertEqual(svg.count('M'), len(runs))
        self.assertIn(f'M{QUIET} 0h2', svg)

    def test_value_is_escaped(self):
        self.assertNotIn('<b>', barcode_svg('<b>"1'))

    def test_only_plain_ascii_is_printable(self):
        self.assertTrue(printable('INV-9/1'))
        for value in ('', None, 'KOD‘1', 'Қ-1', ' 12', 'a\tb'):
            with self.subTest(value=value):
                self.assertFalse(printable(value))


class SheetTests(SimpleTestCase):
    def test_used_cells_are_skipped_only_on_first_sheet(self):
        paper = pick_paper(COPY_PAPERS, 'a4-24')

        pages = sheets(list(range(1, 31)), paper, skip=5)

        self.assertEqual([len(page) for page in pages], [24, 11])
        self.assertEqual(pages[0][:6], [None] * 5 + [1])

    def test_skip_is_limited_and_empty_selection_has_no_sheet(self):
        self.assertEqual(sheets([1], pick_paper(COPY_PAPERS, 't58'), skip=9), [[1]])
        self.assertEqual(sheets([], pick_paper(CARD_PAPERS, 'a4-10'), skip=3), [])

    def test_unknown_paper_falls_back_to_first(self):
        self.assertEqual(pick_paper(CARD_PAPERS, 'yo\'q').code, 'a4-10')

    def test_a4_grids_fit_the_page(self):
        for paper in (*COPY_PAPERS, *CARD_PAPERS):
            with self.subTest(paper=paper.code):
                self.assertLessEqual(paper.label[0] * paper.columns, paper.page[0])
                self.assertLessEqual(paper.label[1] * paper.rows, paper.page[1])


class CopyLabelTests(TestCase):
    def setUp(self):
        self.client.force_login(make_librarian())
        self.book = make_book("Algoritmlar", copies=3)
        self.items = list(Item.objects.filter(book=self.book).order_by('pk'))
        for number, item in enumerate(self.items[:2], start=1):
            item.barcode = f'XIU90000000{number}'
            item.save(update_fields=['barcode'])
        Item.objects.filter(pk=self.items[2].pk).update(barcode=None)
        self.url = reverse('panel:labels_copies')

    def codes(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return [entry['item'].barcode for sheet in response.context['sheets']
                for entry in sheet if entry]

    def test_sheet_keeps_every_row_even_when_not_full(self):
        response = self.client.get(self.url, {'book': self.book.pk, 'paper': 'a4-24'})

        self.assertContains(response, '--columns: 3; --rows: 8;')

    def test_nothing_is_printed_without_a_condition(self):
        for params in ({}, {'paper': 't58'}, {'book': 'abc'}, {'since': 'kecha'}, {'ids': 'x'},
                       {'numbers': ' , '}, {'since': '2026-13-45'}):
            with self.subTest(params=params):
                self.assertEqual(self.codes(**params), [])

    def test_book_selection_reports_copies_without_barcode_and_changes_nothing(self):
        response = self.client.get(self.url, {'book': self.book.pk})

        self.assertEqual(response.context['count'], 2)
        self.assertEqual(response.context['without_barcode'], 1)
        self.assertContains(response, 'Shtrix-kod berish')
        self.assertContains(response, '<svg class="barcode"', count=2)
        self.assertFalse(Item.objects.get(pk=self.items[2].pk).barcode)

    def test_assigning_barcodes_returns_to_the_same_selection(self):
        response = self.client.post(reverse('panel:labels_barcodes'),
                                    {'book': self.book.pk, 'paper': 't58'})

        self.assertRedirects(response, f'{self.url}?book={self.book.pk}&paper=t58')
        code = Item.objects.get(pk=self.items[2].pk).barcode
        self.assertEqual(code, 'XIU900000003')
        self.assertEqual(len(self.codes(book=self.book.pk)), 3)
        self.assertTrue(ActionLog.objects.filter(action=ActionLog.Action.ITEM_EDIT,
                                                 note__contains=code).exists())

    def test_assigning_without_a_condition_does_nothing(self):
        self.client.post(reverse('panel:labels_barcodes'), {})

        self.assertFalse(Item.objects.get(pk=self.items[2].pk).barcode)

    def test_selected_ids_and_barcode_range(self):
        self.assertEqual(self.codes(ids=str(self.items[1].pk)), ['XIU900000002'])
        self.assertEqual(self.codes(**{'from': 'xiu900000002', 'to': 'XIU900000002'}),
                         ['XIU900000002'])

    def test_typed_numbers_report_what_was_not_found(self):
        typed = f'{self.items[0].inventory_number}, xiu900000002\nYOQ-1'

        response = self.client.get(self.url, {'numbers': typed})

        self.assertEqual(response.context['count'], 2)
        self.assertEqual(response.context['missing'], ['YOQ-1'])

    def test_withdrawn_copy_is_left_out_unless_named(self):
        Item.objects.filter(pk=self.items[0].pk).update(status=Item.Status.WITHDRAWN)

        self.assertEqual(self.codes(book=self.book.pk), ['XIU900000002'])
        self.assertEqual(self.codes(ids=str(self.items[0].pk)), ['XIU900000001'])

    def test_unprintable_code_is_listed_instead_of_failing(self):
        Item.objects.filter(pk=self.items[0].pk).update(barcode='КОД-1')

        response = self.client.get(self.url, {'book': self.book.pk})

        self.assertEqual(response.context['unprintable'], ['КОД-1'])
        self.assertEqual(response.context['count'], 1)

    def test_printed_code_is_found_by_the_desk(self):
        code = self.codes(ids=str(self.items[0].pk))[0]

        self.assertEqual(exact_items(code), [self.items[0]])

    def test_entry_points(self):
        detail = self.client.get(reverse('panel:book_detail', args=[self.book.pk]))
        self.assertContains(detail, f'{self.url}?book={self.book.pk}')
        item = self.client.get(reverse('panel:item_detail', args=[self.items[0].pk]))
        self.assertContains(item, f'{self.url}?ids={self.items[0].pk}')
        self.book.title = "Algo & ritm"
        self.book.save()
        listing = self.client.get(reverse('panel:items'), {'q': 'Algo & ritm'})
        self.assertContains(listing, f'{self.url}?q=Algo+%26+ritm')
        self.assertContains(self.client.get(reverse('panel:labels')), 'name="numbers"')


class MemberCardTests(TestCase):
    def setUp(self):
        self.client.force_login(make_librarian())
        self.patrons = []
        for number, (name, group) in enumerate((('Aliyev', 'IQ-1'), ('Karimova', 'IQ-2'))):
            user = User.objects.create(username=f'card{number}', first_name='Ism',
                                       second_name=name, user_type='STUDENT')
            user.student_profile.group = group
            user.student_profile.save()
            self.patrons.append(get_or_create_patron(user))
        self.url = reverse('panel:labels_cards')

    def cards(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return [entry['patron'] for sheet in response.context['sheets']
                for entry in sheet if entry]

    def test_nothing_without_a_condition(self):
        self.assertEqual(self.cards(), [])

    def test_group_selection(self):
        response = self.client.get(self.url, {'group': 'iq-1'})

        self.assertContains(response, self.patrons[0].card_number)
        self.assertNotContains(response, self.patrons[1].card_number)
        self.assertContains(response, 'IQ-1')

    def test_closed_member_is_skipped_unless_chosen(self):
        Patron.objects.filter(pk=self.patrons[0].pk).update(status=Patron.Status.CLOSED)

        self.assertEqual(self.cards(category='TALABA'), [self.patrons[1]])
        self.assertEqual(self.cards(ids=str(self.patrons[0].pk)), [self.patrons[0]])

    def test_printed_card_number_is_found_by_the_desk(self):
        card = self.cards(ids=str(self.patrons[1].pk))[0]

        self.assertEqual(exact_patrons(card.card_number), [self.patrons[1]])

    def test_entry_points(self):
        detail = self.client.get(reverse('panel:member_detail', args=[self.patrons[0].pk]))
        self.assertContains(detail, f'{self.url}?ids={self.patrons[0].pk}')
        listing = self.client.get(reverse('panel:members'), {'q': 'Aliyev'})
        self.assertContains(listing, f'{self.url}?q=Aliyev')


class LabelPermissionTests(TestCase):
    def login_with(self, preset):
        user = make_employee()
        role = Role.objects.get(name=preset)
        user.employe_profile.roles.add(role)
        user.employe_profile.current_role = role
        user.employe_profile.save()
        self.client.force_login(user)

    def status(self, name):
        return self.client.get(reverse(f'panel:{name}')).status_code

    def test_cataloguer_prints_labels_but_not_cards(self):
        self.login_with("Kataloglovchi")

        self.assertEqual((self.status('labels'), self.status('labels_copies'),
                          self.status('labels_cards')), (200, 200, 403))
        self.assertNotContains(self.client.get(reverse('panel:labels')), 'A\'zo kartalari')

    def test_loan_desk_prints_cards_but_not_labels(self):
        self.login_with("Abonement xodimi")

        self.assertEqual((self.status('labels'), self.status('labels_copies'),
                          self.status('labels_cards')), (200, 403, 200))
        self.assertEqual(self.client.post(reverse('panel:labels_barcodes')).status_code, 403)
