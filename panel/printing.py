"""
Chop etish: shtrix-kod rasmi va qog'oz o'lchamlari.

Shtrix-kod serverning o'zida **Code 128** ko'rinishida chiziladi (tashqi xizmat
va CDN yo'q) — oddiy USB skanerlarning hammasi o'qiydi.
"""
from dataclasses import dataclass

from barcode import Code128
from django.utils.html import escape
from django.utils.safestring import mark_safe

#: Chiziqlar atrofidagi bo'sh joy (modul) — skaner kod boshini shundan taniydi
QUIET = 10


def printable(value) -> bool:
    """Code 128 ga yoziladigan matnmi (lotin harf, raqam va oddiy belgilar)."""
    value = str(value or '')
    return bool(value) and value.isascii() and value.isprintable() and value == value.strip()


def barcode_modules(value) -> str:
    """«1» — qora, «0» — oq modullar ketma-ketligi."""
    return Code128(str(value)).build()[0]


def barcode_svg(value) -> str:
    """Cho'ziladigan SVG: o'lchamni qog'oz tomoni (CSS) belgilaydi."""
    modules = barcode_modules(value)
    bars, start = [], None
    for position, module in enumerate(modules + '0'):
        if module == '1' and start is None:
            start = position
        elif module != '1' and start is not None:
            bars.append(f'M{start + QUIET} 0h{position - start}v100h-{position - start}z')
            start = None
    width = len(modules) + 2 * QUIET
    return mark_safe(
        f'<svg class="barcode" viewBox="0 0 {width} 100" preserveAspectRatio="none" '
        f'shape-rendering="crispEdges" role="img" aria-label="{escape(value)}">'
        f'<path fill="#000" d="{"".join(bars)}"/></svg>')


@dataclass(frozen=True)
class Paper:
    code: str
    name: str
    page: tuple       # sahifa eni va bo'yi, mm
    label: tuple      # bitta yorliq eni va bo'yi, mm
    columns: int = 1
    rows: int = 1

    @property
    def per_page(self):
        return self.columns * self.rows


COPY_PAPERS = (
    Paper('a4-24', "A4 varaq — 24 ta (70×37 mm)", (210, 297), (70, 37), 3, 8),
    Paper('t58', "Termo-yorliq 58×40 mm", (58, 40), (58, 40)),
    Paper('t40', "Termo-yorliq 40×30 mm", (40, 30), (40, 30)),
)

CARD_PAPERS = (
    Paper('a4-10', "A4 varaq — 10 ta karta", (210, 297), (85.6, 54), 2, 5),
    Paper('card', "Bitta karta 85,6×54 mm", (85.6, 54), (85.6, 54)),
)


def pick_paper(papers, code) -> Paper:
    return next((paper for paper in papers if paper.code == code), papers[0])


def sheets(entries, paper, skip=0) -> list:
    """Yozuvlarni sahifalarga bo'ladi; `skip` — ishlatib bo'lingan kataklar soni."""
    skip = max(0, min(int(skip), paper.per_page - 1))
    cells = [None] * skip + list(entries)
    if not entries:
        return []
    size = paper.per_page
    return [cells[start:start + size] for start in range(0, len(cells), size)]
