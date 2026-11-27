"""
Fond tuzilmasi: filial/bo'lim, nusxa turi va javon.

Bu uchta ma'lumotnoma (reference) kutubxona ishining skeleti:

  Library       — fond qayerda turadi (asosiy fond, abonement, o'quv zali, kafedra)
  ItemType      — nusxa qanday (darslik, badiiy, nodir, davriy, faqat zalda...)
  ShelfLocation — javon/raf, o'quvchiga ko'rsatiladigan yo'nalish bilan

P3'da sirkulyatsiya qoidalari matritsasi aynan shu uch o'q bo'yicha quriladi:
(filial x a'zo toifasi x nusxa turi).
"""
from django.db import models


class Library(models.Model):
    """Filial / bo'lim. Kichik kutubxonada bitta yozuv bo'ladi ("Asosiy fond")."""

    class Kind(models.TextChoices):
        MAIN = 'MAIN', "Asosiy fond"
        SUBSCRIPTION = 'SUBSCRIPTION', "Abonement"
        READING_ROOM = 'READING_ROOM', "O'quv zali"
        DEPARTMENT = 'DEPARTMENT', "Kafedra kutubxonasi"
        STORAGE = 'STORAGE', "Saqlash joyi (arxiv)"

    code = models.CharField(max_length=20, unique=True, verbose_name="Kod")
    name = models.CharField(max_length=120, verbose_name="Nomi")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.MAIN,
                            verbose_name="Turi")

    address = models.CharField(max_length=255, blank=True, verbose_name="Manzil")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefon")
    opening_hours = models.CharField(max_length=120, blank=True, verbose_name="Ish vaqti")

    is_active = models.BooleanField(default=True, verbose_name="Faol")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")

    class Meta:
        verbose_name = "Filial / bo'lim"
        verbose_name_plural = "Filiallar va bo'limlar"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @classmethod
    def default(cls):
        """Standart filial — yangi nusxalar shunga tushadi."""
        return cls.objects.filter(is_active=True).order_by('order', 'id').first()


class ItemType(models.Model):
    """Nusxa turi — ijara qoidasining asosiy o'qi."""

    code = models.CharField(max_length=20, unique=True, verbose_name="Kod")
    name = models.CharField(max_length=80, verbose_name="Nomi")
    description = models.CharField(max_length=255, blank=True, verbose_name="Izoh")

    is_loanable = models.BooleanField(
        default=True, verbose_name="Uyga beriladi",
        help_text="O'chirilsa — bu turdagi nusxa faqat zalda ishlatiladi.")
    default_loan_days = models.PositiveIntegerField(
        default=0, verbose_name="Ijara muddati (kun)",
        help_text="0 — a'zo toifasidagi muddat ishlatiladi.")
    replacement_cost_default = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Standart qiymat (so'm)",
        help_text="Yo'qotilganda undiriladigan taxminiy summa.")

    icon = models.CharField(max_length=40, blank=True, verbose_name="Ikonka")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Nusxa turi"
        verbose_name_plural = "Nusxa turlari"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @classmethod
    def default(cls):
        return cls.objects.filter(is_active=True).order_by('order', 'id').first()


class ShelfLocation(models.Model):
    """Javon/raf — "kitob qayerda turibdi" degan savolga javob."""

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name='shelves',
                                verbose_name="Filial")
    code = models.CharField(max_length=30, verbose_name="Kod")
    name = models.CharField(max_length=120, blank=True, verbose_name="Nomi")

    floor = models.CharField(max_length=20, blank=True, verbose_name="Qavat")
    zone = models.CharField(max_length=40, blank=True, verbose_name="Zona")
    navigation_hint = models.CharField(
        max_length=200, blank=True, verbose_name="Yo'nalish",
        help_text="O'quvchiga ko'rsatiladi: \"2-qavat, B-zona, 14-javon\".")

    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Javon"
        verbose_name_plural = "Javonlar"
        ordering = ['library', 'code']
        constraints = [
            models.UniqueConstraint(fields=['library', 'code'], name='uniq_shelf_code_per_library'),
        ]

    def __str__(self):
        return f"{self.code} — {self.library.name}" if self.library_id else self.code

    @property
    def directions(self):
        """O'quvchiga ko'rsatiladigan to'liq yo'nalish."""
        if self.navigation_hint:
            return self.navigation_hint
        parts = [p for p in (self.floor, self.zone, self.name or self.code) if p]
        return ", ".join(parts)
