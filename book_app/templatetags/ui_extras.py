"""
Interfeys yordamchilari (faqat ko'rinish bilan bog'liq).

    {% load ui_extras %}
    <span class="cover tone-{{ book|cover_tone }}">…
    {% include "ui/_icon.html" with name=genre.name|genre_icon %}
    {{ user|initials }}
"""
from django import template

from ..translit import fold

register = template.Library()

COVER_TONES = 8

#: Katalog nomidagi so'z boshlanishi -> ikonka. Tartib muhim: aniqrog'i oldin.
#: Kalitlar `fold()`dan o'tgan ko'rinishda solishtiriladi.
GENRE_ICONS = (
    (('dastur', 'informat', 'kompyuter', 'axborot', 'texnolog', 'программ', 'it '), 'code'),
    (('matemat', 'algebra', 'geometr', 'statist'), 'calculator'),
    (('fizik', 'astronom'), 'atom'),
    (('kimyo', 'biolog'), 'flask'),
    (('tibbiy', 'salomat', 'sport', 'jismoniy'), 'heart-pulse'),
    (('iqtisod', 'moliya', 'bank', 'soliq', 'buxgalter', 'marketing'), 'trending'),
    (('menejment', 'boshqaruv', 'biznes', 'turizm'), 'briefcase'),
    (('huquq', 'yurid', 'qonun'), 'scale'),
    (('tarix', 'arxeolog', 'siyosat', 'politolog'), 'landmark'),
    (('adabiyot', 'badiiy', 'sheriyat', 'roman', 'qissa'), 'feather'),
    (('pedagog', 'talim', 'maktab', 'metodik', 'darslik'), 'graduation'),
    (('til', 'lingvist', 'filolog', 'ingliz', 'rus ', 'tarjima'), 'globe'),
    (('psixolog', 'falsafa', 'sotsiolog', 'ijtimoiy'), 'lightbulb'),
    (('sanat', 'musiqa', 'dizayn', 'madaniyat'), 'palette'),
    (('qishloq', 'agro', 'ekolog', 'geograf'), 'sprout'),
    (('muhandis', 'qurilish', 'arxitektur', 'energet'), 'building'),
)


@register.filter
def cover_tone(book) -> int:
    """Muqova rangi: bir katalogdagi kitoblar ham turlicha, lekin har doim bir xil."""
    pk = getattr(book, 'pk', None) or 0
    category = getattr(book, 'category_id', None) or 0
    return (pk * 3 + category) % COVER_TONES


@register.filter
def tone_of(number) -> int:
    """Tartib raqamidan rang (kataloglar to'ri uchun)."""
    try:
        return int(number) % COVER_TONES
    except (TypeError, ValueError):
        return 0


@register.filter
def genre_icon(name) -> str:
    text = f"{fold(str(name or ''))} "
    for stems, icon in GENRE_ICONS:
        for stem in stems:
            key = fold(stem) + (' ' if stem.endswith(' ') else '')
            if text.startswith(key) or f' {key}' in text:
                return icon
    return 'book-open'


@register.filter
def initials(user) -> str:
    """«Karimov Anvar» -> «KA»."""
    parts = [getattr(user, 'second_name', ''), getattr(user, 'first_name', '')]
    letters = ''.join(p.strip()[0] for p in parts if p and p.strip())
    if not letters:
        letters = (getattr(user, 'username', '') or '?')[:2]
    return letters.upper()


@register.filter
def spaced(number) -> str:
    """2392 -> «2 392» (uzilmas bo'shliq bilan)."""
    try:
        return f"{int(number):,}".replace(',', ' ')
    except (TypeError, ValueError):
        return str(number)
