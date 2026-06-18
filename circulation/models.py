from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class LibrarySettings(models.Model):
    """Kutubxona sozlamalari (yagona yozuv — singleton)."""
    rental_days = models.PositiveIntegerField(
        default=14, verbose_name="Ijara muddati (kun)")
    reservation_hold_days = models.PositiveIntegerField(
        default=2, verbose_name="Navbat ushlab turish (kun)")
    fine_per_day = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Kuniga jarima (so'm)")
    max_active_rentals = models.PositiveIntegerField(
        default=5, verbose_name="Bir vaqtda maksimal ijara")

    class Meta:
        verbose_name = "Kutubxona sozlamasi"
        verbose_name_plural = "Kutubxona sozlamalari"

    def __str__(self):
        return "Kutubxona sozlamalari"

    def save(self, *args, **kwargs):
        self.pk = 1  # har doim bitta yozuv
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RentalRequest(models.Model):
    """Talabaning jismoniy kitobni ijaraga olish so'rovi."""
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Kutilmoqda')
        APPROVED = 'APPROVED', _('Tasdiqlangan')
        REJECTED = 'REJECTED', _('Rad etilgan')
        CANCELLED = 'CANCELLED', _('Bekor qilingan')

    student = models.ForeignKey(
        'user_app.StudentProfile', on_delete=models.CASCADE,
        related_name='rental_requests', verbose_name="Talaba")
    book = models.ForeignKey(
        'book_app.Book', on_delete=models.CASCADE,
        related_name='rental_requests', verbose_name="Kitob")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING,
        db_index=True, verbose_name="Holati")

    rental = models.ForeignKey(
        'book_app.Rental', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='request', verbose_name="Ijara")
    note = models.CharField(max_length=255, blank=True, verbose_name="Izoh")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="So'ralgan sana")
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name="Hal qilingan sana")
    decided_by = models.ForeignKey(
        'user_app.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='decided_requests', verbose_name="Kim hal qildi")

    class Meta:
        verbose_name = "Ijara so'rovi"
        verbose_name_plural = "Ijara so'rovlari"
        ordering = ['-created_at']
        constraints = [
            # Bir talaba bir kitobga faqat bitta ochiq (PENDING) so'rov yubora oladi
            models.UniqueConstraint(fields=['student', 'book'], condition=Q(status='PENDING'),
                                    name='uniq_pending_request_per_student_book'),
        ]

    def __str__(self):
        return f"{self.book.title} — {self.student.user.username} ({self.get_status_display()})"


class Reservation(models.Model):
    """Band kitob uchun navbat."""
    class Status(models.TextChoices):
        WAITING = 'WAITING', _('Navbatda')
        AVAILABLE = 'AVAILABLE', _("Bo'shadi (ushlab turilmoqda)")
        FULFILLED = 'FULFILLED', _('Bajarildi')
        EXPIRED = 'EXPIRED', _("Muddati o'tdi")
        CANCELLED = 'CANCELLED', _('Bekor qilingan')

    student = models.ForeignKey(
        'user_app.StudentProfile', on_delete=models.CASCADE,
        related_name='reservations', verbose_name="Talaba")
    book = models.ForeignKey(
        'book_app.Book', on_delete=models.CASCADE,
        related_name='reservations', verbose_name="Kitob")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.WAITING,
        db_index=True, verbose_name="Holati")

    hold_until = models.DateTimeField(
        null=True, blank=True, verbose_name="Ushlab turish muddati")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Navbatga yozilgan sana")

    class Meta:
        verbose_name = "Navbat"
        verbose_name_plural = "Navbatlar"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['book', 'status']),
        ]

    def __str__(self):
        return f"{self.book.title} — {self.student.user.username} ({self.get_status_display()})"


class Fine(models.Model):
    """Kechikkan ijara uchun jarima (faqat hisob/qo'lda belgilash)."""
    rental = models.OneToOneField(
        'book_app.Rental', on_delete=models.CASCADE,
        related_name='fine', verbose_name="Ijara")
    student = models.ForeignKey(
        'user_app.StudentProfile', on_delete=models.CASCADE,
        related_name='fines', verbose_name="Talaba")

    days_overdue = models.PositiveIntegerField(default=0, verbose_name="Kechikkan kunlar")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Summa (so'm)")
    is_paid = models.BooleanField(default=False, verbose_name="To'langanmi")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="To'langan sana")

    class Meta:
        verbose_name = "Jarima"
        verbose_name_plural = "Jarimalar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.user.username} — {self.amount} so'm"
