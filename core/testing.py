"""
Testlar uchun yengil fabrikalar (factory).

Maqsad: har test faylida bir xil `setUp` kodini qayta yozmaslik. Tashqi kutubxona
(factory_boy) ataylab ishlatilmaydi — bu yerdagi funksiyalar loyihaning o'z
signallari va standartlarini hisobga oladi va qo'shimcha bog'liqlik keltirmaydi.

Foydalanish:
    from core.testing import make_book, make_student

    class MyTests(TestCase):
        def setUp(self):
            self.book = make_book("Algoritmlar", copies=3)
            self.student = make_student()
"""
from datetime import timedelta

from django.utils.timezone import now

_counter = {'n': 0}


def _uniq(prefix=''):
    _counter['n'] += 1
    return f"{prefix}{_counter['n']}"


# --- Katalog ---

def make_genre(name=None, **kwargs):
    from book_app.models import Genre
    return Genre.objects.create(name=name or f"Katalog-{_uniq()}", **kwargs)


def make_author(full_name=None, **kwargs):
    from book_app.models import Author
    return Author.objects.create(full_name=full_name or f"Muallif {_uniq()}", **kwargs)


def make_book(title=None, *, genre=None, authors=(), copies=0, **kwargs):
    """Kitob yaratadi; `copies` berilsa shuncha mavjud nusxa ham qo'shadi."""
    from book_app.models import Book
    book = Book.objects.create(
        title=title or f"Kitob {_uniq()}",
        category=genre or make_genre(),
        **kwargs,
    )
    if authors:
        book.authors.set(authors)
    if copies:
        make_copies(book, copies)
    return book


def make_copies(book, count=1, available=True):
    from book_app.models import Copy
    return [
        Copy.objects.create(book=book, inventory_number=f"INV-{_uniq()}", is_available=available)
        for _ in range(count)
    ]


# --- Foydalanuvchilar ---

def make_student(username=None, **kwargs):
    """Talaba foydalanuvchi (signal `student_profile`ni o'zi yaratadi)."""
    from user_app.models import User
    user = User.objects.create_user(
        username=username or f"talaba{_uniq()}",
        password=kwargs.pop('password', 'test12345'),
        user_type=User.UserType.STUDENT,
        **kwargs,
    )
    return user


def make_employee(username=None, role=None, **kwargs):
    """Xodim foydalanuvchi; `role` berilsa `current_role` o'rnatiladi."""
    from user_app.models import Role, User
    user = User.objects.create_user(
        username=username or f"xodim{_uniq()}",
        password=kwargs.pop('password', 'test12345'),
        user_type=User.UserType.EMPLOYE,
        **kwargs,
    )
    if role:
        profile = user.employe_profile
        role_obj, _ = Role.objects.get_or_create(name=role)
        profile.current_role = role_obj
        profile.roles.add(role_obj)
        profile.save(update_fields=['current_role'])
    return user


def make_librarian(username=None, **kwargs):
    from user_app.roles import Roles
    return make_employee(username, role=Roles.LIBRARIAN, **kwargs)


# --- Ijara ---

def make_rental(student, copy, *, days=14, borrowed_days_ago=0):
    """Faol ijara yaratadi (`student` — StudentProfile)."""
    from book_app.models import Rental
    borrowed = now().date() - timedelta(days=borrowed_days_ago)
    copy.is_available = False
    copy.save(update_fields=['is_available'])
    return Rental.objects.create(
        copy=copy,
        student=student,
        library_admin_checked=True,
        borrowed_date=borrowed,
        due_date=borrowed + timedelta(days=days),
    )
