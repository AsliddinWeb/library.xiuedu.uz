from django import forms
from .models import Author, Genre, Book, Copy, Rental

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
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Janr nomi'}),
        }


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 'authors', 'category', 'published_date', 'description', 'audio_version',
            'electronic_version', 'page_count', 'cover_image', 'language', 'isbn'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kitob nomi'}),
            'authors': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'published_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
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
