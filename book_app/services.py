"""
Fond (katalog + nusxalar) biznes mantig'i.

Bu yerda nusxa bilan bog'liq barcha o'zgarish bitta joydan o'tadi: shtrix-kod
berish, holat o'zgarishi (jurnal + audit bilan), kitobning fond ko'rsatkichlarini
qayta hisoblash. View'lar va admin shu funksiyalarni chaqiradi — holat
to'g'ridan-to'g'ri `item.status = ...` deb o'zgartirilmaydi.
"""
import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.timezone import now

from .models import Book, Item, ItemStatusLog

logger = logging.getLogger('holdings')

BARCODE_PREFIX = getattr(settings, 'ITEM_BARCODE_PREFIX', 'XIU')
BARCODE_DIGITS = 9


# --------------------------------------------------------------------------
#  Shtrix-kod va inventar raqami
# --------------------------------------------------------------------------

def next_barcode() -> str:
    """Keyingi bo'sh shtrix-kod: XIU000000123."""
    last = (Item.objects
            .filter(barcode__startswith=BARCODE_PREFIX)
            .order_by('-barcode')
            .values_list('barcode', flat=True)
            .first())
    number = 0
    if last:
        match = re.search(r'(\d+)$', last)
        if match:
            number = int(match.group(1))
    return f"{BARCODE_PREFIX}{number + 1:0{BARCODE_DIGITS}d}"


def next_inventory_number(book) -> str:
    """Kitob ichida keyingi inventar raqami (INV-1, INV-2 ...)."""
    numbers = []
    for value in Item.objects.filter(book=book).values_list('inventory_number', flat=True):
        match = re.search(r'(\d+)$', value or '')
        if match:
            numbers.append(int(match.group(1)))
    return f"INV-{(max(numbers) + 1) if numbers else 1}"


# --------------------------------------------------------------------------
#  Nusxa yaratish
# --------------------------------------------------------------------------

@transaction.atomic
def create_items(book, quantity=1, *, item_type=None, library=None, shelf_location=None,
                 price=0, acquisition_source=Item.Source.PURCHASE, created_by=None,
                 call_number='', status=Item.Status.AVAILABLE):
    """Kitobga N ta nusxa qo'shadi: shtrix-kod va inventar raqami avtomatik.

    Qaytaradi: yaratilgan nusxalar ro'yxati.
    """
    from holdings.models import ItemType, Library

    item_type = item_type or ItemType.default()
    library = library or Library.default()
    created = []

    for _ in range(max(1, int(quantity or 1))):
        for attempt in range(3):
            try:
                item = Item.objects.create(
                    book=book,
                    barcode=next_barcode(),
                    inventory_number=next_inventory_number(book),
                    item_type=item_type,
                    library=library,
                    shelf_location=shelf_location,
                    call_number=call_number or _suggest_call_number(book),
                    status=status,
                    price=price or 0,
                    replacement_price=price or (item_type.replacement_cost_default if item_type else 0),
                    acquisition_source=acquisition_source,
                    acquired_on=now().date(),
                )
                created.append(item)
                break
            except IntegrityError:
                if attempt == 2:
                    raise
                logger.warning("Shtrix-kod/inventar raqami band chiqdi, qayta urinilmoqda")

    if created:
        log_item_event(created[0], None, status, reason=f"{len(created)} ta nusxa qo'shildi",
                       by=created_by)
        recalc_book_counters(book)
    return created


def _suggest_call_number(book):
    """Chaqiruv raqami: UDK + muallif belgisi (bo'lsa)."""
    parts = [book.udc, book.author_sign]
    return " ".join(p for p in parts if p).strip()


# --------------------------------------------------------------------------
#  Holat o'zgarishi
# --------------------------------------------------------------------------

@transaction.atomic
def change_item_status(item, new_status, *, reason='', by=None, document_no='', audit=True):
    """Nusxa holatini o'zgartiradi: jurnal + audit + ko'rsatkichlar.

    Qaytaradi: (o'zgardimi, xabar)
    """
    if item.status == new_status:
        return False, "Holat allaqachon shunday."

    old_status = item.status
    item.status = new_status
    if new_status == Item.Status.WITHDRAWN and not item.withdrawn_on:
        item.withdrawn_on = now().date()
    item.save()  # `is_available` save() ichida moslanadi

    log_item_event(item, old_status, new_status, reason=reason, by=by, document_no=document_no,
                   audit=audit)
    recalc_book_counters(item.book)
    return True, f"Holat o'zgardi: {item.get_status_display()}"


def log_item_event(item, old_status, new_status, *, reason='', by=None, document_no='',
                   audit=True):
    """Nusxa jurnaliga yozadi va audit izini qoldiradi."""
    ItemStatusLog.objects.create(
        item=item,
        from_status=old_status or '',
        to_status=new_status,
        reason=reason[:200],
        document_no=document_no[:60],
        changed_by=by,
    )
    # Berish/qabul qilishda audit yozuvini sirkulyatsiya o'zi qoldiradi
    if not audit:
        return

    from audit.models import ActionLog
    from audit.services import log_action
    action = (ActionLog.Action.ITEM_WITHDRAW if new_status == Item.Status.WITHDRAWN
              else ActionLog.Action.ITEM_EDIT)
    labels = dict(Item.Status.choices)
    log_action(action, obj=item, actor=by,
               note=f"{labels.get(old_status, '—')} → {labels.get(new_status, new_status)}"
                    + (f" ({reason})" if reason else ""))


def withdraw_item(item, reason, by=None, document_no=''):
    """Nusxani hisobdan chiqarish (yo'qolgan/eskirgan/shikastlangan)."""
    return change_item_status(item, Item.Status.WITHDRAWN, reason=reason, by=by,
                              document_no=document_no)


def mark_item_seen(item):
    """Inventarizatsiyada skanerlandi."""
    item.last_seen_at = now().date()
    item.save(update_fields=['last_seen_at', 'updated_at'])


# --------------------------------------------------------------------------
#  Ko'rsatkichlar
# --------------------------------------------------------------------------

def recalc_book_counters(book):
    """Kitobning fond ko'rsatkichlarini qayta hisoblaydi."""
    if book is None:
        return
    items = Item.objects.filter(book=book)
    Book.objects.filter(pk=book.pk).update(
        items_count=items.count(),
        available_count=items.filter(status=Item.Status.AVAILABLE).count(),
    )


def recalc_all_counters():
    """Barcha kitoblar uchun (management buyruq / migratsiyadan keyin)."""
    count = 0
    for book in Book.objects.all().only('id'):
        recalc_book_counters(book)
        count += 1
    return count
