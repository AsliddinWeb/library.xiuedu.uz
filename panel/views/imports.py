"""
Kitob import qilish: Excel (CSV) fayldan yoki tashqi API manzilidan.
"""
import os
from io import BytesIO

import requests as http
from django.contrib import messages
from django.core.files import File
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from audit.models import ActionLog
from audit.services import log_action
from book_app.models import Author, Book, Genre
from user_app.permissions import Perms, has_perm, require_perm

from .. import importers
from ..exports import csv_response

__all__ = ['import_books', 'import_preview', 'import_confirm']

SESSION_KEY = 'book_csv_import'
PREVIEW_ROWS = 200


def _import_page(request, **extra):
    return render(request, 'panel/import.html', {
        'active': 'import', 'page_title': 'Kitoblarni import qilish',
        'columns': importers.template_header(), 'max_rows': importers.MAX_ROWS, **extra})


@require_POST
@require_perm(Perms.CATALOG_IMPORT)
def import_preview(request):
    """CSV faylni o'qib, nima bo'lishini ko'rsatadi — bazaga hali yozilmaydi."""
    upload = request.FILES.get('file')
    if upload is None:
        return _import_page(request, error="Faylni tanlang.")
    try:
        rows = importers.parse(upload)
    except importers.ImportProblem as problem:
        return _import_page(request, error=str(problem))

    request.session[SESSION_KEY] = {'name': upload.name, 'rows': rows}
    broken = [row for row in rows if row['errors']]
    return _import_page(
        request,
        preview=(broken + [row for row in rows if not row['errors']])[:PREVIEW_ROWS],
        file_name=upload.name,
        counts={
            'total': len(rows),
            'new': sum(1 for row in rows if not row['errors'] and not row['existing']),
            'existing': sum(1 for row in rows if row['existing']),
            'broken': len(broken),
        })


@require_POST
@require_perm(Perms.CATALOG_IMPORT)
def import_confirm(request):
    data = request.session.pop(SESSION_KEY, None)
    if not data:
        messages.error(request, "Import ma'lumoti topilmadi — faylni qayta yuklang.")
        return redirect('panel:import_books')

    summary = importers.apply(
        data['rows'], user=request.user,
        add_copies_to_existing=bool(request.POST.get('add_copies')),
        with_items=has_perm(request.user, Perms.ITEMS_MANAGE))
    text = (f"{summary['books']} ta kitob, {summary['copies']} ta nusxa qo'shildi. "
            f"Tashlab ketilgan qator: {summary['skipped']}.")
    log_action(ActionLog.Action.IMPORT, actor=request.user, note=f"{data['name']}: {text}")
    messages.success(request, text)
    return redirect('panel:books')


@require_perm(Perms.CATALOG_IMPORT)
def import_books(request):
    """Import sahifasi (GET) va tashqi API'dan ommaviy yuklash (POST, JSON javob)."""
    if request.method != 'POST':
        if request.GET.get('template') == '1':
            return csv_response(request, 'kitob-shabloni', importers.template_header(),
                                [importers.EXAMPLE])
        return _import_page(request)

    url = request.POST.get('url', '').strip()
    if not url:
        return JsonResponse({'error': 'URL kiriting.'}, status=400)
    try:
        resp = http.get(url, timeout=20)
        resp.raise_for_status()
        results = resp.json().get('results', [])
    except Exception as e:
        return JsonResponse({'error': f"Manbaga ulanib bo'lmadi: {e}"}, status=400)

    created = 0
    for item in results:
        try:
            year_raw = str(item.get('year') or '')
            published_year = int(year_raw) if year_raw.isdigit() else None
            author, _ = Author.objects.get_or_create(full_name=item.get('author', {}).get('name') or "Noma'lum")
            category, _ = Genre.objects.get_or_create(name=item.get('category', {}).get('title') or 'Boshqa')
            book = Book.objects.create(
                title=item.get('title') or 'Nomsiz',
                published_year=published_year,
                description=item.get('description') or '',
                page_count=item.get('page_count') or None,
                category=category,
                reading_mode=Book.ReadingMode.DIGITAL,
            )
            book.authors.add(author)
            book.slug = f"{slugify(book.title)[:280] or 'kitob'}-{book.pk}"
            book.save(update_fields=['slug'])

            cover = item.get('photo')
            if cover:
                try:
                    ir = http.get(cover, timeout=15)
                    if ir.ok:
                        book.cover_image.save(os.path.basename(cover) or 'cover.jpg', File(BytesIO(ir.content)), save=True)
                except Exception:
                    pass
            src = item.get('source')
            if src:
                try:
                    br = http.get(src, timeout=30)
                    if br.ok:
                        book.electronic_version.save(os.path.basename(src) or 'book.pdf', File(BytesIO(br.content)), save=True)
                except Exception:
                    pass
            created += 1
        except Exception:
            continue

    return JsonResponse({'success': f"{created} ta kitob muvaffaqiyatli qo'shildi."})
