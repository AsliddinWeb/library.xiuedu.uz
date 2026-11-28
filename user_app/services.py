"""
A'zolik (Patron) biznes mantig'i.

Asosiy vazifa: HEMIS orqali kirgan HAR QANDAY foydalanuvchiga — talaba, magistrant,
doktorant, o'qituvchi yoki xodimga — kutubxona bileti (`Patron`) ochish va uning
toifasini HEMIS ma'lumotidan aniqlash. Shu bilan "faqat talaba kitob oladi"
cheklovi yo'qoladi.
"""
import calendar
import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.timezone import now

from .models import Patron, PatronCategory, Role, User
from .roles import Roles, is_library_staff

logger = logging.getLogger('patrons')

CARD_PREFIX = getattr(settings, 'PATRON_CARD_PREFIX', 'XIU')
CARD_DIGITS = 6

# Lavozim nomidan professor-o'qituvchini aniqlash (HEMIS matni har xil yoziladi)
TEACHER_WORDS = ('professor', 'dotsent', 'docent', "o'qituvchi", 'oqituvchi', 'ukituvchi',
                 'muallim', 'assistent', 'kafedra mudiri')
MASTER_WORDS = ('magistr',)
PHD_WORDS = ('doktoran', 'tadqiqotchi', 'phd', 'aspirant', 'stajyor-tadqiqotchi')


# --------------------------------------------------------------------------
#  Bilet raqami
# --------------------------------------------------------------------------

def next_card_number() -> str:
    """Keyingi bo'sh bilet raqami: XIU-000123.

    Raqamlar nol bilan to'ldirilgani uchun matn bo'yicha saralash = raqam bo'yicha
    saralash. Poyga holatida `IntegrityError` bo'lishi mumkin — chaqiruvchi
    (`sync_patron`) qayta urinadi.
    """
    prefix = f"{CARD_PREFIX}-"
    last = (Patron.objects
            .filter(card_number__startswith=prefix)
            .order_by('-card_number')
            .values_list('card_number', flat=True)
            .first())
    number = 0
    if last:
        match = re.search(r'(\d+)$', last)
        if match:
            number = int(match.group(1))
    return f"{prefix}{number + 1:0{CARD_DIGITS}d}"


# --------------------------------------------------------------------------
#  HEMIS hisobi (oAuth kirish va ro'yxat sinxronlash uchun umumiy)
# --------------------------------------------------------------------------

def hemis_username(hemis_id, user_type, prefix):
    """HEMIS raqamidan login nomi.

    Talaba va xodim raqamlari ikki alohida HEMIS'dan keladi. Bir xil raqam
    chiqib qolsa, biri ikkinchisining hisobini egallab olmasligi uchun
    keyingisiga prefiks qo'shiladi.
    """
    username = str(hemis_id)
    if User.objects.filter(username=username).exclude(user_type=user_type).exists():
        username = f'{prefix}-{username}'
        logger.warning("HEMIS raqami ikki turdagi hisobda uchradi, %s ishlatildi", username)
    return username


def ensure_reader_role(profile):
    """HEMIS xodimiga o'quvchi roli beradi; mavjud rollarga tegmaydi."""
    role, _ = Role.objects.get_or_create(name=Roles.EMPLOYEE)
    # current_role faqat birinchi marta o'rnatiladi (mavjudini bekor qilmaslik uchun)
    if profile.current_role is None:
        profile.current_role = role
        profile.save(update_fields=['current_role'])
    if not profile.roles.filter(pk=role.pk).exists():
        profile.roles.add(role)


# --------------------------------------------------------------------------
#  Toifa
# --------------------------------------------------------------------------

def _contains(text, words):
    text = (text or '').lower()
    return any(word in text for word in words)


def resolve_category_code(user) -> str:
    """Foydalanuvchining HEMIS ma'lumotidan a'zo toifasini aniqlaydi."""
    if user.user_type == User.UserType.EMPLOYE:
        profile = getattr(user, 'employe_profile', None)
        position = getattr(profile, 'position', '') if profile else ''
        if _contains(position, TEACHER_WORDS):
            return PatronCategory.Code.TEACHER
        return PatronCategory.Code.STAFF

    profile = getattr(user, 'student_profile', None)
    haystack = ' '.join(filter(None, [
        getattr(profile, 'education_type', '') if profile else '',
        getattr(profile, 'level', '') if profile else '',
    ]))
    if _contains(haystack, PHD_WORDS):
        return PatronCategory.Code.PHD
    if _contains(haystack, MASTER_WORDS):
        return PatronCategory.Code.MASTER
    return PatronCategory.Code.STUDENT


def is_teacher(user) -> bool:
    """Professor-o'qituvchimi — a'zo toifasi bo'yicha (fan adabiyotini u tuzadi).

    A'zolik hali ochilmagan bo'lsa HEMIS lavozimidan aniqlanadi.
    """
    if user is None or not user.is_authenticated:
        return False
    if user.user_type != User.UserType.EMPLOYE:
        return False
    patron = Patron.objects.filter(user=user).select_related('category').first()
    code = patron.category.code if patron else resolve_category_code(user)
    return code == PatronCategory.Code.TEACHER


