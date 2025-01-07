from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.db import models
from .managers import UserManager

# User Model
class User(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        STUDENT = 'STUDENT', _('Talaba')
        EMPLOYE = 'EMPLOYE', _('Xodim')

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
    gender = models.CharField(max_length=10, choices=[("Erkak", "Erkak"), ("Ayol", "Ayol")], null=True, blank=True, verbose_name="Jinsi")

    # passport_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="Passport raqami")
    # jshshir = models.CharField(max_length=50, null=True, blank=True, verbose_name="JSHSHIR")

    country = models.CharField(max_length=100, null=True, blank=True, verbose_name="Davlat")
    province = models.CharField(max_length=100, null=True, blank=True, verbose_name="Viloyat")
    district = models.CharField(max_length=100, null=True, blank=True, verbose_name="Tuman")
    address = models.TextField(null=True, blank=True, verbose_name="Manzil")

    is_active = models.BooleanField(default=True, verbose_name="Faol")
    is_staff = models.BooleanField(default=False, verbose_name="Hodim")

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.second_name.upper()} {self.first_name.upper()}"

# Employe Profile Model
class EmployeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employe_profile", verbose_name="Foydalanuvchi")

    department = models.TextField(null=True, blank=True, verbose_name="Bo'lim")
    position = models.TextField(null=True, blank=True, verbose_name="Lavozim")

    roles = models.ManyToManyField('Role', blank=True, related_name="employe_profiles", verbose_name="Xodim rollari")
    current_role = models.ForeignKey('Role', on_delete=models.SET_NULL, blank=True, null=True, related_name="current_employes", verbose_name="Hozirgi rol")

    class Meta:
        verbose_name = "Hodim"
        verbose_name_plural = "Hodimlar"

    def __str__(self):
        return self.user.username


# Student Profile Model
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile", verbose_name="Foydalanuvchi")

    faculty = models.CharField(max_length=100, null=True, blank=True, verbose_name="Fakultet")
    group = models.CharField(max_length=100, null=True, blank=True, verbose_name="Guruh")
    level = models.CharField(max_length=100, null=True, blank=True, verbose_name="Bosqich")
    semester = models.CharField(max_length=100, null=True, blank=True, verbose_name="Semestr")

    education_form = models.CharField(max_length=100, null=True, blank=True, verbose_name="Ta'lim shakli")
    education_type = models.CharField(max_length=100, null=True, blank=True, verbose_name="Ta'lim turi")
    payment_form = models.CharField(max_length=100, null=True, blank=True, verbose_name="To'lov shakli")

    class Meta:
        verbose_name = "Talaba"
        verbose_name_plural = "Talabalar"

    def __str__(self):
        return self.user.username

# Role Model
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Rol nomi")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Rollar"

    def __str__(self):
        return self.name