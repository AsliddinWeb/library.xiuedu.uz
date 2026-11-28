from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


# User Model
class User(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        STUDENT = 'STUDENT', _('Talaba')
        EMPLOYE = 'EMPLOYE', _('Xodim')

    class Gender(models.TextChoices):
        MALE = 'Erkak', _('Erkak')
        FEMALE = 'Ayol', _('Ayol')

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.STUDENT,
        verbose_name="Foydalanuvchi turi"
    )

    username = models.CharField(max_length=150, unique=True, verbose_name="Foydalanuvchi nomi")
    email = models.EmailField(null=True, blank=True, verbose_name="Elektron pochta")
    phone = models.CharField(max_length=15, null=True, blank=True, verbose_name="Telefon raqami")

    first_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="Ismi")
    second_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="Familiyasi")
    third_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="Sharifi")

    image = models.ImageField(upload_to="user_images/", null=True, blank=True, verbose_name="Rasm")
    birth_day = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    gender = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True, verbose_name="Jinsi")

    country = models.CharField(max_length=100, null=True, blank=True, verbose_name="Davlat")
    province = models.CharField(max_length=100, null=True, blank=True, verbose_name="Viloyat")
    district = models.CharField(max_length=100, null=True, blank=True, verbose_name="Tuman")
    address = models.TextField(null=True, blank=True, verbose_name="Manzil")

    # HEMIS identifikatorlari
    hemis_uuid = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="HEMIS UUID")
    university_id = models.CharField(max_length=50, null=True, blank=True, verbose_name="Universitet ID")

    is_active = models.BooleanField(default=True, verbose_name="Faol")
    is_staff = models.BooleanField(default=False, verbose_name="Admin panelga kirish")

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name="Yangilangan sana")

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return self.username

    def get_full_name(self):
        parts = [p for p in (self.second_name, self.first_name) if p]
        full_name = " ".join(p.upper() for p in parts)
        return full_name or self.username

# Employe Profile Model
class EmployeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employe_profile", verbose_name="Foydalanuvchi")

    department = models.TextField(null=True, blank=True, verbose_name="Bo'lim")
    position = models.TextField(null=True, blank=True, verbose_name="Lavozim")

    roles = models.ManyToManyField('Role', blank=True, related_name="employe_profiles", verbose_name="Xodim rollari")
    current_role = models.ForeignKey('Role', on_delete=models.SET_NULL, blank=True, null=True, related_name="current_employes", verbose_name="Hozirgi rol")

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "Xodim profili"
        verbose_name_plural = "Xodim profillari"

    def __str__(self):
        return self.user.username


# Student Profile Model
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile", verbose_name="Foydalanuvchi")

    faculty = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name="Fakultet")
    group = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name="Guruh")
    level = models.CharField(max_length=100, null=True, blank=True, verbose_name="Bosqich")
    semester = models.CharField(max_length=100, null=True, blank=True, verbose_name="Semestr")

    education_form = models.CharField(max_length=100, null=True, blank=True, verbose_name="Ta'lim shakli")
    education_type = models.CharField(max_length=100, null=True, blank=True, verbose_name="Ta'lim turi")
    payment_form = models.CharField(max_length=100, null=True, blank=True, verbose_name="To'lov shakli")

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "Talaba"
        verbose_name_plural = "Talabalar"

    def __str__(self):
        return self.user.username

# Role Model
class Role(models.Model):
    """Xodim roli + unga biriktirilgan granular ruxsatlar.

    `name` mavjud DB qiymatlari bilan bog'liq (Student/Employee/LibraryAdmin/Admin) —
    o'zgartirilmaydi. Ruxsatlar `permissions` ro'yxatida saqlanadi; ro'yxat ichidagi
    `"*"` — barcha ruxsatlar degani (`user_app/permissions.py`).
    """
    name = models.CharField(max_length=50, unique=True, verbose_name="Rol nomi")
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="Izoh")

    permissions = models.JSONField(
        default=list, blank=True, verbose_name="Ruxsatlar",
        help_text="Ruxsat kodlari ro'yxati, masalan [\"circ.checkout\", \"patrons.edit\"]. "
                  "\"*\" — barcha ruxsatlar.")

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Rollar"
        ordering = ['name']

    def __str__(self):
        return self.name

    def has_perm(self, flag) -> bool:
        perms = self.permissions or []
        return '*' in perms or flag in perms


# =============================================================================
#  A'ZOLIK (Patron) — kitob olish huquqining yagona manbai
#
#  MUHIM: talaba ham, xodim/o'qituvchi ham, tashqi o'quvchi ham shu model orqali
#  kitob oladi. `StudentProfile`/`EmployeProfile` endi faqat HEMIS'dan kelgan
#  akademik ma'lumot uchun — sirkulyatsiyaga aralashmaydi.
# =============================================================================

