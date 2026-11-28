"""
Xodim paneli — HEMIS'dan talaba va xodimlarni yuklash.

Token ikki yo'l bilan beriladi: serverdagi `HEMIS_API_TOKEN` yoki shu
sahifadagi maydon. Maydondan kelgan token bazaga, sessiyaga va jurnalga
yozilmaydi hamda sahifaga qaytarilmaydi.
"""
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_POST

from audit.models import ActionLog, JobRun
from audit.services import log_action
from user_app.hemis import sync
from user_app.hemis.client import HemisClient, HemisError
from user_app.permissions import Perms, require_perm

__all__ = ['hemis', 'hemis_check', 'hemis_start', 'hemis_status']


def _status_context():
    sync.close_stale()
    runs = list(JobRun.objects.filter(name=sync.JOB_NAME)[:5])
    latest = runs[0] if runs else None
    rows = []
    if latest:
        for kind, label in sync.LABELS.items():
            stats = latest.stats
            if f'{kind}_total' not in stats and f'{kind}_done' not in stats:
                continue
            total = stats.get(f'{kind}_total') or 0
            done = stats.get(f'{kind}_done', 0)
            rows.append({
                'label': label, 'total': total, 'done': done,
                'percent': min(100, round(done * 100 / total)) if total else 0,
                'new': stats.get(f'{kind}_new', 0), 'updated': stats.get(f'{kind}_updated', 0),
                'same': stats.get(f'{kind}_same', 0), 'skipped': stats.get(f'{kind}_skipped', 0),
                'failed': stats.get(f'{kind}_failed', 0),
            })
    return {'runs': runs, 'latest': latest, 'rows': rows,
            'running': bool(latest and latest.status == JobRun.Status.RUNNING)}


@sensitive_variables('token')
def _request_data(request):
    """(token, tanlangan turlar) — token maydonda bo'lmasa serverdagisi."""
    token = request.POST.get('token', '').strip() or settings.HEMIS_API_TOKEN
    kinds = [kind for kind in sync.SOURCES if kind in request.POST.getlist('kinds')]
    if not kinds:
        raise HemisError("Kamida bittasini belgilang: talabalar yoki xodimlar.")
    return token, kinds


def _result(request, **context):
    return render(request, 'panel/hemis/_result.html', context)


@require_perm(Perms.SETTINGS_MANAGE)
def hemis(request):
    return render(request, 'panel/hemis/page.html', {
        'page_title': "HEMIS'dan yuklash",
        'has_server_token': bool(settings.HEMIS_API_TOKEN),
        'api_url': settings.HEMIS_API_URL,
        **_status_context(),
    })


@sensitive_post_parameters('token')
@sensitive_variables('token')
@require_POST
@require_perm(Perms.SETTINGS_MANAGE)
def hemis_check(request):
    """Hech narsa yozmaydi: tokenni sinaydi va yozuvlar sonini ko'rsatadi."""
    try:
        token, kinds = _request_data(request)
        counts = sync.preview(HemisClient(token), kinds)
    except HemisError as exc:
        return _result(request, error=str(exc))
    return _result(request, counts=[(sync.LABELS[kind], counts[kind]) for kind in kinds])


@sensitive_post_parameters('token')
@sensitive_variables('token')
@require_POST
@require_perm(Perms.SETTINGS_MANAGE)
def hemis_start(request):
    try:
        token, kinds = _request_data(request)
        # Noto'g'ri token fonda emas, shu yerda darhol bilinsin
        sync.preview(HemisClient(token), kinds)
        if sync.start(token, kinds) is None:
            raise HemisError("Sinxronlash allaqachon ishlayapti.")
    except HemisError as exc:
        return _result(request, error=str(exc))
    log_action(ActionLog.Action.IMPORT, actor=request.user,
               note="HEMIS'dan yuklash boshlandi: "
                    + ', '.join(sync.LABELS[kind] for kind in kinds))
    response = _result(request, started=True)
    response['HX-Trigger'] = 'hemis-started'
    return response


@require_perm(Perms.SETTINGS_MANAGE)
def hemis_status(request):
    return render(request, 'panel/hemis/_status.html', _status_context())
