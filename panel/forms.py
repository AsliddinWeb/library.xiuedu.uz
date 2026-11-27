"""
Xodim paneli formalari.

P2-B dan boshlab kitob formasi — to'laqonli **kataloglash formasi**: bibliografik
maydonlar bo'limlarga ajratilgan, nashriyot/turkum/mavzular matn sifatida kiritiladi
va kerak bo'lsa avtomatik yaratiladi (kataloglovchi avval ma'lumotnomaga kirib,
keyin qaytib kelmasligi uchun).
"""
from django import forms
from django.utils.text import slugify

from book_app.models import Author, Book, Genre, Item, Publisher, Series, Subject
from holdings.models import ItemType, Library, ShelfLocation

__all__ = [
    'PanelBookForm', 'PanelGenreForm', 'PanelAuthorForm', 'PanelSettingsForm',
    'PanelItemForm', 'ItemBulkActionForm', 'PanelLibraryForm', 'PanelItemTypeForm',
    'PanelShelfForm',
]

# Eski (v2) sahifalar uchun klasslar — yangi formalar `.input`/`.select` ishlatadi
INPUT = ("w-full rounded-lg border border-navy-200 bg-paper px-3.5 py-2.5 text-sm text-navy-900 "
         "transition placeholder:text-navy-400 focus:border-gold-400 focus:ring-2 "
         "focus:ring-gold-200 focus:outline-none")
FILE = ("block w-full text-sm text-navy-600 file:mr-4 file:rounded-lg file:border-0 "
        "file:bg-navy-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white "
        "hover:file:bg-navy-800")


