"""
Granular ruxsatlar (Koha uslubidagi flaglar).

Nega kerak: kutubxonada bitta "LibraryAdmin" roli yetarli emas — kataloglovchi,
abonement xodimi, zal xodimi, ta'minotchi va bosh kutubxonachining vakolati
har xil. Rol "nomi" emas, **ruxsat flagi** tekshiriladi.

Ishlatish:

    from user_app.permissions import Perms, has_perm, require_perm

    @require_perm(Perms.CIRC_CHECKOUT)
    def checkout(request): ...

    if has_perm(request.user, Perms.BILLING_WAIVE): ...

Shablonda:
    {% if perms_flags.circ_checkout %}   (context processor orqali)

Ruxsatlar FAQAT xodim rollaridan olinadi: `Student`/`Employee` (o'quvchi) rollari
hech qanday ruxsat bermaydi — o'quvchi xodim sahifalariga kira olmaydi.

Ruxsatlar `Role.permissions` (JSON ro'yxat) ichida saqlanadi; `"*"` — hammasi.
O'quvchiga mo'ljallangan amallar uchun `reader_required` ishlatiladi.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render

from .roles import Roles, home_url, is_library_staff, staff_roles


class Perms:
    # --- Katalog ---
    CATALOG_VIEW = 'catalog.view'
    CATALOG_EDIT = 'catalog.edit'
    CATALOG_DELETE = 'catalog.delete'
    CATALOG_IMPORT = 'catalog.import'

    # --- Fond (nusxalar) ---
    ITEMS_MANAGE = 'items.manage'
    ITEMS_WITHDRAW = 'items.withdraw'
    INVENTORY_MANAGE = 'inventory.manage'

    # --- Sirkulyatsiya ---
    CIRC_CHECKOUT = 'circ.checkout'
    CIRC_CHECKIN = 'circ.checkin'
    CIRC_RENEW = 'circ.renew'
    CIRC_HOLDS = 'circ.holds'
    CIRC_OVERRIDE = 'circ.override'      # qoidani buzib berish

    # --- A'zolar ---
    PATRONS_VIEW = 'patrons.view'
    PATRONS_EDIT = 'patrons.edit'
    PATRONS_BLOCK = 'patrons.block'

    # --- Pul ---
    BILLING_CHARGE = 'billing.charge'
    BILLING_COLLECT = 'billing.collect'
    BILLING_WAIVE = 'billing.waive'

    # --- Ta'minot ---
    ACQ_MANAGE = 'acq.manage'
    SERIALS_MANAGE = 'serials.manage'

    # --- Zal ---
    ROOM_DESK = 'room.desk'
    ROOM_MANAGE = 'room.manage'

    # --- Tizim ---
    REPORTS_VIEW = 'reports.view'
    REPORTS_EXPORT = 'reports.export'
    MODERATE_REVIEWS = 'moderate.reviews'
    SETTINGS_MANAGE = 'settings.manage'
    AUDIT_VIEW = 'audit.view'


#: Admin interfeysi va sozlamalar sahifasi uchun guruhlangan ro'yxat
PERMISSION_GROUPS = [
    ("Katalog", [
        (Perms.CATALOG_VIEW, "Yozuvlarni ko'rish"),
        (Perms.CATALOG_EDIT, "Yozuv yaratish/tahrirlash"),
        (Perms.CATALOG_DELETE, "Yozuvni o'chirish"),
        (Perms.CATALOG_IMPORT, "Import/eksport"),
    ]),
    ("Fond", [
        (Perms.ITEMS_MANAGE, "Nusxalarni boshqarish"),
        (Perms.ITEMS_WITHDRAW, "Hisobdan chiqarish"),
        (Perms.INVENTORY_MANAGE, "Inventarizatsiya"),
    ]),
    ("Sirkulyatsiya", [
        (Perms.CIRC_CHECKOUT, "Kitob berish"),
        (Perms.CIRC_CHECKIN, "Kitob qabul qilish"),
        (Perms.CIRC_RENEW, "Muddat uzaytirish"),
        (Perms.CIRC_HOLDS, "Navbatlarni boshqarish"),
        (Perms.CIRC_OVERRIDE, "Qoidani buzib bajarish"),
    ]),
    ("A'zolar", [
        (Perms.PATRONS_VIEW, "A'zolarni ko'rish"),
        (Perms.PATRONS_EDIT, "A'zo yaratish/tahrirlash"),
        (Perms.PATRONS_BLOCK, "Bloklash / ochish"),
    ]),
    ("Pul", [
        (Perms.BILLING_CHARGE, "Qarz yozish"),
        (Perms.BILLING_COLLECT, "To'lov qabul qilish"),
        (Perms.BILLING_WAIVE, "Qarzni kechirish"),
    ]),
    ("Ta'minot", [
        (Perms.ACQ_MANAGE, "Akvizitsiya"),
        (Perms.SERIALS_MANAGE, "Davriy nashrlar"),
    ]),
    ("O'quv zali", [
        (Perms.ROOM_DESK, "Zal deski (kirish/chiqish)"),
        (Perms.ROOM_MANAGE, "Zalni sozlash"),
    ]),
    ("Tizim", [
        (Perms.REPORTS_VIEW, "Hisobotlarni ko'rish"),
        (Perms.REPORTS_EXPORT, "Hisobot eksporti"),
        (Perms.MODERATE_REVIEWS, "Sharh moderatsiyasi"),
        (Perms.SETTINGS_MANAGE, "Sozlamalar"),
        (Perms.AUDIT_VIEW, "Audit jurnali"),
    ]),
]

ALL_PERMISSIONS = [flag for _, items in PERMISSION_GROUPS for flag, _ in items]

#: Standart rollarga biriktiriladigan ruxsatlar (migratsiya shu yerdan seed qiladi)
DEFAULT_ROLE_PERMISSIONS = {
    Roles.ADMIN: ['*'],
    Roles.LIBRARIAN: [
        Perms.CATALOG_VIEW, Perms.CATALOG_EDIT, Perms.CATALOG_DELETE, Perms.CATALOG_IMPORT,
        Perms.ITEMS_MANAGE, Perms.ITEMS_WITHDRAW, Perms.INVENTORY_MANAGE,
        Perms.CIRC_CHECKOUT, Perms.CIRC_CHECKIN, Perms.CIRC_RENEW, Perms.CIRC_HOLDS,
        Perms.CIRC_OVERRIDE,
        Perms.PATRONS_VIEW, Perms.PATRONS_EDIT, Perms.PATRONS_BLOCK,
        Perms.BILLING_CHARGE, Perms.BILLING_COLLECT, Perms.BILLING_WAIVE,
        Perms.ROOM_DESK,
        Perms.REPORTS_VIEW, Perms.REPORTS_EXPORT, Perms.MODERATE_REVIEWS,
        Perms.SETTINGS_MANAGE,
    ],
    # O'quvchilar — xodim ruxsati yo'q
    Roles.EMPLOYEE: [],
    Roles.STUDENT: [],
}

#: Tayyor ish o'rinlari. Birinchi ikkitasi migratsiya bilan bazaga yoziladi;
#: qolganlari tegishli modul (o'quv zali, ta'minot) yoqilganda kerak bo'ladi.
ROLE_PRESETS = {
    "Kataloglovchi": [Perms.CATALOG_VIEW, Perms.CATALOG_EDIT, Perms.CATALOG_IMPORT,
                      Perms.ITEMS_MANAGE, Perms.REPORTS_EXPORT],
    "Abonement xodimi": [Perms.CATALOG_VIEW, Perms.CIRC_CHECKOUT, Perms.CIRC_CHECKIN,
                         Perms.CIRC_RENEW, Perms.CIRC_HOLDS, Perms.PATRONS_VIEW,
                         Perms.PATRONS_EDIT, Perms.BILLING_CHARGE, Perms.BILLING_COLLECT],
    "Zal xodimi": [Perms.CATALOG_VIEW, Perms.ROOM_DESK, Perms.PATRONS_VIEW],
    "Ta'minot xodimi": [Perms.CATALOG_VIEW, Perms.ACQ_MANAGE, Perms.SERIALS_MANAGE,
                        Perms.ITEMS_MANAGE],
}


def user_permissions(user) -> set:
    """Foydalanuvchining amaldagi ruxsatlari to'plami (o'quvchida — bo'sh)."""
    if user is None or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ALL_PERMISSIONS)

    flags = set()
    # Xodimda bir nechta rol bo'lishi mumkin — hammasining ruxsatlari qo'shiladi
    for role in staff_roles(user):
        perms = role.permissions or []
        if '*' in perms:
            return set(ALL_PERMISSIONS)
        flags.update(perms)
    return flags


