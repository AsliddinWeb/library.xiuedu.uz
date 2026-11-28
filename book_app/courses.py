"""
Fan adabiyoti (course reserves) biznes mantig'i.

Kim nima qila oladi:
  * hamma (tizimga kirgan) — faol va ichida kitobi bor ro'yxatlarni ko'radi;
  * o'qituvchi — o'z fani uchun ro'yxat ochadi va faqat o'zinikini tahrirlaydi;
  * kutubxonachi (katalog tahriri huquqi) — hammasini boshqaradi.
"""
import re

from django.db.models import Count, Max, Q

from user_app.models import StudentProfile
from user_app.permissions import Perms, has_perm
from user_app.services import is_teacher

from .models import CourseReserve, CourseReserveItem
from .translit import fold

#: Bitta fan ro'yxatidagi kitoblar chegarasi
MAX_ITEMS_PER_COURSE = 200


def is_curator(user) -> bool:
    return has_perm(user, Perms.CATALOG_EDIT)


def can_create_reserve(user) -> bool:
    return is_curator(user) or is_teacher(user)


def can_edit_reserve(user, reserve) -> bool:
    if not user.is_authenticated:
        return False
    if is_curator(user):
        return True
    # O'qituvchilik toifasi olib tashlansa, tahrir huquqi ham yo'qoladi
    return user.pk in (reserve.teacher_id, reserve.created_by_id) and is_teacher(user)


def _with_counts(queryset):
    return (queryset
            .select_related('teacher')
            .annotate(
                books_count=Count('items'),
                required_count=Count(
                    'items',
                    filter=Q(items__importance=CourseReserveItem.Importance.REQUIRED))))


def published_reserves():
    """O'quvchilarga ko'rinadigan ro'yxatlar: faol va bo'sh emas."""
    return (_with_counts(CourseReserve.objects.filter(is_active=True))
            .filter(books_count__gt=0)
            .order_by('course_name', 'semester', 'pk'))


def own_reserves(user):
    """O'qituvchining o'z ro'yxatlari (bo'sh va yopilganlari ham)."""
    mine = Q(teacher=user) | Q(created_by=user)
    return _with_counts(CourseReserve.objects.filter(mine)).order_by('-updated_at')


def filter_reserves(queryset, query='', faculty='', semester=''):
    # Har bir so'z alohida qidiriladi — "matematika karimov" ham topadi
    for word in fold(query).split():
        queryset = queryset.filter(search_text__icontains=word)
    if faculty:
        # Umumiy fanlar (fakultet ko'rsatilmagan) har qanday fakultetga tegishli
        queryset = queryset.filter(Q(faculty__iexact=faculty) | Q(faculty=''))
    if str(semester).isdigit():
        queryset = queryset.filter(Q(semester=int(semester)) | Q(semester__isnull=True))
    return queryset


def semester_number(value):
    """HEMIS'dagi "8-semestr" -> 8. Aniqlab bo'lmasa — None."""
    match = re.search(r'\d+', value or '')
    return int(match.group()) if match else None


def reserves_for_student(user):
    """Talabaning fakulteti va semestriga mos ro'yxatlar ("Sizning fanlaringiz")."""
    profile = StudentProfile.objects.filter(user=user).first()
    if profile is None or not profile.faculty:
        return CourseReserve.objects.none()
    queryset = filter_reserves(published_reserves(), faculty=profile.faculty,
                               semester=semester_number(profile.semester) or '')
    # Hech bo'lmasa fakultet yoki semestr aniq ko'rsatilganlari — "hamma uchun"lar emas
    return queryset.exclude(faculty='', semester__isnull=True)


def faculty_choices():
    """Fakultetlar ro'yxati — HEMIS'dan kelgan talaba ma'lumoti va mavjud ro'yxatlardan."""
    names = set(StudentProfile.objects.exclude(faculty__isnull=True).exclude(faculty='')
                .values_list('faculty', flat=True).distinct())
    names.update(CourseReserve.objects.exclude(faculty='')
                 .values_list('faculty', flat=True).distinct())
    return sorted(names)


def add_book(reserve, book, importance=CourseReserveItem.Importance.REQUIRED, note=''):
    """(qo'shildimi, xabar)."""
    if reserve.items.filter(book=book).exists():
        return False, "Kitob ro'yxatda bor."
    if reserve.items.count() >= MAX_ITEMS_PER_COURSE:
        return False, f"Ro'yxat to'lgan ({MAX_ITEMS_PER_COURSE} ta)."
    if importance not in CourseReserveItem.Importance.values:
        importance = CourseReserveItem.Importance.REQUIRED
    last = reserve.items.aggregate(last=Max('order'))['last'] or 0
    _, created = CourseReserveItem.objects.get_or_create(
        reserve=reserve, book=book,
        defaults={'importance': importance, 'note': note[:255], 'order': last + 1})
    return created, f"«{book.title}» qo'shildi."


def update_item(item, importance, note):
    if importance in CourseReserveItem.Importance.values:
        item.importance = importance
    item.note = (note or '').strip()[:255]
    item.save(update_fields=['importance', 'note'])


def remove_book(reserve, book):
    deleted, _ = reserve.items.filter(book=book).delete()
    return bool(deleted), "Kitob ro'yxatdan olib tashlandi."
