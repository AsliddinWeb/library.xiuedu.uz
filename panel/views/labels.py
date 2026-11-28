"""
Xodim paneli — kitob yorlig'i va a'zo kartasini chop etish.

Chop etish sahifasi faqat o'qiydi. Shtrix-kodi yo'q nusxaga raqam berish
alohida POST amali: «chop etish»ni ochishning o'zi bazani o'zgartirmaydi.
"""
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from book_app.models import Item
from book_app.services import assign_barcodes
from user_app.models import Patron, PatronCategory, StudentProfile
from user_app.permissions import Perms, require_perm

from ..printing import CARD_PAPERS, COPY_PAPERS, barcode_svg, pick_paper, printable, sheets
from .items import filter_items
from .members import filter_members

__all__ = ['labels', 'labels_copies', 'labels_barcodes', 'labels_cards']

#: Bir martada chiqariladigan eng ko'p yorliq va karta (brauzer ko'tarsin)
COPY_LIMIT = 480
CARD_LIMIT = 200
LIST_LIMIT = 500

COPY_CRITERIA = ('ids', 'book', 'q', 'status', 'library', 'type', 'from', 'to', 'since', 'numbers')
CARD_CRITERIA = ('ids', 'q', 'category', 'status', 'group')
#: Chop sahifasining o'z sozlamalari — tanlov shartiga kirmaydi
LAYOUT_PARAMS = ('paper', 'skip')


def _values(params, names):
    return {name: params.get(name, '').strip() for name in names
            if params.get(name, '').strip()}


def _ids(value):
    return [int(part) for part in value.split(',') if part.strip().isdigit()][:LIST_LIMIT]


def _tokens(value):
    """Qo'lda yozilgan ro'yxat: qator, vergul yoki bo'sh joy bilan ajratilgan."""
    return [part for part in re.split(r'[\s,;]+', value) if part][:LIST_LIMIT]


def _select_copies(criteria):
    """(queryset, topilmagan raqamlar). Shartsiz butun fond chiqarilmaydi."""
    items = (Item.objects.select_related('book', 'shelf_location', 'library')
             .order_by('barcode', 'pk'))
    missing = []
    picked = False

    if 'ids' in criteria:
        items, picked = items.filter(pk__in=_ids(criteria['ids'])), True
    if 'numbers' in criteria:
        tokens = _tokens(criteria['numbers'])
        match = Q(pk__in=[])
        for token in tokens:
            match |= Q(barcode__iexact=token) | Q(inventory_number__iexact=token)
        items, picked = items.filter(match), True
        found = {value.lower() for pair in items.values_list('barcode', 'inventory_number')
                 for value in pair if value}
        missing = [token for token in tokens if token.lower() not in found]
    if criteria.get('book', '').isdigit():
        items = items.filter(book_id=criteria['book'])
    if 'from' in criteria:
        items = items.filter(barcode__gte=criteria['from'].upper())
    if 'to' in criteria:
        items = items.filter(barcode__lte=criteria['to'].upper())
    since = _date(criteria.get('since'))
    if since:
        items = items.filter(acquired_on__gte=since)
    items = filter_items(items, criteria)

    # Aniq sanab ko'rsatilmagan bo'lsa, hisobdan chiqarilganlar kerak emas
    if not picked and criteria.get('status') != Item.Status.WITHDRAWN:
        items = items.exclude(status=Item.Status.WITHDRAWN)
    return items, missing


def _date(value):
    try:
        return parse_date(value or '')
    except ValueError:
        return None


def _usable(criteria, names):
    """Kamida bitta haqiqiy tanlov sharti bormi."""
    checks = {'ids': _ids, 'numbers': _tokens, 'since': _date,
              'book': str.isdigit, 'library': str.isdigit, 'type': str.isdigit}
    return any(checks.get(name, bool)(criteria[name]) for name in names if name in criteria)


def _print_context(request, criteria, papers, entries):
    paper = pick_paper(papers, request.GET.get('paper'))
    skip = request.GET.get('skip', '')
    skip = int(skip) if skip.isdigit() else 0
    skip = min(skip, paper.per_page - 1)
    return {
        'papers': papers, 'paper': paper, 'skip': skip,
        'sheets': sheets(entries, paper, skip), 'count': len(entries),
        'criteria': criteria,
    }


