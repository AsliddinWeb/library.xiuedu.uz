from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.db import models
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
        verbose_name = "Hodim"
        verbose_name_plural = "Hodimlar"

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
    name = models.CharField(max_length=50, unique=True, verbose_name="Rol nomi")
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="Izoh")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Rollar"
        ordering = ['name']

    def __str__(self):
        return self.name