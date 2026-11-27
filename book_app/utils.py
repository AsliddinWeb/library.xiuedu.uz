"""Kitob yordamchilari (eski API — yangi kod `book_app.services` ni ishlatadi)."""
from .models import Rental


def add_copies(book, quantity, **kwargs):
    """Kitobga N ta nusxa qo'shadi.

    Mantiq `book_app.services.create_items` ichida: shtrix-kod, inventar raqami,
    filial, nusxa turi va jurnal — hammasi o'sha yerda.
    """
    from .services import create_items
    return create_items(book, quantity, **kwargs)


def is_book_borrowed_by_patron(patron, book):
    """Kitob shu a'zoda ijaradami (qaytarilmaganmi)."""
    return Rental.objects.filter(
        patron=patron,
        copy__book=book,
        return_date__isnull=True
    ).exists()