@require_perm(Perms.ITEMS_MANAGE, Perms.PATRONS_EDIT)
def labels(request):
    """Nima chop etilishini tanlash sahifasi."""
    from holdings.models import Library

    return render(request, 'panel/labels.html', {
        'page_title': "Yorliq va kartalar",
        'libraries': Library.objects.filter(is_active=True),
        'categories': PatronCategory.objects.filter(is_active=True),
        'groups': (StudentProfile.objects.exclude(Q(group__isnull=True) | Q(group=''))
                   .values_list('group', flat=True).distinct().order_by('group')),
        'copy_papers': COPY_PAPERS, 'card_papers': CARD_PAPERS,
        'without_barcode': Item.objects.filter(Q(barcode__isnull=True) | Q(barcode=''))
                                       .exclude(status=Item.Status.WITHDRAWN).count(),
    })


@require_perm(Perms.ITEMS_MANAGE)
def labels_copies(request):
    criteria = _values(request.GET, COPY_CRITERIA)
    entries, unprintable, without, missing, truncated = [], [], 0, [], False

    if _usable(criteria, COPY_CRITERIA):
        items, missing = _select_copies(criteria)
        rows = list(items[:COPY_LIMIT + 1])
        truncated = len(rows) > COPY_LIMIT
        for item in rows[:COPY_LIMIT]:
            if not item.barcode:
                without += 1
            elif not printable(item.barcode):
                unprintable.append(item.barcode)
            else:
                entries.append({
                    'item': item,
                    'svg': barcode_svg(item.barcode),
                    'shelf': item.call_number
                    or (item.shelf_location.code if item.shelf_location_id else ''),
                })

    return render(request, 'panel/print/copies.html', {
        **_print_context(request, criteria, COPY_PAPERS, entries),
        'chosen': _usable(criteria, COPY_CRITERIA),
        'without_barcode': without, 'unprintable': unprintable,
        'missing': missing, 'truncated': truncated, 'limit': COPY_LIMIT,
    })


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def labels_barcodes(request):
    """Tanlovdagi shtrix-kodsiz nusxalarga raqam beradi va sahifaga qaytaradi."""
    criteria = _values(request.POST, COPY_CRITERIA)
    if _usable(criteria, COPY_CRITERIA):
        items, _ = _select_copies(criteria)
        # Diapazon shtrix-kod bo'yicha bo'lsa, kodsizlar unga tushmaydi — tabiiy hol
        assigned = assign_barcodes(list(items.filter(Q(barcode__isnull=True) | Q(barcode=''))
                                        [:COPY_LIMIT]), by=request.user)
        messages.success(request, f"{len(assigned)} ta nusxaga shtrix-kod berildi.")
    layout = _values(request.POST, LAYOUT_PARAMS)
    return redirect(f"{reverse('panel:labels_copies')}?{urlencode({**criteria, **layout})}")


def _member_details(patron):
    """Karta ostidagi qator: talabada fakultet va guruh, xodimda lavozim."""
    user = patron.user
    if user is None:
        return ''
    if user.user_type == 'STUDENT':
        profile = getattr(user, 'student_profile', None)
        parts = (getattr(profile, 'group', ''), getattr(profile, 'faculty', ''))
    else:
        profile = getattr(user, 'employe_profile', None)
        parts = (getattr(profile, 'position', ''), getattr(profile, 'department', ''))
    return ' · '.join(part for part in parts if part)


def _photo_url(patron):
    image = patron.photo or (patron.user.image if patron.user else None)
    return image.url if image else ''


@require_perm(Perms.PATRONS_EDIT)
def labels_cards(request):
    criteria = _values(request.GET, CARD_CRITERIA)
    entries, unprintable, truncated = [], [], False
    chosen = _usable(criteria, CARD_CRITERIA)

    if chosen:
        patrons = (Patron.objects
                   .select_related('user', 'category', 'user__student_profile',
                                   'user__employe_profile')
                   .order_by('user__second_name', 'user__first_name', 'full_name', 'pk'))
        if 'ids' in criteria:
            patrons = patrons.filter(pk__in=_ids(criteria['ids']))
        else:
            patrons = patrons.exclude(status=Patron.Status.CLOSED)
        if 'group' in criteria:
            patrons = patrons.filter(user__student_profile__group__iexact=criteria['group'])
        patrons = filter_members(patrons, criteria)
        rows = list(patrons[:CARD_LIMIT + 1])
        truncated = len(rows) > CARD_LIMIT
        for patron in rows[:CARD_LIMIT]:
            if not printable(patron.card_number):
                unprintable.append(patron.card_number)
                continue
            entries.append({
                'patron': patron,
                'svg': barcode_svg(patron.card_number),
                'details': _member_details(patron),
                'photo': _photo_url(patron),
            })

    return render(request, 'panel/print/cards.html', {
        **_print_context(request, criteria, CARD_PAPERS, entries),
        'chosen': chosen, 'unprintable': unprintable,
        'truncated': truncated, 'limit': CARD_LIMIT,
    })
