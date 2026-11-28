"""
HEMIS ro'yxatlarini kutubxona hisoblari va a'zoliklariga aylantirish.

Qoidalar:
  * hisob HEMIS ID raqami bo'yicha topiladi — oAuth kirishdagi bilan bir xil,
    shuning uchun keyin o'zi kirgan talabada ikkinchi hisob ochilmaydi;
  * faqat HEMIS'dan kelgan maydonlar yangilanadi, bo'sh qiymat mavjudini
    o'chirmaydi (telefon, rasm, pochta ro'yxatda umuman kelmaydi);
  * hech kim o'chirilmaydi, bloklanmaydi va rollari o'zgartirilmaydi;
  * kutubxona xodimiga a'zolik ochilmaydi (`sync_patron` qoidasi);
  * qayta ishga tushirish xavfsiz.
"""
import logging
import threading
from collections import Counter
from datetime import UTC, datetime, timedelta

from django.db import connection, transaction
from django.utils import timezone

from audit.models import JobRun
from core.autojobs import exclusive

from ..models import EmployeProfile, StudentProfile, User
from ..services import ensure_reader_role, hemis_username, sync_patron
from .client import HemisClient, HemisError

logger = logging.getLogger('hemis')

JOB_NAME = 'hemis_sync'
#: pg_advisory_lock kaliti ("XIU2")
LOCK_KEY = 0x58495532
STUDENTS = 'students'
EMPLOYEES = 'employees'
SOURCES = {
    STUDENTS: ('v1/data/student-list', {}),          # standart: o'qiyotganlar
    EMPLOYEES: ('v1/data/employee-list', {'type': 'all'}),
}
LABELS = {STUDENTS: "Talabalar", EMPLOYEES: "Xodimlar"}
#: Shuncha vaqt belgi bermagan «bajarilmoqda» yozuvi uzilgan hisoblanadi
STALE_AFTER = timedelta(minutes=10)
PROGRESS_EVERY = 100


# --------------------------------------------------------------------------
#  Qiymatlarni tozalash
# --------------------------------------------------------------------------

def _text(value, limit):
    return str(value or '').strip()[:limit]


def _name(block, limit=100):
    """`{"code": .., "name": ..}` ko'rinishidagi maydonning nomi."""
    return _text(block.get('name'), limit) if isinstance(block, dict) else ''


def _birth_date(value):
    """UTC timestamp -> sana. Mahalliy yarim tun (UTC-5 soat) ham o'sha kunga tushadi."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value == 0:
        return None
    try:
        return (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=value, hours=12)).date()
    except (OverflowError, ValueError):
        return None


def _hemis_id(value):
    return str(value).strip() if value not in (None, '', 0) else ''


def _assign(instance, values):
    """Bo'sh bo'lmagan va farq qiladigan maydonlarni yozadi; o'zgarganlar ro'yxati."""
    changed = []
    for field, value in values.items():
        if value not in (None, '') and getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)
    return changed


def _user_values(item):
    gender = _name(item.get('gender'), 10)
    return {
        'first_name': _text(item.get('first_name'), 50),
        'second_name': _text(item.get('second_name'), 50),
        'third_name': _text(item.get('third_name'), 50),
        'birth_day': _birth_date(item.get('birth_date')),
        'gender': gender if gender in User.Gender.values else '',
    }


# --------------------------------------------------------------------------
#  Bitta yozuv
# --------------------------------------------------------------------------

@transaction.atomic
def _apply(item, id_field, user_type, prefix, profile_model, profile_values):
    """'new' | 'updated' | 'same' | 'skipped'."""
    hemis_id = _hemis_id(item.get(id_field))
    values = _user_values(item)
    if not hemis_id or not (values['first_name'] or values['second_name']):
        return 'skipped'

    username = hemis_username(hemis_id, user_type, prefix)
    user = User.objects.filter(username=username).first()
    created = user is None
    if created:
        user = User(username=username, user_type=user_type)
        user.set_unusable_password()          # faqat HEMIS orqali kiradi
        _assign(user, values)
        user.save()
        changed = []
    else:
        if user.is_superuser or user.user_type != user_type:
            return 'skipped'
        changed = _assign(user, values)
        if changed:
            user.save(update_fields=changed + ['updated_at'])

    profile, _ = profile_model.objects.get_or_create(user=user)
    profile_changed = _assign(profile, profile_values)
    if profile_changed:
        profile.save(update_fields=profile_changed + ['updated_at'])

    # Toifa profil ma'lumotidan aniqlanadi — keshdagi eski nusxa qolmasin
    if user_type == User.UserType.STUDENT:
        user.student_profile = profile
    else:
        user.employe_profile = profile
        ensure_reader_role(profile)

    had_patron = hasattr(user, 'patron')
    sync_patron(user)

    if created:
        return 'new'
    return 'updated' if changed or profile_changed or not had_patron else 'same'


def apply_student(item):
    return _apply(item, 'student_id_number', User.UserType.STUDENT, 'st', StudentProfile, {
        'faculty': _name(item.get('department')),
        'group': _name(item.get('group')),
        'level': _name(item.get('level')),
        'semester': _name(item.get('semester')),
        'education_form': _name(item.get('educationForm')),
        'education_type': _name(item.get('educationType')),
        'payment_form': _name(item.get('paymentForm')),
    })


def apply_employee(item):
    return _apply(item, 'employee_id_number', User.UserType.EMPLOYE, 'emp', EmployeProfile, {
        'department': _name(item.get('department'), 500),
        'position': _name(item.get('staffPosition'), 500),
    })


def _main_jobs(items):
    """Bir xodim bir necha o'rinda ishlasa — asosiy ish joyi qoladi."""
    chosen = {}
    for item in items:
        if item.get('active') is False:
            continue
        key = _hemis_id(item.get('employee_id_number'))
        if not key:
            continue
        main = 'asosiy' in _name(item.get('employmentForm')).lower()
        if key not in chosen or (main and not chosen[key][0]):
            chosen[key] = (main, item)
    return [item for _, item in chosen.values()]