def has_perm(user, *flags) -> bool:
    """Foydalanuvchida berilgan ruxsat(lar)dan kamida bittasi bormi."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    granted = user_permissions(user)
    return any(flag in granted for flag in flags)


def _forbidden(request):
    return render(request, '403.html', status=403)


def require_perm(*flags):
    """Xodim view'i: berilgan ruxsatlardan kamida bittasi talab qilinadi."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if has_perm(request.user, *flags):
                return view_func(request, *args, **kwargs)
            return _forbidden(request)
        return _wrapped
    return decorator


def staff_required(view_func):
    """Istalgan kutubxona xodimi (aniq ruxsat shart emas)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if is_library_staff(request.user):
            return view_func(request, *args, **kwargs)
        return _forbidden(request)
    return _wrapped


def reader_required(view_func):
    """Faqat o'quvchi: kitob olish, navbat, sevimli, sharh, shaxsiy sahifalar.

    Kutubxona xodimi va administrator sahifani ochsa — o'z ish joyiga
    yo'naltiriladi; amal (POST/HTMX) yuborsa — 403.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if is_library_staff(request.user):
            if request.method != 'GET' or getattr(request, 'htmx', False):
                return _forbidden(request)
            messages.info(request, "Bu sahifa o'quvchilar uchun — siz xodim hisobidasiz.")
            return redirect(home_url(request.user))
        return view_func(request, *args, **kwargs)
    return _wrapped
