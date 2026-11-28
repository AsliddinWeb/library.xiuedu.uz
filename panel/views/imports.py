"""
Kitob import qilish: universitet kitoblar bazasidan (arm-admin) yoki Excel
(CSV) fayldan.
"""
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import ActionLog, JobRun
from audit.services import log_action
from book_app import arm_import
from book_app.models import Book, ExternalRecord
from book_app.remote import free_bytes
from core import background
from user_app.permissions import Perms, has_perm, require_perm

from .. import importers
from ..exports import csv_response

__all__ = ['import_books', 'import_preview', 'import_confirm',
           'arm_start', 'arm_stop', 'arm_status']

SESSION_KEY = 'book_csv_import'
PREVIEW_ROWS = 200

COUNTERS = (
    ('new', "Yangi kitob"), ('linked', "Katalogda bor"), ('updated', "Yangilandi"),
    ('same', "O'zgarmagan"), ('covers', "Muqova"), ('files', "PDF"),
    ('skipped', "O'tkazildi"), ('failed', "Xato"), ('cover_failed', "Olinmagan muqova"),
    ('file_failed', "Olinmagan PDF"),
)


def _status_context():
    background.close_stale(arm_import.JOB_NAME)
    runs = list(JobRun.objects.filter(name=arm_import.JOB_NAME)[:5])
    latest = runs[0] if runs else None
    context = {'runs': runs, 'latest': latest, 'running': False}
    if latest:
        stats = latest.stats
        total, done = stats.get('total') or 0, stats.get('done', 0)
        dry = bool(stats.get('dry'))
        counters = []
        for key, label in COUNTERS:
            value = stats.get(key, 0)
            if dry and key == 'new':
                label = "Qo'shiladi"
            if value or key in ('new', 'linked'):
                counters.append((key, label, value))
        context.update(
            running=latest.status == JobRun.Status.RUNNING,
            stopping=bool(stats.get('stop')), dry=dry,
            total=total, done=done,
            percent=min(100, round(done * 100 / total)) if total else 0,
            counters=counters, samples=stats.get('samples') or {},
            disk_full=stats.get('disk_full'))
    return context


def _export_info():
    """Serverdagi eksport fayli (bo'lsa) — manba sifatida ko'rsatiladi."""
    path = Path(settings.ARM_EXPORT_FILE)
    if not path.is_file():
        return None
    return {'made_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.get_current_timezone()),
            'media_found': Path(settings.ARM_MEDIA_ROOT).is_dir(),
            'media_root': settings.ARM_MEDIA_ROOT}


def _import_page(request, **extra):
    return render(request, 'panel/import.html', {
        'active': 'import', 'page_title': 'Kitoblarni import qilish',
        'columns': importers.template_header(), 'max_rows': importers.MAX_ROWS,
        'source_url': settings.ARM_API_URL,
        'export': _export_info(),
        'linked_total': ExternalRecord.objects.filter(source=arm_import.SOURCE).count(),
        'book_total': Book.objects.count(),
        'free_gb': round(free_bytes() / 1024 ** 3, 1),
        'min_free_gb': settings.MEDIA_MIN_FREE_GB,
        **_status_context(), **extra})


def _result(request, **context):
    return render(request, 'panel/import/_result.html', context)


@require_POST
@require_perm(Perms.CATALOG_IMPORT)
def arm_start(request):
    """«Solishtirish» (hech narsa yozmaydi) yoki importni fonda boshlaydi."""
    dry = request.POST.get('mode') != 'import'
    covers = bool(request.POST.get('covers'))
    files = bool(request.POST.get('files'))
    if arm_import.start(dry=dry, covers=covers, files=files) is None:
        return _result(request, error="Import allaqachon ishlayapti.")
    if not dry:
        log_action(ActionLog.Action.IMPORT, actor=request.user,
                   note="Universitet bazasidan import boshlandi"
                        + (", muqovalar bilan" if covers else "")
                        + (", PDF fayllar bilan" if files else ""))
    response = _result(request, started=True, dry=dry)
    response['HX-Trigger'] = 'arm-changed'
    return response


@require_POST
@require_perm(Perms.CATALOG_IMPORT)
def arm_stop(request):
    background.request_stop(arm_import.JOB_NAME)
    return render(request, 'panel/import/_status.html', _status_context())


@require_perm(Perms.CATALOG_IMPORT)
def arm_status(request):
    return render(request, 'panel/import/_status.html', _status_context())


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
    """Import sahifasi va CSV namunasi."""
    if request.GET.get('template') == '1':
        return csv_response(request, 'kitob-shabloni', importers.template_header(),
                            [importers.EXAMPLE])
    return _import_page(request)
