"""
Xodim paneli — NUSXA boshqaruvi va tezkor qidiruv.

Kutubxonachining kundalik ishi nusxa darajasida boradi: shtrix-kodni skanerlaydi,
nusxani boshqa javonga ko'chiradi, holatini o'zgartiradi, hisobdan chiqaradi.
Shu sahifa aynan shuning uchun.
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from book_app.models import Book, Item, ItemStatusLog, Rental
from book_app.services import change_item_status, withdraw_item
from user_app.models import Patron
from user_app.permissions import Perms, has_perm, require_perm

from ..forms import ItemBulkActionForm, PanelItemForm

PER_PAGE = 30


# --------------------------------------------------------------------------
#  Nusxalar ro'yxati
# --------------------------------------------------------------------------

@require_perm(Perms.CATALOG_VIEW)
def item_list(request):
    """Butun fond bo'yicha nusxalar ro'yxati (shtrix-kod bo'yicha qidiruv bilan)."""
    items = (Item.objects
             .select_related('book', 'item_type', 'library', 'shelf_location')
             .order_by('-id'))

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    library = request.GET.get('library', '').strip()
    item_type = request.GET.get('type', '').strip()

    if q:
        items = items.filter(
            Q(barcode__icontains=q) | Q(inventory_number__icontains=q) |
            Q(call_number__icontains=q) | Q(book__title__icontains=q))
    if status:
        items = items.filter(status=status)
    if library:
        items = items.filter(library_id=library)
    if item_type:
        items = items.filter(item_type_id=item_type)

    page = Paginator(items, PER_PAGE).get_page(request.GET.get('page', 1))

    query = ''.join(f"&{key}={value}" for key, value in
                    (('q', q), ('status', status), ('library', library), ('type', item_type))
                    if value)

    from holdings.models import ItemType, Library
    ctx = {
        'active': 'items',
        'page_title': "Fond nusxalari",
        'items': page,
        'page_obj': page,
        'q': q, 'status': status, 'library': library, 'type': item_type, 'query': query,
        'statuses': Item.Status.choices,
        'libraries': Library.objects.filter(is_active=True),
        'item_types': ItemType.objects.filter(is_active=True),
        'total': page.paginator.count,
    }
    template = ('panel/items/_table.html' if getattr(request, 'htmx', False)
                else 'panel/items/list.html')
    return render(request, template, ctx)


# --------------------------------------------------------------------------
#  Nusxa kartasi
# --------------------------------------------------------------------------

@require_perm(Perms.CATALOG_VIEW)
def item_detail(request, pk):
    """Nusxa kartasi: tahrirlash formasi, holat amallari, tarix."""
    item = get_object_or_404(
        Item.objects.select_related('book', 'item_type', 'library', 'shelf_location'), pk=pk)

    form = PanelItemForm(request.POST or None, instance=item)
    if request.method == 'POST':
        # Ko'rish uchun `catalog.view` yetarli, lekin SAQLASH uchun `items.manage` kerak
        if not has_perm(request.user, Perms.ITEMS_MANAGE):
            return render(request, '403.html', status=403)
        if form.is_valid():
            from audit.models import ActionLog
            from audit.services import log_change, snapshot
            before = snapshot(item)
            form.save()
            log_change(ActionLog.Action.ITEM_EDIT, item, before)
            messages.success(request, "Nusxa saqlandi.")
            return redirect('panel:item_detail', pk=item.pk)

    loans = (Rental.objects.filter(copy=item)
             .select_related('patron__user').order_by('-id')[:15])
    logs = ItemStatusLog.objects.filter(item=item).select_related('changed_by')[:20]

    return render(request, 'panel/items/detail.html', {
        'active': 'items',
        'page_title': item.barcode or item.inventory_number,
        'breadcrumb': [
            {'label': "Kitoblar", 'url': '/panel/books/'},
            {'label': item.book.title[:40], 'url': f'/panel/books/{item.book_id}/'},
            {'label': item.barcode or item.inventory_number},
        ],
        'item': item,
        'form': form,
        'loans': loans,
        'logs': logs,
        'statuses': Item.Status.choices,
        'active_loan': next((loan for loan in loans if loan.is_active), None),
    })


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def item_status(request, pk):
    """Holatni qo'lda o'zgartirish (sabab bilan — jurnalga tushadi)."""
    item = get_object_or_404(Item, pk=pk)
    new_status = request.POST.get('status', '')
    reason = request.POST.get('reason', '').strip()

    if new_status not in dict(Item.Status.choices):
        messages.error(request, "Noto'g'ri holat.")
        return redirect('panel:item_detail', pk=item.pk)

    if item.status == Item.Status.ON_LOAN and new_status != Item.Status.LOST:
        messages.error(request, "Ijaradagi nusxa faqat qaytarilgandan keyin o'zgaradi "
                                "(yoki \"yo'qolgan\" deb belgilanadi).")
        return redirect('panel:item_detail', pk=item.pk)

    if new_status == Item.Status.WITHDRAWN:
        withdraw_item(item, reason=reason or "Panel orqali", by=request.user)
    else:
        change_item_status(item, new_status, reason=reason, by=request.user)

    messages.success(request, "Nusxa holati yangilandi.")
    return redirect('panel:item_detail', pk=item.pk)


@require_POST
@require_perm(Perms.ITEMS_MANAGE)
def item_bulk(request, pk):
    """Kitob sahifasidan bir nechta nusxaga bir vaqtda amal."""
    book = get_object_or_404(Book, pk=pk)
    form = ItemBulkActionForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Amalni to'liq tanlang.")
        return redirect('panel:book_detail', pk=book.pk)

    items = Item.objects.filter(pk__in=form.item_ids(), book=book)
    if not items:
        messages.warning(request, "Nusxa tanlanmagan.")
        return redirect('panel:book_detail', pk=book.pk)

    action = form.cleaned_data['action']
    reason = form.cleaned_data.get('reason') or "Partiyada o'zgartirildi"
    done = 0

    if action == 'status':
        new_status = form.cleaned_data['status']
        for item in items:
            if item.status == Item.Status.ON_LOAN:
                continue  # ijaradagi nusxaga tegmaymiz
            changed, _ = change_item_status(item, new_status, reason=reason, by=request.user)
            done += int(changed)
        messages.success(request, f"{done} ta nusxaning holati o'zgartirildi.")
    else:
        shelf = form.cleaned_data['shelf_location']
        for item in items:
            item.shelf_location = shelf
            item.library = shelf.library
            item.save(update_fields=['shelf_location', 'library', 'updated_at'])
            done += 1
        messages.success(request, f"{done} ta nusxa «{shelf.code}» javoniga ko'chirildi.")

    return redirect('panel:book_detail', pk=book.pk)


# --------------------------------------------------------------------------
#  Tezkor qidiruv (skaner uchun)
# --------------------------------------------------------------------------

@require_perm(Perms.CATALOG_VIEW)
def quick_search(request):
    """Topbardagi global qidiruv.

    Skaner shtrix-kodni o'qiydi va Enter bosadi — xodim hech narsa tanlamaydi:
      · nusxa shtrix-kodi  -> nusxa kartasi
      · o'quvchi bileti    -> a'zo kartasi
      · boshqa har qanday  -> kitoblar ro'yxatidagi qidiruv
    """
    q = (request.GET.get('q') or '').strip()
    if not q:
        return redirect('panel:books')

    item = Item.objects.filter(barcode__iexact=q).first()
    if item:
        return redirect('panel:item_detail', pk=item.pk)

    patron = Patron.objects.filter(card_number__iexact=q).first()
    if patron:
        return redirect('panel:member_detail', pk=patron.pk)

    # Inventar raqami ham skanerlanishi mumkin
    item = Item.objects.filter(inventory_number__iexact=q).first()
    if item:
        return redirect('panel:item_detail', pk=item.pk)

    return redirect(f'/panel/books/?q={q}')