def _style(form, file_class=FILE):
    """Formaning barcha maydoniga dizayn tizimi klasslarini qo'yadi."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault('class', 'checkbox')
        elif isinstance(widget, forms.CheckboxSelectMultiple):
            continue
        elif isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
            widget.attrs.setdefault('class', file_class)
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault('class', 'select')
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('class', 'textarea')
        else:
            widget.attrs.setdefault('class', 'input')


class PanelBookForm(forms.ModelForm):
    """Kataloglash formasi.

    Qo'shimcha (modelda yo'q) maydonlar:
      publisher_name / series_name — matn; mavjud bo'lmasa yangi yozuv yaratiladi
      subjects_text                — vergul bilan ajratilgan mavzular
    """

    publisher_name = forms.CharField(
        required=False, label="Nashriyot",
        help_text="Ro'yxatda bo'lmasa — yangi nashriyot yaratiladi.")
    series_name = forms.CharField(
        required=False, label="Turkum",
        help_text="Masalan: Jahon adabiyoti durdonalari.")
    subjects_text = forms.CharField(
        required=False, label="Mavzular",
        help_text="Vergul bilan ajrating: dasturlash, algoritmlar, Python.")
    # Modelda 13 belgi saqlanadi, lekin kataloglovchi defis bilan yozadi
    # ("978-9943-00-000-1") — shuning uchun forma kengroq qabul qiladi.
    isbn = forms.CharField(required=False, max_length=20, label="ISBN",
                           help_text="Defis bilan yozsa ham bo'ladi.")

    class Meta:
        model = Book
        fields = [
            # Asosiy
            'record_type', 'title', 'subtitle', 'parallel_title', 'category',
            # Nashr
            'published_year', 'place_of_publication', 'edition_statement',
            'series_number', 'page_count',
            # Identifikatorlar va klassifikatsiya
            'isbn', 'issn', 'doi', 'udc', 'bbk', 'author_sign',
            # Mazmun
            'description', 'annotation', 'contents_note', 'target_audience',
            'language', 'original_language',
            # Universitet
            'faculty', 'department', 'is_textbook',
            # Fayllar
            'cover_image', 'electronic_version', 'audio_version',
            'reading_mode', 'download_allowed',
            # Holat
            'authors', 'is_active',
        ]
        widgets = {
            'authors': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(attrs={'rows': 3}),
            'annotation': forms.Textarea(attrs={'rows': 3}),
            'contents_note': forms.Textarea(attrs={'rows': 3}),
        }

    #: Shablon bo'limlarga shu xarita bo'yicha ajratadi
    SECTIONS = [
        ("Asosiy", ['record_type', 'title', 'subtitle', 'parallel_title', 'category',
                    'authors']),
        ("Nashr", ['publisher_name', 'place_of_publication', 'published_year',
                   'edition_statement', 'series_name', 'series_number', 'page_count']),
        ("Identifikatorlar va klassifikatsiya",
         ['isbn', 'issn', 'doi', 'udc', 'bbk', 'author_sign']),
        ("Mazmun", ['subjects_text', 'description', 'annotation', 'contents_note',
                    'target_audience', 'language', 'original_language']),
        ("Universitet", ['faculty', 'department', 'is_textbook']),
        ("Fayllar va o'qish", ['cover_image', 'electronic_version', 'audio_version',
                               'reading_mode', 'download_allowed']),
        ("Holat", ['is_active']),
    ]

    #: Bir ustunga sig'maydigan (keng) maydonlar
    WIDE_FIELDS = {'title', 'subtitle', 'parallel_title', 'authors', 'subjects_text',
                   'description', 'annotation', 'contents_note', 'cover_image',
                   'electronic_version', 'audio_version'}

    def sections(self):
        """Shablon uchun: [{title, fields: [{field, wide}]}] ko'rinishida."""
        for title, names in self.SECTIONS:
            fields = [{'field': self[name], 'wide': name in self.WIDE_FIELDS}
                      for name in names if name in self.fields]
            if fields:
                yield {'title': title, 'fields': fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Genre.objects.all()
        self.fields['category'].empty_label = "— Katalog tanlang —"
        self.fields['authors'].queryset = Author.objects.all()
        self.fields['authors'].required = False
        self.fields['authors'].label = "Mualliflar"
        self.fields['authors'].help_text = (
            "Muharrir/tarjimon kabi boshqa rollar kitob sahifasidan qo'shiladi.")

        if self.instance.pk:
            self.fields['publisher_name'].initial = (
                self.instance.publisher.name if self.instance.publisher_id else '')
            self.fields['series_name'].initial = (
                self.instance.series.name if self.instance.series_id else '')
            self.fields['subjects_text'].initial = ", ".join(
                self.instance.subjects.values_list('name', flat=True))

        _style(self)

    def clean_isbn(self):
        """ISBN faqat raqam va defis; 10/13 belgi."""
        isbn = (self.cleaned_data.get('isbn') or '').strip()
        if not isbn:
            return isbn
        digits = isbn.replace('-', '').replace(' ', '')
        if not digits.isdigit() or len(digits) not in (10, 13):
            raise forms.ValidationError("ISBN 10 yoki 13 raqamdan iborat bo'lishi kerak.")
        return digits

    def save(self, commit=True):
        book = super().save(commit=False)

        # Nashriyot / turkum — matndan yozuvga
        publisher_name = (self.cleaned_data.get('publisher_name') or '').strip()
        book.publisher = (Publisher.objects.get_or_create(name=publisher_name)[0]
                          if publisher_name else None)

        series_name = (self.cleaned_data.get('series_name') or '').strip()
        book.series = (Series.objects.get_or_create(name=series_name)[0]
                       if series_name else None)

        # Chaqiruv raqami uchun qulay bo'lsin: UDK bo'lsa, muallif belgisi avtomatik
        if book.udc and not book.author_sign:
            first_author = self.cleaned_data.get('authors')
            if first_author:
                name = list(first_author)[0].full_name
                book.author_sign = f"{name[:1].upper()}-{len(name) * 7 % 90 + 10}"

        if commit:
            book.save()
            self.save_m2m()
            self._sync_subjects(book)
            if not book.slug:
                book.slug = f"{slugify(book.title)[:280] or 'kitob'}-{book.pk}"
                book.save(update_fields=['slug'])
        return book

    def _sync_subjects(self, book):
        raw = (self.cleaned_data.get('subjects_text') or '').strip()
        names = [part.strip() for part in raw.split(',') if part.strip()]
        subjects = [Subject.objects.get_or_create(name=name, kind=Subject.Kind.SUBJECT)[0]
                    for name in names]
        book.subjects.set(subjects)


class PanelItemForm(forms.ModelForm):
    """Nusxani tahrirlash: joylashuv, tur, narx, jismoniy holat.

    `status` bu yerda o'zgartirilmaydi — u uchun alohida amal bor
    (`book_app.services.change_item_status`), chunki har o'zgarish jurnalga yoziladi.
    """

    class Meta:
        model = Item
        fields = ['barcode', 'inventory_number', 'call_number', 'item_type', 'library',
                  'shelf_location', 'volume_number', 'copy_number', 'condition',
                  'condition_note', 'acquired_on', 'acquisition_source', 'price',
                  'replacement_price', 'not_for_loan_reason']
        widgets = {
            'acquired_on': forms.DateInput(attrs={'type': 'date'}),
            'condition_note': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item_type'].queryset = ItemType.objects.filter(is_active=True)
        self.fields['library'].queryset = Library.objects.filter(is_active=True)
        self.fields['shelf_location'].queryset = (
            ShelfLocation.objects.filter(is_active=True).select_related('library'))
        _style(self)


class ItemBulkActionForm(forms.Form):
    """Bir nechta nusxaga bir vaqtda amal (holat yoki ko'chirish)."""

    ACTIONS = [
        ('status', "Holatni o'zgartirish"),
        ('move', "Boshqa javonga ko'chirish"),
    ]

    action = forms.ChoiceField(choices=ACTIONS, widget=forms.Select(attrs={'class': 'select'}))
    status = forms.ChoiceField(choices=Item.Status.choices, required=False,
                               widget=forms.Select(attrs={'class': 'select'}))
    shelf_location = forms.ModelChoiceField(
        queryset=ShelfLocation.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'select'}))
    reason = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'input'}))
    items = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shelf_location'].queryset = (
            ShelfLocation.objects.filter(is_active=True).select_related('library'))

    def clean(self):
        data = super().clean()
        if data.get('action') == 'status' and not data.get('status'):
            self.add_error('status', "Holatni tanlang.")
        if data.get('action') == 'move' and not data.get('shelf_location'):
            self.add_error('shelf_location', "Javonni tanlang.")
        return data

    def item_ids(self):
        return [int(value) for value in (self.cleaned_data.get('items') or '').split(',')
                if value.strip().isdigit()]


