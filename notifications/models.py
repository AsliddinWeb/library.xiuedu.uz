from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    class Type(models.TextChoices):
        REQUEST_APPROVED = 'REQUEST_APPROVED', _('So\'rov tasdiqlandi')
        REQUEST_REJECTED = 'REQUEST_REJECTED', _('So\'rov rad etildi')
        RESERVATION_AVAILABLE = 'RESERVATION_AVAILABLE', _('Navbat bo\'shadi')
        DUE_SOON = 'DUE_SOON', _('Muddat yaqin')
        OVERDUE = 'OVERDUE', _('Muddat o\'tdi')
        FINE = 'FINE', _('Jarima')
        REVIEW_APPROVED = 'REVIEW_APPROVED', _('Sharh tasdiqlandi')
        GENERAL = 'GENERAL', _('Umumiy')

    user = models.ForeignKey('user_app.User', on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=24, choices=Type.choices, default=Type.GENERAL, verbose_name="Turi")
    title = models.CharField(max_length=200, verbose_name="Sarlavha")
    message = models.CharField(max_length=400, blank=True, verbose_name="Matn")
    link = models.CharField(max_length=300, blank=True, verbose_name="Havola")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="O'qilgan")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read'])]

    def __str__(self):
        return f"{self.user.username} — {self.title}"
