from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from book_app.translit import to_latin


class Review(models.Model):
    """Kitobga baho va sharh (moderatsiya bilan)."""
    user = models.ForeignKey('user_app.User', on_delete=models.CASCADE, related_name='reviews')
    book = models.ForeignKey('book_app.Book', on_delete=models.CASCADE, related_name='reviews')

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Baho")
    text = models.TextField(blank=True, verbose_name="Sharh")
    is_approved = models.BooleanField(default=False, db_index=True, verbose_name="Tasdiqlangan")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sharh"
        verbose_name_plural = "Sharhlar"
        ordering = ['-created_at']
        unique_together = ('user', 'book')  # bitta foydalanuvchi — bitta sharh

    def __str__(self):
        return f"{self.user.username} — {self.book.title} ({self.rating}★)"


class Favorite(models.Model):
    """Foydalanuvchining sevimli kitobi."""
    user = models.ForeignKey('user_app.User', on_delete=models.CASCADE, related_name='favorites')
    book = models.ForeignKey('book_app.Book', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sevimli"
        verbose_name_plural = "Sevimlilar"
        ordering = ['-created_at']
        unique_together = ('user', 'book')

    def __str__(self):
        return f"{self.user.username} — {self.book.title}"


class Shelf(models.Model):
    """Nomlangan kitob ro'yxati (Koha "Lists" uslubida).

    O'quvchi uchun — "Kurs ishi uchun", "Keyin o'qiyman" kabi shaxsiy to'plam.
    Kutubxona uchun — hammaga ko'rinadigan tavsiya to'plami (`is_official`).
    """

    class Visibility(models.TextChoices):
        PRIVATE = 'PRIVATE', "Faqat o'zimga"
        PUBLIC = 'PUBLIC', "Hammaga ochiq"
        STAFF = 'STAFF', "Faqat xodimlarga"

    owner = models.ForeignKey('user_app.User', on_delete=models.CASCADE,
                              related_name='shelves', verbose_name="Egasi")
    name = models.CharField(max_length=120, verbose_name="Nomi")
    slug = models.SlugField(max_length=160, unique=True, editable=False)
    description = models.CharField(max_length=300, blank=True, verbose_name="Izoh")
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE,
        verbose_name="Kimga ko'rinadi")
    is_official = models.BooleanField(
        default=False, verbose_name="Kutubxona tanlovi",
        help_text="Kutubxona tavsiya qiladigan to'plam — ro'yxatlar sahifasida yuqorida turadi.")
    books = models.ManyToManyField('book_app.Book', through='ShelfItem',
                                   related_name='shelves', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ro'yxat"
        verbose_name_plural = "Ro'yxatlar"
        ordering = ['-is_official', '-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='uniq_shelf_name_per_owner'),
        ]
        indexes = [models.Index(fields=['visibility', 'is_official'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(to_latin(self.name))[:120] or 'royxat'
            suffix = get_random_string(6, 'abcdefghijkmnpqrstuvwxyz23456789')
            self.slug = f'{base}-{suffix}'
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('engagement:shelf_detail', args=[self.slug])


class ShelfItem(models.Model):
    """Ro'yxatdagi bitta kitob."""
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey('book_app.Book', on_delete=models.CASCADE,
                             related_name='shelf_items')
    note = models.CharField(max_length=255, blank=True, verbose_name="Izoh")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ro'yxatdagi kitob"
        verbose_name_plural = "Ro'yxatdagi kitoblar"
        ordering = ['order', 'added_at']
        constraints = [
            models.UniqueConstraint(fields=['shelf', 'book'], name='uniq_book_per_shelf'),
        ]

    def __str__(self):
        return f"{self.shelf.name}: {self.book.title}"
