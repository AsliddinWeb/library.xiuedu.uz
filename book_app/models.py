from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q

from user_app.models import StudentProfile


class Author(models.Model):
    """Muallif (va boshqa hissadorlar: muharrir, tarjimon...).

    `name_variants` — kirill/lotin/asl yozuvdagi variantlar. O'zbek fondida bir
    muallif uch xil yozilishi mumkin ("Qodiriy", "Кодирий", "Kodiriy"), qidiruv
    shu ro'yxat bo'yicha ham topadi.
    """
    full_name = models.CharField(max_length=200, db_index=True, verbose_name="Ism Familiya")
    normalized_name = models.CharField(max_length=200, blank=True, db_index=True,
                                       verbose_name="Normallashgan nom")
    name_variants = models.JSONField(default=list, blank=True, verbose_name="Nom variantlari",
                                     help_text="Masalan: [\"Кодирий\", \"Kodiriy\"]")

    birth_year = models.IntegerField(null=True, blank=True, verbose_name="Tug'ilgan yili")
    death_year = models.IntegerField(null=True, blank=True, verbose_name="Vafot yili")
    nationality = models.CharField(max_length=60, blank=True, verbose_name="Millati / davlati")
    photo = models.ImageField(upload_to='author_photos/', null=True, blank=True,
                              verbose_name="Rasmi")

    bio = models.TextField(verbose_name="Qisqacha tavsif", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")

    class Meta:
        verbose_name = "Muallif"
        verbose_name_plural = "Mualliflar"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name

    @property
    def life_years(self):
        if not (self.birth_year or self.death_year):
            return ""
        return f"{self.birth_year or '?'}–{self.death_year or ''}".rstrip('–')


class Publisher(models.Model):
    """Nashriyot."""
    name = models.CharField(max_length=200, unique=True, verbose_name="Nomi")
    city = models.CharField(max_length=100, blank=True, verbose_name="Shahar")
    website = models.URLField(blank=True, verbose_name="Veb-sayt")

    class Meta:
        verbose_name = "Nashriyot"
        verbose_name_plural = "Nashriyotlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Series(models.Model):
    """Turkum / seriya ("Jahon adabiyoti durdonalari", "O'quv qo'llanmalar")."""
    name = models.CharField(max_length=200, unique=True, verbose_name="Nomi")
    issn = models.CharField(max_length=20, blank=True, verbose_name="ISSN")
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='series', verbose_name="Nashriyot")

    class Meta:
        verbose_name = "Turkum"
        verbose_name_plural = "Turkumlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """Mavzu / kalit so'z (ierarxik). Fasetli qidiruvning asosi."""

    class Kind(models.TextChoices):
        SUBJECT = 'SUBJECT', "Mavzu rubrikasi"
        KEYWORD = 'KEYWORD', "Kalit so'z"
        UDC = 'UDC', "UDK bo'limi"
        BBK = 'BBK', "BBK bo'limi"

    name = models.CharField(max_length=160, verbose_name="Nomi")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SUBJECT,
                            verbose_name="Turi")
    code = models.CharField(max_length=40, blank=True, verbose_name="Kod (UDK/BBK)")
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name="Yuqori mavzu")
    books_count = models.PositiveIntegerField(default=0, verbose_name="Kitoblar soni")

    class Meta:
        verbose_name = "Mavzu"
        verbose_name_plural = "Mavzular"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['name', 'kind'], name='uniq_subject_name_kind'),
        ]

    def __str__(self):
        return f"{self.code} {self.name}".strip()


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
    """Bibliografik yozuv.

    Nomi tarixiy sabablarga ko'ra `Book` bo'lib qoldi (kod va shablonlarda 100+ joyda
    ishlatiladi), lekin mazmunan bu — har qanday nashr turi uchun yozuv: monografiya,
    darslik, dissertatsiya, davriy nashr, AV yoki elektron resurs (`record_type`).
    """

    class ReadingMode(models.TextChoices):
        PHYSICAL = 'PHYSICAL', "Jismoniy"
        DIGITAL = 'DIGITAL', "Raqamli"
        BOTH = 'BOTH', "Ikkalasi"

    class RecordType(models.TextChoices):
        MONOGRAPH = 'MONOGRAPH', "Monografiya / kitob"
        TEXTBOOK = 'TEXTBOOK', "Darslik"
        MANUAL = 'MANUAL', "O'quv qo'llanma"
        DISSERTATION = 'DISSERTATION', "Dissertatsiya / avtoreferat"
        SERIAL = 'SERIAL', "Davriy nashr"
        AV = 'AV', "Audio / video"
        ELECTRONIC = 'ELECTRONIC', "Elektron resurs"
        ARTICLE = 'ARTICLE', "Maqola"

    record_type = models.CharField(max_length=14, choices=RecordType.choices,
                                   default=RecordType.MONOGRAPH, db_index=True,
                                   verbose_name="Yozuv turi")

    title = models.CharField(max_length=500, verbose_name="Kitob nomi")
    subtitle = models.CharField(max_length=500, blank=True, verbose_name="Ikkinchi sarlavha")
    parallel_title = models.CharField(max_length=500, blank=True,
                                      verbose_name="Parallel sarlavha",
                                      help_text="Boshqa tildagi sarlavha.")
    slug = models.SlugField(max_length=300, unique=True, null=True, blank=True, verbose_name="Slug")

    authors = models.ManyToManyField(Author, through='Contributor', verbose_name="Mualliflar")
    category = models.ForeignKey(Genre, verbose_name="Katalog", on_delete=models.PROTECT)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='books',
                                      verbose_name="Mavzular")

    published_year = models.PositiveIntegerField(verbose_name="Chop etilgan yili", null=True, blank=True)
    # Eski matnli maydon (deprecated — published_year ishlatiladi)
    published_date = models.CharField(max_length=255, verbose_name="Chop etilgan sana (eski)", null=True, blank=True)

    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='books', verbose_name="Nashriyot")
    place_of_publication = models.CharField(max_length=120, blank=True, verbose_name="Nashr joyi")
    edition_statement = models.CharField(max_length=120, blank=True, verbose_name="Nashr ma'lumoti",
                                         help_text="Masalan: 3-nashr, qayta ishlangan.")
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='books', verbose_name="Turkum")
    series_number = models.CharField(max_length=40, blank=True, verbose_name="Turkumdagi raqami")

    description = models.TextField(verbose_name="Qisqacha tavsif", blank=True, null=True)

    audio_version = models.FileField(upload_to="audio_books/", verbose_name="Audio versiyasi", blank=True, null=True)
    electronic_version = models.FileField(upload_to="ebooks/", verbose_name="Elektron versiyasi", blank=True, null=True)

    page_count = models.PositiveIntegerField(verbose_name="Sahifalar soni", blank=True, null=True)
    cover_image = models.ImageField(upload_to="book_covers/", verbose_name="Muqova rasmi", blank=True, null=True)

    language = models.CharField(max_length=50, verbose_name="Til", default="O'zbekcha")
    original_language = models.CharField(max_length=50, blank=True, verbose_name="Asl tili")

    isbn = models.CharField(max_length=13, verbose_name="ISBN", blank=True, null=True)
    issn = models.CharField(max_length=20, blank=True, verbose_name="ISSN")
    doi = models.CharField(max_length=120, blank=True, verbose_name="DOI")

    # --- Klassifikatsiya (javondagi o'rin shu yerdan kelib chiqadi) ---
    udc = models.CharField(max_length=40, blank=True, db_index=True, verbose_name="UDK")
    bbk = models.CharField(max_length=40, blank=True, verbose_name="BBK")
    author_sign = models.CharField(max_length=20, blank=True, verbose_name="Muallif belgisi")

    # --- Mazmun ---
    annotation = models.TextField(blank=True, verbose_name="Annotatsiya")
    contents_note = models.TextField(blank=True, verbose_name="Mundarija")
    target_audience = models.CharField(max_length=160, blank=True, verbose_name="Kimga mo'ljallangan")

    # --- Universitet bog'lanishi (hisobotlar uchun juda muhim) ---
    faculty = models.CharField(max_length=160, blank=True, db_index=True, verbose_name="Fakultet")
    department = models.CharField(max_length=160, blank=True, verbose_name="Kafedra")
    is_textbook = models.BooleanField(default=False, db_index=True, verbose_name="Darslik/qo'llanma")

    reading_mode = models.CharField(max_length=10, choices=ReadingMode.choices,
                                    default=ReadingMode.PHYSICAL, verbose_name="Foydalanish turi")
    download_allowed = models.BooleanField(default=False, verbose_name="Yuklab olishga ruxsat")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Aktivmi?")

    view_count = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Ko'rishlar soni")
    loan_count = models.PositiveIntegerField(default=0, verbose_name="Ijaraga berilgan (jami)")
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, verbose_name="O'rtacha reyting")
    rating_count = models.PositiveIntegerField(default=0, verbose_name="Baholar soni")

    # Fond ko'rsatkichlari (servislar yangilaydi — har sahifada COUNT qilinmaydi)
    items_count = models.PositiveIntegerField(default=0, verbose_name="Nusxalar soni")
    available_count = models.PositiveIntegerField(default=0, verbose_name="Mavjud nusxalar")

    # --- Import va qidiruv ---
    marc_raw = models.TextField(blank=True, verbose_name="MARC yozuvi (import)",
                                help_text="Z39.50/MARC import qilinganda asl yozuv saqlanadi.")
    search_text = models.TextField(
        blank=True, verbose_name="Qidiruv matni",
        help_text="Kirill va lotin yozuv bir ko'rinishga keltirilgan matn "
                  "(sarlavha, mualliflar, mavzular, nashriyot). Avtomatik to'ladi.")
    search_title = models.TextField(
        blank=True, verbose_name="Qidiruv: sarlavha",
        help_text="Faqat sarlavhalar (normallashgan) — sarlavhada mos kelgan "
                  "kitob natijalarda yuqoriroq turishi uchun.")
    search_vector = SearchVectorField(
        null=True, blank=True, editable=False, verbose_name="Qidiruv vektori")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Kitob yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Kitob yangilangan sana")

    class Meta:
        verbose_name = "Kitob"
        verbose_name_plural = "Kitoblar"
        ordering = ['-id']
        indexes = [
            # To'liq matnli qidiruv (so'z bo'yicha, reyting bilan)
            GinIndex(fields=['search_vector'], name='book_search_vector_gin'),
            # Trigram — xato yozilgan so'zni ham topadi ("algaritm" -> "Algoritmlar")
            GinIndex(name='book_search_text_trgm', fields=['search_text'],
                     opclasses=['gin_trgm_ops']),
            GinIndex(name='book_search_title_trgm', fields=['search_title'],
                     opclasses=['gin_trgm_ops']),
        ]

    def __str__(self):
        return self.title

    def copy_count(self):
        """Mavjud nusxalar soni (denormalizatsiya maydonidan — tez)."""
        return self.available_count

    @property
    def contributors_by_role(self):
        """Hissadorlarni rol bo'yicha guruhlab qaytaradi (kitob sahifasi uchun)."""
        grouped = {}
        for contributor in self.contributor_set.select_related('author').all():
            grouped.setdefault(contributor.get_role_display(), []).append(contributor.author)
        return grouped


