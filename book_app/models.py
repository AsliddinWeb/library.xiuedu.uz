from django.db import models
from django.db.models import Q

from user_app.models import StudentProfile


class Author(models.Model):
    full_name = models.CharField(max_length=200, db_index=True, verbose_name="Ism Familiya")

    bio = models.TextField(verbose_name="Qisqacha tavsif", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")

    class Meta:
        verbose_name = "Muallif"
        verbose_name_plural = "Mualliflar"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class Genre(models.Model):
    name = models.CharField(max_length=100, verbose_name="Katalog nomi")
    icon = models.TextField(verbose_name="Ikonkasi", null=True, blank=True)
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    is_active = models.BooleanField(verbose_name="Aktivmi?", default=True)

    class Meta:
        verbose_name = "Katalog"
        verbose_name_plural = "Kataloglar"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def book_count(self):
        return self.book_set.all().count()


class Book(models.Model):
    class ReadingMode(models.TextChoices):
        PHYSICAL = 'PHYSICAL', "Jismoniy"
        DIGITAL = 'DIGITAL', "Raqamli"
        BOTH = 'BOTH', "Ikkalasi"

    title = models.CharField(max_length=500, verbose_name="Kitob nomi")
    slug = models.SlugField(max_length=300, unique=True, null=True, blank=True, verbose_name="Slug")

    authors = models.ManyToManyField(Author, verbose_name="Mualliflar")
    category = models.ForeignKey(Genre, verbose_name="Katalog", on_delete=models.PROTECT)

    published_year = models.PositiveIntegerField(verbose_name="Chop etilgan yili", null=True, blank=True)
    # Eski matnli maydon (deprecated — published_year ishlatiladi)
    published_date = models.CharField(max_length=255, verbose_name="Chop etilgan sana (eski)", null=True, blank=True)

    description = models.TextField(verbose_name="Qisqacha tavsif", blank=True, null=True)

    audio_version = models.FileField(upload_to="audio_books/", verbose_name="Audio versiyasi", blank=True, null=True)
    electronic_version = models.FileField(upload_to="ebooks/", verbose_name="Elektron versiyasi", blank=True, null=True)

    page_count = models.PositiveIntegerField(verbose_name="Sahifalar soni", blank=True, null=True)
    cover_image = models.ImageField(upload_to="book_covers/", verbose_name="Muqova rasmi", blank=True, null=True)

    language = models.CharField(max_length=50, verbose_name="Til", default="O'zbekcha")
    isbn = models.CharField(max_length=13, verbose_name="ISBN", blank=True, null=True)

    reading_mode = models.CharField(max_length=10, choices=ReadingMode.choices,
                                    default=ReadingMode.PHYSICAL, verbose_name="Foydalanish turi")
    download_allowed = models.BooleanField(default=False, verbose_name="Yuklab olishga ruxsat")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Aktivmi?")

    view_count = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Ko'rishlar soni")
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, verbose_name="O'rtacha reyting")
    rating_count = models.PositiveIntegerField(default=0, verbose_name="Baholar soni")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Kitob yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Kitob yangilangan sana")

    class Meta:
        verbose_name = "Kitob"
        verbose_name_plural = "Kitoblar"
        ordering = ['-id']

    def __str__(self):
        return self.title

    def copy_count(self):
        """Faqat mavjud (`is_available=True`) bo'lgan kitob nusxalarini qaytaradi."""
        return self.copy_set.filter(is_available=True).count()


class Copy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Kitob")
    inventory_number = models.CharField(max_length=50, verbose_name="Inventar raqami")
    is_available = models.BooleanField(default=True, db_index=True, verbose_name="Mavjudmi")

    class Meta:
        verbose_name = "Nusxa"
        verbose_name_plural = "Nusxalar"
        constraints = [
            models.UniqueConstraint(fields=['book', 'inventory_number'],
                                    name='uniq_inventory_per_book'),
        ]

    def __str__(self):
        return f"{self.book.title} - {self.inventory_number}"


class Rental(models.Model):
    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, verbose_name="Nusxa")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, verbose_name="O'quvchi")

    library_admin_checked = models.BooleanField(default=False, verbose_name="Kutubxonachi tasdiqladimi?")

    borrowed_date = models.DateField(verbose_name="Olgan sana", blank=True, null=True)
    due_date = models.DateField(verbose_name="Qaytarish muddati", blank=True, null=True, db_index=True)
    return_date = models.DateField(verbose_name="Qaytarilgan sana", blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kitob yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Kitob yangilangan sana")

    class Meta:
        verbose_name = "Ijara"
        verbose_name_plural = "Ijaralar"
        constraints = [
            # Bitta nusxa bir vaqtda faqat bitta faol (qaytarilmagan) ijarada
            models.UniqueConstraint(fields=['copy'], condition=Q(return_date__isnull=True),
                                    name='uniq_active_rental_per_copy'),
        ]

    def __str__(self):
        return f"{self.copy.book.title} ({self.student.user.first_name} {self.student.user.third_name})"

    @property
    def is_active(self):
        return self.return_date is None

    @property
    def is_overdue(self):
        from django.utils.timezone import now
        return self.return_date is None and self.due_date is not None and self.due_date < now().date()