# --------------------------------------------------------------------------
#  Fond tuzilmasi ma'lumotnomalari
# --------------------------------------------------------------------------

class PanelLibraryForm(forms.ModelForm):
    class Meta:
        model = Library
        fields = ['code', 'name', 'kind', 'address', 'phone', 'opening_hours',
                  'order', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class PanelItemTypeForm(forms.ModelForm):
    class Meta:
        model = ItemType
        fields = ['code', 'name', 'description', 'is_loanable', 'default_loan_days',
                  'replacement_cost_default', 'order', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class PanelShelfForm(forms.ModelForm):
    class Meta:
        model = ShelfLocation
        fields = ['library', 'code', 'name', 'floor', 'zone', 'navigation_hint', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['library'].queryset = Library.objects.filter(is_active=True)
        _style(self)


class PanelGenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ['name', 'icon', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Katalog nomi'}),
            'icon': forms.Textarea(attrs={'class': INPUT, 'rows': 2,
                                          'placeholder': 'Ikonka (SVG yoki emoji) — ixtiyoriy'}),
            'order': forms.NumberInput(attrs={'class': INPUT, 'placeholder': '0'}),
        }


class PanelAuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['full_name', 'birth_year', 'death_year', 'nationality', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Ism Familiya'}),
            'birth_year': forms.NumberInput(attrs={'class': INPUT, 'placeholder': '1894'}),
            'death_year': forms.NumberInput(attrs={'class': INPUT, 'placeholder': '1938'}),
            'nationality': forms.TextInput(attrs={'class': INPUT, 'placeholder': "O'zbek"}),
            'bio': forms.Textarea(attrs={'class': INPUT, 'rows': 4,
                                         'placeholder': 'Qisqacha tavsif'}),
        }


class PanelSettingsForm(forms.ModelForm):
    class Meta:
        from circulation.models import LibrarySettings
        model = LibrarySettings
        fields = ['rental_days', 'reservation_hold_days', 'fine_per_day', 'max_active_rentals']
        widgets = {
            'rental_days': forms.NumberInput(attrs={'class': INPUT}),
            'reservation_hold_days': forms.NumberInput(attrs={'class': INPUT}),
            'fine_per_day': forms.NumberInput(attrs={'class': INPUT}),
            'max_active_rentals': forms.NumberInput(attrs={'class': INPUT}),
        }
