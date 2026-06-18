from django import forms

from .models import Author, Book, Copy, Genre, Rental


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['full_name', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ism Familiya'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Qisqacha tavsif', 'rows': 4}),
        }


class GenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Katalog nomi'}),
        }


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 'authors', 'category', 'published_year', 'description', 'audio_version',
            'electronic_version', 'page_count', 'cover_image', 'language', 'isbn',
            'reading_mode', 'download_allowed', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kitob nomi'}),
            'authors': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'published_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Yil (masalan 2021)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Qisqacha tavsif', 'rows': 4}),
            'audio_version': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'electronic_version': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'page_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sahifalar soni'}),
            'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'language': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Til'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ISBN'}),
        }


class CopyForm(forms.ModelForm):
    class Meta:
        model = Copy
        fields = ['book', 'inventory_number', 'is_available']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-control'}),
            'inventory_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inventar raqami'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RentalForm(forms.ModelForm):
    class Meta:
        model = Rental
        fields = ['copy', 'student', 'borrowed_date', 'return_date']
        widgets = {
            'copy': forms.Select(attrs={'class': 'form-control'}),
            'student': forms.Select(attrs={'class': 'form-control'}),
            'borrowed_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
