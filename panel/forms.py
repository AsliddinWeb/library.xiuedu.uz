from django import forms
from django.utils.text import slugify

from book_app.models import Author, Book, Genre

INPUT = ("w-full rounded-lg border border-navy-200 bg-paper px-3.5 py-2.5 text-sm text-navy-900 "
         "transition placeholder:text-navy-400 focus:border-gold-400 focus:ring-2 "
         "focus:ring-gold-200 focus:outline-none")
FILE = ("block w-full text-sm text-navy-600 file:mr-4 file:rounded-lg file:border-0 "
        "file:bg-navy-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white "
        "hover:file:bg-navy-800")


class PanelBookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 'authors', 'category', 'published_year', 'isbn', 'language',
            'page_count', 'description', 'cover_image', 'electronic_version',
            'audio_version', 'reading_mode', 'download_allowed', 'is_active',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Kitob nomi'}),
            'authors': forms.CheckboxSelectMultiple(),
            'category': forms.Select(attrs={'class': INPUT}),
            'published_year': forms.NumberInput(attrs={'class': INPUT, 'placeholder': '2021'}),
            'isbn': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'ISBN'}),
            'language': forms.TextInput(attrs={'class': INPUT}),
            'page_count': forms.NumberInput(attrs={'class': INPUT, 'placeholder': 'Sahifalar'}),
            'description': forms.Textarea(attrs={'class': INPUT, 'rows': 4, 'placeholder': 'Qisqacha tavsif'}),
            'cover_image': forms.ClearableFileInput(attrs={'class': FILE}),
            'electronic_version': forms.ClearableFileInput(attrs={'class': FILE}),
            'audio_version': forms.ClearableFileInput(attrs={'class': FILE}),
            'reading_mode': forms.Select(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Genre.objects.all()
        self.fields['authors'].queryset = Author.objects.all()
        self.fields['authors'].required = False
        self.fields['category'].empty_label = "— Katalog tanlang —"

    def save(self, commit=True):
        book = super().save(commit=False)
        if commit:
            book.save()
            self.save_m2m()
            if not book.slug:
                book.slug = f"{slugify(book.title)[:280] or 'kitob'}-{book.pk}"
                book.save(update_fields=['slug'])
        return book
