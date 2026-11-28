"""
arm-admin kitoblarini kutubxona import qiladigan faylga chiqaradi.

arm-admin papkasida, uning o'z muhitida ishga tushiriladi:

    cd ~/projects/arm-admin.xiuedu.uz
    venv/bin/python manage.py shell -c "import os; exec(open(os.path.expanduser(
        '~/projects/library.xiuedu.uz/bin/arm_export.py'), encoding='utf-8').read(), {})"

Faqat o'qiydi: arm-admin bazasi va fayllari o'zgarmaydi. «Yashirilgan» kitoblar
(HiddenBook) chiqarilmaydi. Boshqa joyga yozish: ARM_EXPORT_OUT=/yo'l/fayl.json

Eslatma: bu skript eski Django/Python bilan ham ishlashi uchun sodda yozilgan.
"""
import json
import os

from bookapp.models import Book

target = os.environ.get('ARM_EXPORT_OUT') or os.path.expanduser(
    '~/projects/library.xiuedu.uz/var/arm-books.json')

rows = []
for book in Book.objects.select_related('author', 'category').order_by('pk').iterator():
    rows.append({
        'id': book.pk,
        'title': book.title,
        'author': {'name': book.author.name},
        'category': {'title': book.category.title},
        'year': book.year,
        'description': book.description,
        # Fayllar media papkasiga nisbatan yo'l ko'rinishida
        'source': book.source.name if book.source else '',
        'photo': book.photo.name if book.photo else '',
        'updated_at': book.updated_at.isoformat() if book.updated_at else '',
    })

folder = os.path.dirname(target)
if folder and not os.path.isdir(folder):
    os.makedirs(folder)
with open(target + '.tmp', 'w', encoding='utf-8') as handle:
    json.dump({'count': len(rows), 'results': rows}, handle, ensure_ascii=False)
os.replace(target + '.tmp', target)

print('Chiqarildi: %d ta kitob -> %s' % (len(rows), target))
