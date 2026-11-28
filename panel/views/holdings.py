"""
Xodim paneli — FOND TUZILMASI: filiallar, nusxa turlari, javonlar.

Kutubxonachi Django admin'ga kirmasdan shu yerdan boshqaradi. Uchala
ma'lumotnoma bitta sahifada: ko'rish, qo'shish, tahrirlash, faolsizlantirish.
"""
from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit.models import ActionLog
from audit.services import log_action, log_change, snapshot
from holdings.models import ItemType, Library, ShelfLocation
from user_app.permissions import Perms, require_perm

from ..forms import PanelItemTypeForm, PanelLibraryForm, PanelShelfForm

#: kind -> (model, forma, sarlavha)
KINDS = {
    'library': (Library, PanelLibraryForm, "Filial"),
    'type': (ItemType, PanelItemTypeForm, "Nusxa turi"),
    'shelf': (ShelfLocation, PanelShelfForm, "Javon"),
}


def _overview_ctx(forms=None):
    return {
        'active': 'holdings',
        'page_title': "Fond tuzilmasi",
        'libraries': (Library.objects.annotate(items_total=Count('items'))
                      .prefetch_related('shelves').order_by('order', 'name')),
        'item_types': ItemType.objects.annotate(items_total=Count('items')).order_by('order', 'name'),
        'shelves': (ShelfLocation.objects
                    .select_related('library')
                    .annotate(items_total=Count('items'))
                    .order_by('library__name', 'code')),
        'forms': forms or {
            'library': PanelLibraryForm(),
            'type': PanelItemTypeForm(),
            'shelf': PanelShelfForm(),
        },
    }


@require_perm(Perms.ITEMS_MANAGE)
def holdings_overview(request):
    """Uchala ma'lumotnoma bitta sahifada; POST — yangi yozuv qo'shish."""
    if request.method != 'POST':
        return render(request, 'panel/holdings/overview.html', _overview_ctx())

    # DIQQAT: `kind` nomi `Library.kind` maydoni bilan to'qnashadi,
    # shuning uchun bo'lim diskriminatori `form_kind` deb ataladi.
    kind = request.POST.get('form_kind', '')
    if kind not in KINDS:
        messages.error(request, "Noma'lum bo'lim.")
        return redirect('panel:holdings')

    _, form_class, label = KINDS[kind]
    form = form_class(request.POST)
    if form.is_valid():
        obj = form.save()
        log_action(ActionLog.Action.SETTINGS, obj=obj, note=f"{label} qo'shildi")
        messages.success(request, f"{label} qo'shildi: {obj}")
        return redirect('panel:holdings')

    forms = {
        'library': PanelLibraryForm(),
        'type': PanelItemTypeForm(),
        'shelf': PanelShelfForm(),
    }
    forms[kind] = form
    messages.error(request, f"{label} saqlanmadi — formani tekshiring.")
    return render(request, 'panel/holdings/overview.html', _overview_ctx(forms))


@require_perm(Perms.ITEMS_MANAGE)
def holdings_edit(request, kind, pk):
    if kind not in KINDS:
        messages.error(request, "Noma'lum bo'lim.")
        return redirect('panel:holdings')

    model, form_class, label = KINDS[kind]
    obj = get_object_or_404(model, pk=pk)
    before = snapshot(obj)
    form = form_class(request.POST or None, instance=obj)

    if request.method == 'POST' and form.is_valid():
        form.save()
        log_change(ActionLog.Action.SETTINGS, obj, before, note=f"{label} tahrirlandi")
        messages.success(request, f"{label} saqlandi.")
        return redirect('panel:holdings')

    return render(request, 'panel/holdings/form.html', {
        'active': 'holdings',
        'page_title': f"{label}: {obj}",
        'breadcrumb': [{'label': "Fond tuzilmasi", 'url': '/panel/holdings/'},
                       {'label': str(obj)}],
        'form': form,
        'object': obj,
        'kind_label': label,
    })


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def holdings_delete(request, kind, pk):
    """Hech qayerda ishlatilmagan yozuvni o'chiradi; ishlatilgani faolsizlantiriladi."""
    if kind not in KINDS:
        messages.error(request, "Noma'lum bo'lim.")
        return redirect('panel:holdings')

    model, _, label = KINDS[kind]
    obj = get_object_or_404(model, pk=pk)
    used = obj.items.exists() or (kind == 'library' and obj.shelves.exists())
    if used:
        messages.error(request, f"{label} ishlatilgan — o'chirib bo'lmaydi, faolsizlantiring.")
        return redirect('panel:holdings')

    name = str(obj)
    log_action(ActionLog.Action.SETTINGS, obj=obj, note=f"{label} o'chirildi")
    try:
        obj.delete()
    except ProtectedError:
        messages.error(request, f"{label}ga bog'langan yozuvlar bor — o'chirib bo'lmadi.")
    else:
        messages.success(request, f"{label} o'chirildi: {name}")
    return redirect('panel:holdings')


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def holdings_toggle(request, kind, pk):
    """Faol/nofaol holatini almashtiradi (o'chirish o'rniga — tarix saqlanadi)."""
    if kind not in KINDS:
        messages.error(request, "Noma'lum bo'lim.")
        return redirect('panel:holdings')

    model, _, label = KINDS[kind]
    obj = get_object_or_404(model, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=['is_active'])

    log_action(ActionLog.Action.SETTINGS, obj=obj,
               note=f"{label} {'faollashtirildi' if obj.is_active else 'faolsizlantirildi'}")
    messages.success(request, f"{label} yangilandi.")
    return redirect('panel:holdings')