class PatronCategory(models.Model):
    """A'zo toifasi — sirkulyatsiya qoidalari shu toifa bo'yicha hal qilinadi."""

    class Code(models.TextChoices):
        STUDENT = 'TALABA', "Talaba"
        MASTER = 'MAGISTR', "Magistrant"
        PHD = 'DOKTORANT', "Doktorant / tadqiqotchi"
        TEACHER = 'PROF_OQITUVCHI', "Professor-o'qituvchi"
        STAFF = 'XODIM', "Xodim"
        EXTERNAL = 'TASHQI', "Tashqi o'quvchi"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True,
                            verbose_name="Kod")
    name = models.CharField(max_length=80, verbose_name="Nomi")
    description = models.CharField(max_length=255, blank=True, verbose_name="Izoh")

    # --- Standart qoidalar (P3'dagi CirculationRule matritsasi uchun zaxira qiymat) ---
    default_loan_days = models.PositiveIntegerField(default=14, verbose_name="Ijara muddati (kun)")
    loan_limit = models.PositiveIntegerField(default=5, verbose_name="Bir vaqtda maks. nusxa")
    hold_limit = models.PositiveIntegerField(default=3, verbose_name="Bir vaqtda maks. navbat")
    renewals_allowed = models.PositiveIntegerField(default=1, verbose_name="Uzaytirishlar soni")
    fine_per_day = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name="Kuniga jarima (so'm)")
    debt_block_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Bloklash chegarasi (so'm)",
        help_text="Qarz shu summadan oshsa yangi ijara bloklanadi. 0 — cheklanmagan.")

    # --- A'zolik ---
    membership_months = models.PositiveIntegerField(
        default=0, verbose_name="A'zolik muddati (oy)",
        help_text="0 — muddatsiz (HEMIS foydalanuvchilari uchun odatda 0).")
    requires_deposit = models.BooleanField(default=False, verbose_name="Garov talab qilinadi")
    can_borrow_reading_room_items = models.BooleanField(
        default=False, verbose_name="Faqat-zal nusxalarini olishi mumkin")

    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "A'zo toifasi"
        verbose_name_plural = "A'zo toifalari"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Patron(models.Model):
    """Kutubxona a'zosi (o'quvchi bileti).

    `user` — HEMIS orqali kirgan foydalanuvchi; tashqi a'zoda `None` bo'lishi mumkin,
    bunday a'zoning ism/aloqa ma'lumotlari shu modelning o'zida saqlanadi.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', "Faol"
        EXPIRED = 'EXPIRED', "Muddati o'tgan"
        BLOCKED = 'BLOCKED', "Bloklangan"
        DEBT = 'DEBT', "Qarzdor"
        CLOSED = 'CLOSED', "Yopilgan"

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='patron', verbose_name="Foydalanuvchi")
    card_number = models.CharField(max_length=32, unique=True, db_index=True,
                                   verbose_name="Kitobxon bileti (shtrix-kod)")
    category = models.ForeignKey(PatronCategory, on_delete=models.PROTECT,
                                 related_name='patrons', verbose_name="Toifa")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE,
                              db_index=True, verbose_name="Holati")

    registered_on = models.DateField(auto_now_add=True, verbose_name="Ro'yxatga olingan")
    expires_on = models.DateField(null=True, blank=True, verbose_name="Amal qilish muddati")

    # --- HEMIS'siz (qo'lda qo'shilgan) a'zo uchun ---
    full_name = models.CharField(max_length=200, blank=True, verbose_name="F.I.Sh.")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    email = models.EmailField(blank=True, verbose_name="Elektron pochta")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    address = models.TextField(blank=True, verbose_name="Manzil")
    photo = models.ImageField(upload_to='patron_photos/', null=True, blank=True,
                              verbose_name="Rasm")

    # --- Xizmat maydonlari ---
    note = models.TextField(blank=True, verbose_name="Ichki izoh")
    block_reason = models.CharField(max_length=255, blank=True, verbose_name="Bloklash sababi")
    blocked_until = models.DateField(null=True, blank=True, verbose_name="Blok muddati")
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name="Garov (so'm)")

    # --- Denormalizatsiya (tez ko'rsatish uchun; servislar yangilaydi) ---
    active_loans_count = models.PositiveIntegerField(default=0, verbose_name="Faol ijaralar")
    overdue_count = models.PositiveIntegerField(default=0, verbose_name="Kechikkanlar")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  verbose_name="Qarz qoldig'i (so'm)")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "Kutubxona a'zosi"
        verbose_name_plural = "Kutubxona a'zolari"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'category']),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.card_number})"

    # --- Ko'rsatish ---
    @property
    def display_name(self):
        if self.user_id and self.user:
            return self.user.get_full_name()
        return self.full_name or self.card_number

    @property
    def contact_phone(self):
        return (self.user.phone if self.user_id and self.user else None) or self.phone

    @property
    def contact_email(self):
        return (self.user.email if self.user_id and self.user else None) or self.email

    # --- Holat ---
    @property
    def is_expired(self):
        from django.utils.timezone import now
        return bool(self.expires_on and self.expires_on < now().date())

    @property
    def is_blocked(self):
        from django.utils.timezone import now
        if self.status == self.Status.BLOCKED:
            return not self.blocked_until or self.blocked_until >= now().date()
        return False

    def borrow_blocks(self):
        """Yangi ijaraga to'sqinlik qiluvchi sabablar: [(kod, matn), ...]."""
        from .roles import is_library_staff
        if self.user_id and is_library_staff(self.user):
            return [('staff', "Kutubxona xodimi hisobi bilan kitob olinmaydi.")]
        blocks = []
        if self.status == self.Status.CLOSED:
            blocks.append(('closed', "A'zolik yopilgan."))
        if self.is_blocked:
            blocks.append(('blocked', self.block_reason or "A'zo bloklangan."))
        if self.is_expired:
            blocks.append(('expired', "A'zolik muddati tugagan."))
        limit = self.category.loan_limit
        if limit and self.active_loans_count >= limit:
            blocks.append(('limit', f"Ijara limiti to'lgan ({limit} ta)."))
        block_at = self.category.debt_block_amount
        if block_at and self.balance >= block_at:
            blocks.append(('debt', f"Qarz chegaradan oshgan ({self.balance} so'm)."))
        return blocks

    def can_borrow(self):
        """(bo'ladimi, sabab) — ijara berishdan oldin tekshiriladi."""
        blocks = self.borrow_blocks()
        return (False, blocks[0][1]) if blocks else (True, "")