class Contributor(models.Model):
    """Kitob <-> muallif bog'lanishi, ROL bilan.

    Oddiy M2M "kim yozgan" degan savolga javob bera olmaydi: bir yozuvda muallif,
    muharrir, tarjimon va ilmiy rahbar bo'lishi mumkin. Shu model ularni ajratadi
    va tartibini saqlaydi (1-muallif, 2-muallif...).
    """

    class Role(models.TextChoices):
        AUTHOR = 'AUTHOR', "Muallif"
        CO_AUTHOR = 'CO_AUTHOR', "Hammuallif"
        EDITOR = 'EDITOR', "Muharrir"
        TRANSLATOR = 'TRANSLATOR', "Tarjimon"
        COMPILER = 'COMPILER', "Tuzuvchi"
        ILLUSTRATOR = 'ILLUSTRATOR', "Rassom"
        SUPERVISOR = 'SUPERVISOR', "Ilmiy rahbar"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Kitob")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, verbose_name="Shaxs")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.AUTHOR,
                            verbose_name="Roli")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Tartib")

    class Meta:
        verbose_name = "Hissador"
        verbose_name_plural = "Hissadorlar"
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['book', 'author', 'role'],
                                    name='uniq_contributor_role'),
        ]

    def __str__(self):
        return f"{self.author.full_name} — {self.get_role_display()}"


