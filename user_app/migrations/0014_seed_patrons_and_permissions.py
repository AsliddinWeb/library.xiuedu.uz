"""
P1 data-migratsiyasi:

  1. A'zo toifalari (6 ta) — standart qoidalar bilan.
  2. Standart rollarga granular ruxsatlar biriktiriladi.
  3. MAVJUD HAR BIR FOYDALANUVCHIGA a'zolik (Patron) ochiladi — talabaga ham,
     xodimga ham. Shu bilan xodimlar ham kitob ola oladigan bo'ladi.

Toifa HEMIS ma'lumotidan aniqlanadi (lavozim / ta'lim turi). Keyin kutubxonachi
admin panelidan qo'lda o'zgartirishi mumkin.

Orqaga qaytarish: yozuvlar o'chirilmaydi (ma'lumot yo'qotmaslik uchun) —
jadvalning o'zi sxema migratsiyasi bilan qaytariladi.
"""
from django.db import migrations

CATEGORIES = [
    # (code, name, loan_days, loan_limit, hold_limit, renewals, membership_months, deposit, order)
    ('TALABA', "Talaba", 14, 5, 3, 1, 0, False, 10),
    ('MAGISTR', "Magistrant", 21, 7, 4, 2, 0, False, 20),
    ('DOKTORANT', "Doktorant / tadqiqotchi", 30, 10, 5, 2, 0, False, 30),
    ('PROF_OQITUVCHI', "Professor-o'qituvchi", 30, 10, 5, 3, 0, False, 40),
    ('XODIM', "Xodim", 21, 5, 3, 1, 0, False, 50),
    ('TASHQI', "Tashqi o'quvchi", 7, 2, 1, 0, 12, True, 60),
]

TEACHER_WORDS = ('professor', 'dotsent', 'docent', "o'qituvchi", 'oqituvchi', 'ukituvchi',
                 'muallim', 'assistent', 'kafedra mudiri')
MASTER_WORDS = ('magistr',)
PHD_WORDS = ('doktoran', 'tadqiqotchi', 'phd', 'aspirant')

# `user_app/permissions.py` dagi DEFAULT_ROLE_PERMISSIONS bilan mos
ROLE_PERMISSIONS = {
    'Admin': ['*'],
    'LibraryAdmin': [
        'catalog.view', 'catalog.edit', 'catalog.delete', 'catalog.import',
        'items.manage', 'items.withdraw', 'inventory.manage',
        'circ.checkout', 'circ.checkin', 'circ.renew', 'circ.holds', 'circ.override',
        'patrons.view', 'patrons.edit', 'patrons.block',
        'billing.charge', 'billing.collect', 'billing.waive',
        'room.desk', 'reports.view', 'reports.export', 'moderate.reviews',
        'settings.manage',
    ],
    'Employee': ['catalog.view'],
    'Student': ['catalog.view'],
}


def _contains(text, words):
    text = (text or '').lower()
    return any(word in text for word in words)


def seed(apps, schema_editor):
    PatronCategory = apps.get_model('user_app', 'PatronCategory')
    Patron = apps.get_model('user_app', 'Patron')
    Role = apps.get_model('user_app', 'Role')
    User = apps.get_model('user_app', 'User')

    # --- 1. Toifalar ---
    by_code = {}
    for (code, name, days, limit, holds, renewals, months, deposit, order) in CATEGORIES:
        category, _ = PatronCategory.objects.get_or_create(
            code=code,
            defaults={
                'name': name, 'default_loan_days': days, 'loan_limit': limit,
                'hold_limit': holds, 'renewals_allowed': renewals,
                'membership_months': months, 'requires_deposit': deposit, 'order': order,
            },
        )
        by_code[code] = category

    # --- 2. Rollarga ruxsatlar ---
    for name, perms in ROLE_PERMISSIONS.items():
        Role.objects.filter(name=name).update(permissions=perms)

    # --- 3. Mavjud foydalanuvchilarga a'zolik ---
    existing = set(Patron.objects.values_list('user_id', flat=True))
    counter = Patron.objects.count()

    for user in User.objects.all().iterator():
        if user.pk in existing:
            continue

        if user.user_type == 'EMPLOYE':
            profile = getattr(user, 'employe_profile', None)
            position = getattr(profile, 'position', '') if profile else ''
            code = 'PROF_OQITUVCHI' if _contains(position, TEACHER_WORDS) else 'XODIM'
        else:
            profile = getattr(user, 'student_profile', None)
            haystack = ' '.join(filter(None, [
                getattr(profile, 'education_type', '') if profile else '',
                getattr(profile, 'level', '') if profile else '',
            ]))
            if _contains(haystack, PHD_WORDS):
                code = 'DOKTORANT'
            elif _contains(haystack, MASTER_WORDS):
                code = 'MAGISTR'
            else:
                code = 'TALABA'

        counter += 1
        Patron.objects.create(
            user=user,
            card_number=f"XIU-{counter:06d}",
            category=by_code[code],
            status='ACTIVE',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0013_patroncategory_role_created_at_role_permissions_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
