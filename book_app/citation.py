"""
Bibliografik tavsif (GOST 7.1 uslubida).

Nega kerak: talaba referat yoki dissertatsiyada adabiyotlar ro'yxatini
rasmiylashtiradi. Buni qo'lda yozish o'rniga kitob sahifasidan bir bosishda
ko'chirib oladi.

Namuna:
    Qodiriy A. O'tkan kunlar : roman / A. Qodiriy. — Toshkent : Yangi asr
    avlodi, 2019. — 384 b. — ISBN 9789943010101.
"""


def _initials(full_name: str) -> str:
    """«Abdulla Qodiriy» -> «Qodiriy A.» (GOST'dagi sarlavha oldi yozuvi)."""
    parts = [p for p in (full_name or "").split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    surname = parts[-1]
    initials = " ".join(f"{p[0].upper()}." for p in parts[:-1])
    return f"{surname} {initials}"


def _author_list(book, limit=3):
    authors = list(book.authors.all()[:limit + 1])
    names = [a.full_name for a in authors[:limit]]
    if len(authors) > limit:
        names.append("[va boshq.]")
    return names


def gost(book) -> str:
    """Kitobning GOST uslubidagi bibliografik tavsifi (bitta satr)."""
    authors = _author_list(book)
    head = f"{_initials(authors[0])} " if authors else ""

    title = book.title.strip()
    if book.subtitle:
        title += f" : {book.subtitle.strip()}"

    # Qiya chiziqdan keyin — mualliflik ma'lumoti
    responsibility = ", ".join(authors)

    parts = [f"{head}{title}"]
    if responsibility:
        parts[0] += f" / {responsibility}"

    if book.edition_statement:
        parts.append(book.edition_statement)

    imprint = []
    if book.place_of_publication:
        imprint.append(book.place_of_publication)
    if book.publisher_id:
        imprint.append(book.publisher.name)
    imprint_text = " : ".join(imprint)
    if book.published_year:
        imprint_text = f"{imprint_text}, {book.published_year}" if imprint_text \
            else str(book.published_year)
    if imprint_text:
        parts.append(imprint_text)

    if book.page_count:
        parts.append(f"{book.page_count} b.")
    if book.series_id:
        series = book.series.name
        if book.series_number:
            series += f" ; {book.series_number}"
        parts.append(f"({series})")
    if book.isbn:
        parts.append(f"ISBN {book.isbn}")

    # "384 b." yoki "G. V." kabi nuqta bilan tugagan qism ".." bo'lib qolmasin
    return ". — ".join(part.rstrip(".") for part in parts) + "."
