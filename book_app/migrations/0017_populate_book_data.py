from django.db import migrations
from django.utils.text import slugify


def populate(apps, schema_editor):
    Book = apps.get_model('book_app', 'Book')
    Copy = apps.get_model('book_app', 'Copy')

    for book in Book.objects.all():
        changed = False

        # published_date (matn) -> published_year (int)
        if not book.published_year and book.published_date:
            digits = ''.join(ch for ch in str(book.published_date) if ch.isdigit())[:4]
            if len(digits) == 4:
                book.published_year = int(digits)
                changed = True

        # slug (title + pk — unikal)
        if not book.slug:
            base = slugify(book.title)[:280] or 'kitob'
            book.slug = f"{base}-{book.pk}"
            changed = True

        # reading_mode — mavjud fayl/nusxalarga qarab
        has_digital = bool(book.electronic_version) or bool(book.audio_version)
        has_physical = Copy.objects.filter(book=book).exists()
        if has_digital and has_physical:
            mode = 'BOTH'
        elif has_digital:
            mode = 'DIGITAL'
        else:
            mode = 'PHYSICAL'
        if book.reading_mode != mode:
            book.reading_mode = mode
            changed = True

        if changed:
            book.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('book_app', '0016_alter_author_options_alter_genre_options_and_more'),
    ]
    operations = [migrations.RunPython(populate, noop)]
