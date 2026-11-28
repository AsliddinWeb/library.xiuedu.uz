"""
Rollar va hisob turlari — kim kimligini aniqlaydigan yagona joy.

Tizimda 4 xil kirish huquqi bor (`AccountKind`):

    GUEST      — kirmagan.
    READER     — o'quvchi: talaba (student.xiuedu.uz) YOKI o'qituvchi/xodim
                 (hemis.xiuedu.uz). Kitob oladi, o'qiydi.
    LIBRARIAN  — kutubxona xodimi. O'z paneli (`/panel/`) bor, kitob OLMAYDI.
    ADMIN      — tizim administratori (`/admin/`), kitob OLMAYDI.

HEMIS orqali kirgan xodim avtomatik O'QUVCHI bo'ladi. Kutubxona xodimiga
aylantirish uchun admin unga rol biriktiradi (LibraryAdmin yoki boshqa xodim roli).

To'liq sahifa matritsasi: `claude-files/11-ROLES.md`, testi: `core/test_access.py`.

`Role.name` qiymatlari bazadagi yozuvlar bilan mos kelishi shart.
"""
from django.db.models import Q


class Roles:
    STUDENT = 'Student'
    EMPLOYEE = 'Employee'
    LIBRARIAN = 'LibraryAdmin'
    ADMIN = 'Admin'

    CHOICES = (STUDENT, EMPLOYEE, LIBRARIAN, ADMIN)

    #: O'quvchi rollari — hech qanday xodim huquqi bermaydi
    READER = (STUDENT, EMPLOYEE)

    #: Admin panelida ko'rinadigan nomlar
    LABELS = {
        STUDENT: "Talaba (o'quvchi)",
        EMPLOYEE: "O'qituvchi / xodim (o'quvchi)",
        LIBRARIAN: "Kutubxona xodimi",
        ADMIN: "Administrator",
    }


class AccountKind:
    GUEST = 'guest'
    READER = 'reader'
    LIBRARIAN = 'librarian'
    ADMIN = 'admin'


def staff_roles(user) -> list:
    """Foydalanuvchining xodim huquqini beradigan rollari.

    `Student`/`Employee` hisobga olinmaydi (ularga bazada ruxsat yozilgan bo'lsa
    ham). Maxsus rol ("Zal xodimi" kabi) kamida bitta ruxsatga ega bo'lsa —
    xodim roli.
    """
    if user is None or not user.is_authenticated:
        return []
    profile = getattr(user, 'employe_profile', None)
    if profile is None:
        return []
    roles = list(profile.roles.all())
    if profile.current_role_id and profile.current_role not in roles:
        roles.append(profile.current_role)
    return [
        role for role in roles
        if role.name not in Roles.READER
        and (role.name in (Roles.LIBRARIAN, Roles.ADMIN) or role.permissions)
    ]


def account_kind(user) -> str:
    if user is None or not user.is_authenticated:
        return AccountKind.GUEST
    if user.is_superuser:
        return AccountKind.ADMIN
    roles = staff_roles(user)
    if any(role.name == Roles.ADMIN for role in roles):
        return AccountKind.ADMIN
    return AccountKind.LIBRARIAN if roles else AccountKind.READER


def is_library_staff(user) -> bool:
    """Kutubxona xodimi yoki administrator (ikkalasi ham kitob olmaydi)."""
    return account_kind(user) in (AccountKind.LIBRARIAN, AccountKind.ADMIN)


def home_url(user) -> str:
    """Har hisob turining bosh ish sahifasi."""
    kind = account_kind(user)
    if kind == AccountKind.ADMIN:
        # `/admin/` faqat `is_staff` hisobni qabul qiladi; aks holda kutubxona paneli
        return '/admin/' if user.is_staff else '/panel/'
    if kind == AccountKind.LIBRARIAN:
        return '/panel/'
    if kind == AccountKind.READER:
        return '/dashboard/'
    return '/'


def staff_user_q(admins=False) -> Q:
    """`User` so'rovi uchun filtr: xodim rollari bor hisoblar.

    `admins=True` — faqat administratorlar, aks holda barcha xodim rollari.
    """
    from .models import EmployeProfile, Role

    if admins:
        roles = Role.objects.filter(name=Roles.ADMIN)
    else:
        roles = (Role.objects.exclude(name__in=Roles.READER)
                 .filter(Q(name__in=(Roles.LIBRARIAN, Roles.ADMIN)) | ~Q(permissions=[])))
    profiles = EmployeProfile.objects.filter(Q(roles__in=roles) | Q(current_role__in=roles))
    return Q(pk__in=profiles.values('user_id'))


def effective_role(user):
    """Foydalanuvchining amaldagi rol nomi (eski chaqiruvlar uchun).

    - autentifikatsiyadan o'tmagan   -> None
    - administrator                  -> ADMIN
    - istalgan xodim roli            -> LIBRARIAN
    - talaba                         -> STUDENT
    - qolgan hamma (HEMIS xodimi)    -> EMPLOYEE
    """
    kind = account_kind(user)
    if kind == AccountKind.GUEST:
        return None
    if kind == AccountKind.ADMIN:
        return Roles.ADMIN
    if kind == AccountKind.LIBRARIAN:
        return Roles.LIBRARIAN
    return Roles.STUDENT if user.user_type == 'STUDENT' else Roles.EMPLOYEE
