from django.db import models


class ReadingProgress(models.Model):
    """Foydalanuvchining kitobdagi oxirgi joyi (PDF sahifa / audio soniya)."""
    class Mode(models.TextChoices):
        READ = 'READ', 'O\'qish'
        LISTEN = 'LISTEN', 'Tinglash'

    user = models.ForeignKey('user_app.User', on_delete=models.CASCADE, related_name='reading_progress')
    book = models.ForeignKey('book_app.Book', on_delete=models.CASCADE, related_name='reading_progress')
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.READ)

    position = models.FloatField(default=0, verbose_name="Joriy joy (sahifa yoki soniya)")
    percent = models.PositiveSmallIntegerField(default=0, verbose_name="Foiz")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "O'qish jarayoni"
        verbose_name_plural = "O'qish jarayonlari"
        unique_together = ('user', 'book', 'mode')

    def __str__(self):
        return f"{self.user.username} — {self.book.title} ({self.percent}%)"


class ReadingHistory(models.Model):
    """Kitob ochilgan vaqtlar tarixi (analitika uchun)."""
    user = models.ForeignKey('user_app.User', on_delete=models.CASCADE, related_name='reading_history')
    book = models.ForeignKey('book_app.Book', on_delete=models.CASCADE, related_name='reading_history')
    opened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "O'qish tarixi"
        verbose_name_plural = "O'qish tarixi"
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.user.username} — {self.book.title}"
