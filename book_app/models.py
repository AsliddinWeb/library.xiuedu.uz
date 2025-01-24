from django.db import models

from user_app.models import StudentProfile


class Author(models.Model):
    full_name = models.CharField(max_length=200, verbose_name="Ism Familiya")

    bio = models.TextField(verbose_name="Qisqacha tavsif", blank=True, null=True)

    class Meta:
        verbose_name = "Muallif"
        verbose_name_plural = "Mualliflar"

    def __str__(self):
        return self.full_name


class Genre(models.Model):
    name = models.CharField(max_length=100, verbose_name="Katalog nomi")
    icon = models.TextField(verbose_name="Ikonkasi", null=True, blank=True)

    class Meta:
        verbose_name = "Katalog"
        verbose_name_plural = "Kataloglar"

    def __str__(self):
        return self.name

    def book_count(self):
        return self.book_set.all().count()


class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="Kitob nomi")

    authors = models.ManyToManyField(Author, verbose_name="Mualliflar")
    # genres = models.ManyToManyField(Genre, verbose_name="Kataloglar")
    category = models.ForeignKey(Genre, verbose_name="Katalog", on_delete=models.PROTECT)

    published_date = models.CharField(max_length=255, verbose_name="Chop etilgan sana", null=True, blank=True, default="2020")

    description = models.TextField(verbose_name="Qisqacha tavsif", blank=True, null=True)

    audio_version = models.FileField(upload_to="audio_books/", verbose_name="Audio versiyasi", blank=True, null=True)
    electronic_version = models.FileField(upload_to="ebooks/", verbose_name="Elektron versiyasi", blank=True, null=True)

    page_count = models.PositiveIntegerField(verbose_name="Sahifalar soni", blank=True, null=True)
    cover_image = models.ImageField(upload_to="book_covers/", verbose_name="Muqova rasmi", blank=True, null=True)

    language = models.CharField(max_length=50, verbose_name="Til", default="O'zbekcha")
    isbn = models.CharField(max_length=13, verbose_name="ISBN", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kitob yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Kitob yangilangan sana")

    class Meta:
        verbose_name = "Kitob"
        verbose_name_plural = "Kitoblar"

    def __str__(self):
        return self.title

    def copy_count(self):
        """Faqat mavjud (`is_available=True`) bo'lgan kitob nusxalarini qaytaradi."""
        return self.copy_set.filter(is_available=True).count()


class Copy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Kitob")
    inventory_number = models.CharField(max_length=50, verbose_name="Inventar raqami")
    is_available = models.BooleanField(default=True, verbose_name="Mavjudmi")

    class Meta:
        verbose_name = "Nusxa"
        verbose_name_plural = "Nusxalar"

    def __str__(self):
        return f"{self.book.title} - {self.inventory_number}"


class Rental(models.Model):
    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, verbose_name="Nusxa")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, verbose_name="O'quvchi")

    library_admin_checked = models.BooleanField(default=False, verbose_name="Kutubxonachi tasdiqladimi?")

    borrowed_date = models.DateField(verbose_name="Olgan sana", blank=True, null=True)
    return_date = models.DateField(verbose_name="Qaytarish sanasi", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kitob yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Kitob yangilangan sana")

    class Meta:
        verbose_name = "Ijara"
        verbose_name_plural = "Ijaralar"

    def __str__(self):
        return f"{self.copy.book.title} ({self.student.user.first_name} {self.student.user.third_name})"
