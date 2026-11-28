"""
Loyiha darajasidagi yordamchi sahifalar.

Hozircha bitta: dizayn tizimi (style-guide) — /_design/
"""
from django.http import Http404
from django.shortcuts import render

from user_app.roles import is_library_staff

from .flags import flag_enabled

PALETTE = [
    {'name': "Pine 700 — brend", 'token': '--color-pine-700', 'value': '#0e675b'},
    {'name': "Clay 500 — aksent", 'token': '--color-clay-500', 'value': '#ec5b30'},
    {'name': "Sun 400 — urg'u", 'token': '--color-sun-400', 'value': '#fdb924'},
    {'name': "Ink 900 — matn", 'token': '--color-ink-900', 'value': '#101a18'},
    {'name': "Paper — OPAC foni", 'token': '--color-paper', 'value': '#fbf9f5'},
    {'name': "Slate — Staff foni", 'token': '--color-slate-bg', 'value': '#f2f5f4'},
    {'name': "Success", 'token': '--color-success-700', 'value': '#067647'},
    {'name': "Warning", 'token': '--color-warning-700', 'value': '#b54708'},
    {'name': "Danger", 'token': '--color-danger-700', 'value': '#b42318'},
]

SHELLS = [
    {'code': 'opac', 'label': 'OPAC — bo\'sh (comfortable)', 'badge': 'badge-brand'},
    {'code': 'staff', 'label': 'STAFF — kompakt (compact)', 'badge': 'badge-neutral'},
]

TABLE_ROWS = [
    {'title': "Algoritmlar va ma'lumotlar tuzilmasi", 'author': "T. Cormen",
     'barcode': 'XIU000001248', 'status': 'success', 'status_label': 'Mavjud', 'copies': 5},
    {'title': "O'tkan kunlar", 'author': "A. Qodiriy",
     'barcode': 'XIU000000317', 'status': 'info', 'status_label': 'Ijarada', 'copies': 12},
    {'title': "Iqtisodiyot nazariyasi", 'author': "N. Mankiw",
     'barcode': 'XIU000002904', 'status': 'warning', 'status_label': 'Navbatda', 'copies': 3},
    {'title': "Clean Architecture", 'author': "R. Martin",
     'barcode': 'XIU000004471', 'status': 'danger', 'status_label': "Muddat o'tgan", 'copies': 1},
]

ICONS = [
    'search', 'bell', 'user', 'users', 'menu', 'close', 'check', 'plus',
    'minus', 'pencil', 'trash', 'book', 'library', 'barcode', 'cash', 'chart',
    'clock', 'alert', 'inbox', 'cog', 'chevron-down', 'chevron-left',
    'chevron-right', 'external', 'printer', 'logout', 'login', 'home', 'grid', 'rows',
    'list', 'filter', 'sliders', 'book-open', 'headphones', 'heart', 'bookmark',
    'graduation', 'star', 'sparkles', 'flame', 'history', 'calendar', 'download',
    'upload', 'copy', 'quote', 'eye', 'play', 'pause', 'rewind', 'forward', 'maximize',
    'zoom-in', 'zoom-out', 'arrow-left', 'arrow-right', 'arrow-up', 'arrow-up-right',
    'check-circle', 'info', 'sun', 'moon', 'monitor', 'map-pin', 'globe', 'send', 'mail',
    'shield', 'id-card', 'code', 'calculator', 'scale', 'atom', 'flask', 'heart-pulse',
    'briefcase', 'trending', 'landmark', 'feather', 'palette', 'sprout', 'lightbulb',
    'layers', 'folder', 'building', 'wallet',
]



def design_system(request):
    """Dizayn tizimi sahifasi — komponentlar ikki qiyofada.

    Ochiq: dev muhitda hammaga, production'da faqat xodimga.
    `design_styleguide` flagi o'chiq bo'lsa — 404.
    """
    if not flag_enabled('design_styleguide'):
        raise Http404("Dizayn tizimi sahifasi o'chirilgan.")

    if not is_library_staff(request.user):
        return render(request, '403.html', status=403)

    return render(request, '_design/index.html', {
        'palette': PALETTE,
        'shells': SHELLS,
        'table_rows': TABLE_ROWS,
        'icons': ICONS,
    })