class Item(models.Model):
    """Fonddagi aniq NUSXA (ex `Copy`).

    Kutubxona hisobi aynan shu modelda yuritiladi: shtrix-kod, inventar raqami,
    qaysi filialda va qaysi javonda turibdi, holati, narxi, qachon qabul qilingan.
    Inventarizatsiya, chiqim akti va sirkulyatsiya — hammasi shu yozuvga tayanadi.
    """

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', "Mavjud"
        ON_LOAN = 'ON_LOAN', "Ijarada"
        ON_HOLD_SHELF = 'ON_HOLD_SHELF', "Ushlab turilgan"
        IN_TRANSIT = 'IN_TRANSIT', "Yo'lda"
        IN_PROCESSING = 'IN_PROCESSING', "Qayta ishlashda"
        DAMAGED = 'DAMAGED', "Shikastlangan"
        LOST = 'LOST', "Yo'qolgan"
        WITHDRAWN = 'WITHDRAWN', "Hisobdan chiqarilgan"
        NOT_FOR_LOAN = 'NOT_FOR_LOAN', "Faqat zalda"

    #: Shu holatlarda nusxa ijaraga berilishi mumkin
    LOANABLE_STATUSES = (Status.AVAILABLE,)

    class Condition(models.TextChoices):
        NEW = 'NEW', "Yangi"
        GOOD = 'GOOD', "Yaxshi"
        WORN = 'WORN', "Eskirgan"
        DAMAGED = 'DAMAGED', "Shikastlangan"

    class Source(models.TextChoices):
        PURCHASE = 'PURCHASE', "Sotib olingan"
        GIFT = 'GIFT', "Sovg'a"
        EXCHANGE = 'EXCHANGE', "Ayirboshlash"
        REPLACEMENT = 'REPLACEMENT', "O'rniga topshirilgan"
        OWN_PUBLICATION = 'OWN_PUBLICATION', "Universitet nashri"
        OTHER = 'OTHER', "Boshqa"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Kitob")

    # --- Identifikatsiya ---
    barcode = models.CharField(max_length=32, unique=True, null=True, blank=True, db_index=True,
                               verbose_name="Shtrix-kod")
    inventory_number = models.CharField(max_length=50, verbose_name="Inventar raqami")
    call_number = models.CharField(max_length=80, blank=True, verbose_name="Chaqiruv raqami",
                                   help_text="UDK + muallif belgisi — javondagi o'rin.")

    # --- Joylashuv va tur ---
    item_type = models.ForeignKey('holdings.ItemType', on_delete=models.PROTECT, null=True,
                                  blank=True, related_name='items', verbose_name="Nusxa turi")
    library = models.ForeignKey('holdings.Library', on_delete=models.PROTECT, null=True,
                                blank=True, related_name='items', verbose_name="Filial")
    shelf_location = models.ForeignKey('holdings.ShelfLocation', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='items',
                                       verbose_name="Javon")

    # --- Holat ---
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.AVAILABLE,
                              db_index=True, verbose_name="Holati")
    not_for_loan_reason = models.CharField(max_length=160, blank=True,
                                           verbose_name="Berilmaslik sababi")
    #: `status` ning soddalashtirilgan ko'rinishi — eski kod va tez filtrlar uchun
    is_available = models.BooleanField(default=True, db_index=True, verbose_name="Mavjudmi")

    # --- Qabul va moliya ---
    acquired_on = models.DateField(null=True, blank=True, verbose_name="Qabul sanasi")
    acquisition_source = models.CharField(max_length=16, choices=Source.choices,
                                          default=Source.PURCHASE, verbose_name="Manbasi")
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                verbose_name="Narxi (so'm)")
    replacement_price = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            verbose_name="O'rnini qoplash narxi")

    # --- Fizik holat ---
    condition = models.CharField(max_length=8, choices=Condition.choices, default=Condition.GOOD,
                                 verbose_name="Jismoniy holati")
    condition_note = models.CharField(max_length=200, blank=True, verbose_name="Holat izohi")
    volume_number = models.CharField(max_length=40, blank=True, verbose_name="Jild")
    copy_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Nusxa raqami")

    # --- Hisob ---
    last_seen_at = models.DateField(null=True, blank=True, verbose_name="Oxirgi ko'rilgan",
                                    help_text="Inventarizatsiyada skanerlangan sana.")
    loan_count = models.PositiveIntegerField(default=0, verbose_name="Necha marta berilgan")
    withdrawn_on = models.DateField(null=True, blank=True, verbose_name="Chiqarilgan sana")

    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, null=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "Nusxa"
        verbose_name_plural = "Nusxalar"
        ordering = ['book', 'inventory_number']
        constraints = [
            models.UniqueConstraint(fields=['book', 'inventory_number'],
                                    name='uniq_inventory_per_book'),
        ]
        indexes = [
            models.Index(fields=['book', 'status']),
            models.Index(fields=['library', 'status']),
        ]

    def __str__(self):
        return f"{self.book.title} — {self.barcode or self.inventory_number}"

    def save(self, *args, **kwargs):
        # `is_available` doim `status` bilan mos bo'lsin (eski kod shunga tayanadi)
        self.is_available = self.status in self.LOANABLE_STATUSES
        super().save(*args, **kwargs)

    @property
    def location_text(self):
        """O'quvchiga ko'rsatiladigan joylashuv: filial + javon yo'nalishi."""
        parts = []
        if self.library_id:
            parts.append(self.library.name)
        if self.shelf_location_id:
            parts.append(self.shelf_location.directions)
        elif self.call_number:
            parts.append(self.call_number)
        return " · ".join(parts) or "—"

    @property
    def is_loanable(self):
        if self.status not in self.LOANABLE_STATUSES:
            return False
        if self.item_type_id and not self.item_type.is_loanable:
            return False
        return True