# --------------------------------------------------------------------------
#  Butun sinxronlash
# --------------------------------------------------------------------------

def preview(client, kinds=(STUDENTS, EMPLOYEES)):
    """Hech narsa yozmasdan HEMIS'dagi yozuvlar sonini oladi."""
    counts = {}
    for kind in kinds:
        path, params = SOURCES[kind]
        items, pagination = client.page(path, 1, limit=1, **params)
        counts[kind] = pagination.get('totalCount', len(items))
    return counts


def _process(items, apply, stats, kind, progress):
    for item in items:
        try:
            result = apply(item)
        except Exception:
            result = 'failed'
            # Birinchi xatolar to'liq, qolgani faqat sanaladi
            if stats[f'{kind}_failed'] < 5:
                logger.exception("HEMIS yozuvini saqlab bo'lmadi (%s, id=%s)", kind, item.get('id'))
        stats[f'{kind}_{result}'] += 1
        stats[f'{kind}_done'] += 1
        if stats[f'{kind}_done'] % PROGRESS_EVERY == 0:
            progress(stats)


def run(token, kinds=(STUDENTS, EMPLOYEES), progress=lambda stats: None, client=None):
    """Sinxronlashni shu oqimda bajaradi va hisoblagichlarni qaytaradi."""
    client = client or HemisClient(token)
    stats = Counter()
    with exclusive(LOCK_KEY) as locked:
        if not locked:
            raise HemisError("Boshqa sinxronlash hozir ishlayapti.")
        for kind in kinds:
            path, params = SOURCES[kind]
            if kind == STUDENTS:
                for items, pagination in client.pages(path, **params):
                    stats[f'{kind}_total'] = pagination.get('totalCount', 0)
                    _process(items, apply_student, stats, kind, progress)
                    progress(stats)
            else:
                rows = [row for items, _ in client.pages(path, **params) for row in items]
                people = _main_jobs(rows)
                stats[f'{kind}_total'] = len(people)
                progress(stats)
                _process(people, apply_employee, stats, kind, progress)
                progress(stats)
    return dict(stats)


def summary(stats):
    parts = []
    for kind, label in LABELS.items():
        if f'{kind}_done' in stats:
            parts.append(f"{label}: {stats.get(f'{kind}_new', 0)} yangi, "
                         f"{stats.get(f'{kind}_updated', 0)} yangilandi, "
                         f"{stats.get(f'{kind}_failed', 0)} xato")
    return '; '.join(parts) or "Yozuv topilmadi"


# --------------------------------------------------------------------------
#  Panel uchun: fonda ishga tushirish va holat
# --------------------------------------------------------------------------

def close_stale():
    """Server qayta ishga tushganda uzilib qolgan yozuvlarni yopadi."""
    limit = timezone.now() - STALE_AFTER
    for record in JobRun.objects.filter(name=JOB_NAME, status=JobRun.Status.RUNNING):
        beat = record.stats.get('beat')
        seen = datetime.fromisoformat(beat) if beat else record.started_at
        if seen < limit:
            _finish(record, JobRun.Status.FAILED,
                    "Uzilib qoldi (server qayta ishga tushgan bo'lishi mumkin). Qayta boshlang.")


def is_running():
    close_stale()
    return JobRun.objects.filter(name=JOB_NAME, status=JobRun.Status.RUNNING).exists()


def _finish(record, status, message):
    record.status = status
    record.message = message[:300]
    record.finished_at = timezone.now()
    record.duration_ms = int((record.finished_at - record.started_at).total_seconds() * 1000)
    record.save(update_fields=['status', 'message', 'stats', 'finished_at', 'duration_ms'])


def reporter(record):
    """Oraliq hisoblagichlarni yozuvga saqlaydigan funksiya."""
    def progress(stats):
        record.stats = {**stats, 'beat': timezone.now().isoformat()}
        record.save(update_fields=['stats'])
    return progress


def execute(record, token, kinds):
    """`JobRun` yozuvini yuritib sinxronlaydi (xato yozuvning o'ziga tushadi)."""
    try:
        stats = run(token, kinds, progress=reporter(record))
    except HemisError as exc:
        _finish(record, JobRun.Status.FAILED, str(exc))
    except Exception as exc:
        logger.exception("HEMIS sinxronlash xato bilan tugadi")
        _finish(record, JobRun.Status.FAILED, f"Kutilmagan xato: {type(exc).__name__}")
    else:
        record.stats = stats
        _finish(record, JobRun.Status.SUCCESS, summary(stats))


def _worker(record_pk, token, kinds):
    try:
        execute(JobRun.objects.get(pk=record_pk), token, kinds)
    finally:
        connection.close()


def start(token, kinds):
    """Fon oqimida boshlaydi. Boshqasi ishlayotgan bo'lsa `None`."""
    if is_running():
        return None
    record = JobRun.objects.create(name=JOB_NAME, status=JobRun.Status.RUNNING)
    threading.Thread(target=_worker, args=(record.pk, token, tuple(kinds)),
                     name='hemis-sync', daemon=True).start()
    return record
