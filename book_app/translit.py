"""
O'zbekcha kirill ↔ lotin transliteratsiya.

Nega kerak: XIU fondida bir muallif uch xil yozilgan bo'lishi mumkin —
"Qodiriy", "Кодирий", "Kodiriy". Transliteratsiyasiz qidiruvning yarmi
ishlamaydi: talaba kirillda yozsa, lotincha yozuvni topa olmaydi.

Yondashuv: qidiruv indeksi (`Book.search_text`) HAM, foydalanuvchi so'rovi HAM
bitta ko'rinishga — **normallashgan lotin**ga keltiriladi. Shunda yozuv qaysi
alifboda kiritilganidan qat'i nazar topiladi.

    >>> normalize("Ўткан кунлар")
    "o'tkan kunlar"
    >>> normalize("O'tkan kunlar")
    "o'tkan kunlar"

Eslatma: bu "rasmiy" standart emas, balki QIDIRUV uchun mo'ljallangan
soddalashtirilgan sxema — maqsad ikki yozuvni bir xil satrga keltirish.
"""
import re

# --- Apostrof variantlari (oʻ, o', o`, o‘ ...) bitta belgiga keltiriladi ---
APOSTROPHES = "‘’ʻʼ´`′"
APOSTROPHE = "'"

#: Kirill -> lotin. Ko'p belgili birikmalar OLDIN turishi shart.
CYRILLIC_TO_LATIN = [
    ("ё", "yo"), ("ж", "j"), ("ц", "ts"), ("ч", "ch"), ("ш", "sh"),
    ("щ", "sh"), ("ю", "yu"), ("я", "ya"),
    ("ғ", "g'"), ("ў", "o'"), ("қ", "q"), ("ҳ", "h"), ("ъ", "'"), ("ь", ""),
    ("а", "a"), ("б", "b"), ("в", "v"), ("г", "g"), ("д", "d"), ("е", "e"),
    ("з", "z"), ("и", "i"), ("й", "y"), ("к", "k"), ("л", "l"), ("м", "m"),
    ("н", "n"), ("о", "o"), ("п", "p"), ("р", "r"), ("с", "s"), ("т", "t"),
    ("у", "u"), ("ф", "f"), ("х", "x"), ("ы", "i"), ("э", "e"),
]

#: Lotin -> kirill (teskari yo'nalish: ma'lumotnoma va eksport uchun).
LATIN_TO_CYRILLIC = [
    ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ch", "ч"), ("sh", "ш"),
    ("ts", "ц"), ("g'", "ғ"), ("o'", "ў"), ("ng", "нг"),
    ("a", "а"), ("b", "б"), ("v", "в"), ("g", "г"), ("d", "д"), ("e", "е"),
    ("j", "ж"), ("z", "з"), ("i", "и"), ("y", "й"), ("k", "к"), ("l", "л"),
    ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("q", "қ"), ("r", "р"),
    ("s", "с"), ("t", "т"), ("u", "у"), ("f", "ф"), ("x", "х"), ("h", "ҳ"),
    ("c", "к"), ("w", "в"),
]

_SPACES = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w'\s]", re.UNICODE)


def unify_apostrophes(text: str) -> str:
    """Barcha apostrof variantlarini bitta belgiga keltiradi."""
    for char in APOSTROPHES:
        text = text.replace(char, APOSTROPHE)
    return text


def to_latin(text: str) -> str:
    """Kirill matnni lotinga o'giradi. Lotin matn o'zgarishsiz qaytadi."""
    if not text:
        return ""
    result = unify_apostrophes(text).lower()
    for cyrillic, latin in CYRILLIC_TO_LATIN:
        result = result.replace(cyrillic, latin)
    return result


def to_cyrillic(text: str) -> str:
    """Lotin matnni kirillga o'giradi (taxminiy — qidiruv uchun yetarli)."""
    if not text:
        return ""
    result = unify_apostrophes(text).lower()
    for latin, cyrillic in LATIN_TO_CYRILLIC:
        result = result.replace(latin, cyrillic)
    return result


def normalize(text: str) -> str:
    """Qidiruv uchun yagona ko'rinish: lotin, kichik harf, tinish belgisiz.

    Ikkala alifbodagi matn ham bir xil natija beradi — qidiruv indeksi va
    foydalanuvchi so'rovi aynan shu funksiyadan o'tkaziladi.
    """
    if not text:
        return ""
    result = to_latin(text)
    result = _PUNCT.sub(" ", result)
    result = _SPACES.sub(" ", result)
    return result.strip()


#: Qidiruvda chalkashadigan harflar — bitta ko'rinishga keltiriladi.
#  Sabab: eski kirill yozuvlarda "к" ham k, ham q o'rnida ishlatilgan
#  ("Кодирий" = "Qodiriy"), "х"/"ҳ" ham tez-tez almashtiriladi.
FOLD_MAP = str.maketrans({
    "q": "k", "x": "h", "w": "v", "c": "k", "'": "", "`": "",
})


def fold(text: str) -> str:
    """Qidiruv uchun eng "kechirimli" ko'rinish.

    `normalize()` dan farqi: apostroflar olib tashlanadi va chalkashadigan
    harflar birlashtiriladi. Indeks ham, so'rov ham shu funksiyadan o'tadi:

        >>> fold("Кодирий") == fold("Qodiriy")
        True
        >>> fold("O'tkan kunlar") == fold("Ўткан кунлар")
        True
    """
    return normalize(text).translate(FOLD_MAP)


def variants(text: str) -> list:
    """Matnning qidiruvda ishlatiladigan ko'rinishlari (dublikatsiz)."""
    seen, result = set(), []
    for value in (normalize(text), to_cyrillic(normalize(text))):
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