class ItemStatusLog(models.Model):
    """Nusxa holatining har bir o'zgarishi — moliyaviy mas'uliyat uchun."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='status_logs',
                             verbose_name="Nusxa")
    from_status = models.CharField(max_length=14, blank=True, verbose_name="Eski holat")
    to_status = models.CharField(max_length=14, verbose_name="Yangi holat")
    reason = models.CharField(max_length=200, blank=True, verbose_name="Sabab")
    document_no = models.CharField(max_length=60, blank=True, verbose_name="Hujjat raqami")
    changed_by = models.ForeignKey('user_app.User', on_delete=models.SET_NULL, null=True,
                                   blank=True, verbose_name="Kim o'zgartirdi")
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Vaqti")

    class Meta:
        verbose_name = "Nusxa holati jurnali"
        verbose_name_plural = "Nusxa holatlari jurnali"
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.item_id}: {self.from_status} -> {self.to_status}"


class Rental(models.Model):
    """Ijara (P3'da `circulation.Loan`ga aylanadi).

    Qarz oluvchi — `patron`. `student` maydoni eski kod/hisobotlar uchun vaqtincha
    to'ldirilib boriladi (faqat talabalar uchun) va P3'da olib tashlanadi.
    """
    copy = models.ForeignKey(Item, on_delete=models.CASCADE, verbose_name="Nusxa")
    patron = models.ForeignKey('user_app.Patron', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='loans', verbose_name="Kutubxona a'zosi")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, null=True, blank=True,
                                verbose_name="O'quvchi (eski)")

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
        indexes = [
            models.Index(fields=['patron', 'return_date']),
        ]

    def __str__(self):
        return f"{self.copy.book.title} — {self.borrower_name}"

    # --- Qarz oluvchi (patron birlamchi, student — eski yo'l) ---
    @property
    def borrower(self):
        return self.patron

    @property
    def borrower_name(self):
        if self.patron_id:
            return self.patron.display_name
        if self.student_id:
            return self.student.user.get_full_name()
        return "—"

    @property
    def is_active(self):
        return self.return_date is None

    @property
    def is_overdue(self):
        from django.utils.timezone import now
        return self.return_date is None and self.due_date is not None and self.due_date < now().date()
