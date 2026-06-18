from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
