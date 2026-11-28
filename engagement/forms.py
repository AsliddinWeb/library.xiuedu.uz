from django import forms

from . import services
from .models import Shelf


class ShelfForm(forms.ModelForm):
    """Ro'yxat yaratish/tahrirlash. Ko'rinadigan maydonlar huquqqa qarab o'zgaradi."""

    class Meta:
        model = Shelf
        fields = ['name', 'description', 'visibility', 'is_official']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': "Masalan: Kurs ishi uchun"}),
            'description': forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'visibility': forms.Select(attrs={'class': 'select'}),
            'is_official': forms.CheckboxInput(attrs={'class': 'checkbox'}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Tahrirlashda egasi o'zgarmaydi — nom takrorlanishi egasi bo'yicha tekshiriladi
        self.owner = self.instance.owner if self.instance.pk else user
        if not services.can_publish_shelf(user):
            del self.fields['visibility']
        if not services.is_curator(user):
            del self.fields['is_official']

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        clash = Shelf.objects.filter(owner=self.owner, name__iexact=name)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Bunday nomli ro'yxat bor.")
        return name

    def clean(self):
        data = super().clean()
        if data.get('is_official') and data.get('visibility') == Shelf.Visibility.PRIVATE:
            self.add_error('visibility', "Kutubxona tanlovi shaxsiy bo'la olmaydi.")
        return data

    def save(self, commit=True):
        shelf = super().save(commit=False)
        # E'lon qilish huquqi yo'q (yoki yo'qolgan) bo'lsa, ro'yxat shaxsiy bo'lib qoladi
        if 'visibility' not in self.fields:
            shelf.visibility = Shelf.Visibility.PRIVATE
            shelf.is_official = False
        if commit:
            shelf.save()
        return shelf
