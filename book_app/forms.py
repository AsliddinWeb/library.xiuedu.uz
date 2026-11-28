from django import forms

from user_app.models import PatronCategory, User

from .models import Author, Book, CourseReserve, Genre, Item, Rental


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['full_name', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ism va familiya'}),
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
        model = Item
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


class CourseReserveForm(forms.ModelForm):
    """Fan ro'yxati. O'qituvchi faqat o'zi uchun ochadi, kutubxonachi — istalgan
    o'qituvchi nomiga."""

    class Meta:
        model = CourseReserve
        fields = ['course_name', 'course_code', 'teacher', 'faculty', 'department',
                  'semester', 'description', 'is_active']
        widgets = {
            'course_name': forms.TextInput(attrs={'class': 'input', 'placeholder': "Masalan: Iqtisodiyot nazariyasi"}),
            'course_code': forms.TextInput(attrs={'class': 'input'}),
            'teacher': forms.Select(attrs={'class': 'select'}),
            'faculty': forms.TextInput(attrs={'class': 'input', 'list': 'faculty-list', 'autocomplete': 'off'}),
            'department': forms.TextInput(attrs={'class': 'input'}),
            'semester': forms.NumberInput(attrs={'class': 'input', 'min': 1, 'max': 12}),
            'description': forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'checkbox'}),
        }
        help_texts = {
            'faculty': "Bo'sh qoldirilsa — barcha fakultetlar uchun.",
            'semester': "Bo'sh qoldirilsa — barcha semestrlar uchun.",
        }

    def __init__(self, *args, user, curator, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if curator:
            teachers = User.objects.filter(patron__category__code=PatronCategory.Code.TEACHER)
            if self.instance.pk and self.instance.teacher_id:
                teachers = teachers | User.objects.filter(pk=self.instance.teacher_id)
            self.fields['teacher'].queryset = teachers.distinct().order_by('second_name', 'first_name')
            self.fields['teacher'].label_from_instance = lambda u: u.get_full_name()
            self.fields['teacher'].required = False
        else:
            del self.fields['teacher']

    def save(self, commit=True):
        reserve = super().save(commit=False)
        if not reserve.pk:
            reserve.created_by = self.user
            if 'teacher' not in self.fields:
                reserve.teacher = self.user
        if commit:
            reserve.save()
        return reserve