def get_category(code) -> PatronCategory:
    """Toifani kod bo'yicha oladi; bo'lmasa standart qiymatlar bilan yaratadi."""
    category, _ = PatronCategory.objects.get_or_create(
        code=code, defaults=dict(DEFAULT_CATEGORIES.get(code, {'name': str(code)})))
    return category


# Standart toifalar — migratsiya ham, `get_category` ham shu jadvaldan foydalanadi.
# Aniq raqamlar kutubxonachi bilan kelishilgach sozlamadan o'zgartiriladi.
DEFAULT_CATEGORIES = {
    PatronCategory.Code.STUDENT: {
        'name': "Talaba", 'default_loan_days': 14, 'loan_limit': 5, 'hold_limit': 3,
        'renewals_allowed': 1, 'order': 10,
    },
    PatronCategory.Code.MASTER: {
        'name': "Magistrant", 'default_loan_days': 21, 'loan_limit': 7, 'hold_limit': 4,
        'renewals_allowed': 2, 'order': 20,
    },
    PatronCategory.Code.PHD: {
        'name': "Doktorant / tadqiqotchi", 'default_loan_days': 30, 'loan_limit': 10,
        'hold_limit': 5, 'renewals_allowed': 2, 'order': 30,
    },
    PatronCategory.Code.TEACHER: {
        'name': "Professor-o'qituvchi", 'default_loan_days': 30, 'loan_limit': 10,
        'hold_limit': 5, 'renewals_allowed': 3, 'order': 40,
    },
    PatronCategory.Code.STAFF: {
        'name': "Xodim", 'default_loan_days': 21, 'loan_limit': 5, 'hold_limit': 3,
        'renewals_allowed': 1, 'order': 50,
    },
    PatronCategory.Code.EXTERNAL: {
        'name': "Tashqi o'quvchi", 'default_loan_days': 7, 'loan_limit': 2, 'hold_limit': 1,
        'renewals_allowed': 0, 'membership_months': 12, 'requires_deposit': True, 'order': 60,
    },
}


def membership_expiry(category, start=None):
    """Toifaga qarab a'zolik tugash sanasi (0 oy — muddatsiz).

    Kalendar bo'yicha hisoblanadi (oy = 30 kun emas): 31-yanvar + 1 oy = 28/29-fevral.
    """
    if not category.membership_months:
        return None

    start = start or now().date()
    total = start.month - 1 + category.membership_months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


# --------------------------------------------------------------------------
#  Sinxronizatsiya
# --------------------------------------------------------------------------

@transaction.atomic
def sync_patron(user) -> Patron | None:
    """Foydalanuvchiga a'zolik ochadi yoki mavjudini yangilaydi.

    Kutubxona xodimi va administratorga a'zolik ochilmaydi (`None`) — ular
    kitob olmaydi.

    HEMIS'ga har kirishda chaqiriladi:
      - a'zolik bo'lmasa — yaratiladi (bilet raqami beriladi);
      - toifa o'zgargan bo'lsa (talaba -> magistrant) — yangilanadi;
      - muddati o'tgan, lekin HEMIS'da hali faol bo'lsa — qayta faollashtiriladi.

    Bloklangan a'zoni HEMIS kirishi ochib yubormaydi (bu xodimning qaroriga bog'liq).
    """
    if is_library_staff(user):
        return None

    category = get_category(resolve_category_code(user))
    patron = Patron.objects.filter(user=user).first()

    if patron is None:
        for attempt in range(3):
            try:
                patron = Patron.objects.create(
                    user=user,
                    card_number=next_card_number(),
                    category=category,
                    status=Patron.Status.ACTIVE,
                )
                break
            except IntegrityError:
                if attempt == 2:
                    raise
                logger.warning("Bilet raqami band chiqdi, qayta urinilmoqda (%s)", user.username)
        patron.expires_on = membership_expiry(category, patron.registered_on)
        if patron.expires_on:
            patron.save(update_fields=['expires_on'])
        logger.info("Yangi a'zo: %s (%s, %s)", patron.card_number, user.username, category.code)
        return patron

    changed = []
    if patron.category_id != category.pk:
        patron.category = category
        changed.append('category')
    if patron.status == Patron.Status.EXPIRED and not patron.is_expired:
        patron.status = Patron.Status.ACTIVE
        changed.append('status')
    if changed:
        patron.save(update_fields=changed + ['updated_at'])
        logger.info("A'zolik yangilandi: %s (%s)", patron.card_number, ', '.join(changed))
    return patron


def get_or_create_patron(user):
    """O'quvchining a'zoligini oladi, bo'lmasa ochadi. Xodimda — `None`."""
    if is_library_staff(user):
        return None
    patron = getattr(user, 'patron', None)
    return patron if patron is not None else sync_patron(user)
