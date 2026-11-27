"""
Audit — tizimdagi har bir muhim harakatning izi va davriy vazifalarning holati.

`ActionLog` — kim, nimani, qachon o'zgartirdi (moliya/fond/a'zo bo'yicha mas'uliyat uchun).
`JobRun`    — rejalashtirilgan vazifaning har bir ishga tushishi (monitoring uchun).
"""
from django.db import models


class ActionLog(models.Model):
    """O'zgarmas (append-only) audit yozuvi. Qo'lda tahrirlanmaydi."""

    class Action(models.TextChoices):
        # Autentifikatsiya
        LOGIN = 'LOGIN', "Kirish"
        LOGOUT = 'LOGOUT', "Chiqish"
        # Sirkulyatsiya
        CHECKOUT = 'CHECKOUT', "Kitob berildi"
        CHECKIN = 'CHECKIN', "Kitob qaytarildi"
        RENEW = 'RENEW', "Muddat uzaytirildi"
        HOLD_PLACE = 'HOLD_PLACE', "Navbatga yozildi"
        HOLD_CANCEL = 'HOLD_CANCEL', "Navbat bekor qilindi"
        OVERRIDE = 'OVERRIDE', "Qoida buzib bajarildi"
        # Pul
        FINE_CHARGE = 'FINE_CHARGE', "Jarima yozildi"
        PAYMENT = 'PAYMENT', "To'lov qabul qilindi"
        WAIVE = 'WAIVE', "Qarz kechirildi"
        # Fond
        BIBLIO_CREATE = 'BIBLIO_CREATE', "Yozuv yaratildi"
        BIBLIO_EDIT = 'BIBLIO_EDIT', "Yozuv tahrirlandi"
        BIBLIO_DELETE = 'BIBLIO_DELETE', "Yozuv o'chirildi"
        ITEM_CREATE = 'ITEM_CREATE', "Nusxa qo'shildi"
        ITEM_EDIT = 'ITEM_EDIT', "Nusxa tahrirlandi"
        ITEM_WITHDRAW = 'ITEM_WITHDRAW', "Nusxa hisobdan chiqarildi"
        # A'zolar
        PATRON_CREATE = 'PATRON_CREATE', "A'zo yaratildi"
        PATRON_EDIT = 'PATRON_EDIT', "A'zo tahrirlandi"
        PATRON_BLOCK = 'PATRON_BLOCK', "A'zo bloklandi"
        # Tizim
        IMPORT = 'IMPORT', "Import"
        EXPORT = 'EXPORT', "Eksport"
        SETTINGS = 'SETTINGS', "Sozlama o'zgartirildi"
        MODERATE = 'MODERATE', "Moderatsiya"
        JOB = 'JOB', "Davriy vazifa"
        OTHER = 'OTHER', "Boshqa"

    actor = models.ForeignKey('user_app.User', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='action_logs', verbose_name="Kim")
    actor_label = models.CharField(max_length=150, blank=True, verbose_name="Kim (yozuv)")

    action = models.CharField(max_length=20, choices=Action.choices, default=Action.OTHER,
                              verbose_name="Harakat")

    object_type = models.CharField(max_length=60, blank=True, verbose_name="Ob'ekt turi")
    object_id = models.CharField(max_length=40, blank=True, verbose_name="Ob'ekt ID")
    object_repr = models.CharField(max_length=300, blank=True, verbose_name="Ob'ekt")

    changes = models.JSONField(default=dict, blank=True, verbose_name="O'zgarishlar")
    note = models.CharField(max_length=300, blank=True, verbose_name="Izoh")

    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    user_agent = models.CharField(max_length=300, blank=True, verbose_name="Brauzer")
    path = models.CharField(max_length=300, blank=True, verbose_name="Manzil")

    at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Vaqt")

    class Meta:
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit jurnali"
        ordering = ['-at']
        indexes = [
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['actor', '-at']),
            models.Index(fields=['action', '-at']),
        ]

    def __str__(self):
        return f"[{self.at:%Y-%m-%d %H:%M}] {self.actor_label or '—'}: {self.get_action_display()}"


class JobRun(models.Model):
    """Rejalashtirilgan vazifaning bir marta ishga tushishi."""

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', "Bajarilmoqda"
        SUCCESS = 'SUCCESS', "Muvaffaqiyatli"
        FAILED = 'FAILED', "Xato"

    name = models.CharField(max_length=60, db_index=True, verbose_name="Vazifa")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING,
                              db_index=True, verbose_name="Holati")

    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Boshlandi")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugadi")
    duration_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name="Davomiylik (ms)")

    stats = models.JSONField(default=dict, blank=True, verbose_name="Natija")
    message = models.CharField(max_length=300, blank=True, verbose_name="Xabar")
    error = models.TextField(blank=True, verbose_name="Xato matni")

    class Meta:
        verbose_name = "Vazifa ishga tushishi"
        verbose_name_plural = "Vazifalar jurnali"
        ordering = ['-started_at']
        indexes = [models.Index(fields=['name', '-started_at'])]

    def __str__(self):
        return f"{self.name} — {self.get_status_display()} ({self.started_at:%Y-%m-%d %H:%M})"
