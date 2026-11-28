"""
Abonement amallari: kitob berish, qabul qilish, muddat uzaytirish, navbat.

Xodim deski (`/panel/desk/`), so'rovni tasdiqlash va ijaralar ro'yxati — hammasi
shu funksiyalardan o'tadi, shuning uchun qoida bitta joyda tekshiriladi.

Cheklovlar ikki xil:
  · **qat'iy** — hech kim chetlab o'ta olmaydi (nusxa boshqada turibdi, a'zolik yopilgan);
  · **chetlab o'tsa bo'ladigan** — `circ.override` ruxsati bor xodim sabab yozib
    davom ettiradi (limit, qarz, navbat...). Bu har safar audit jurnaliga tushadi.

Ruxsatni view tekshiradi; bu yerda faqat kutubxona qoidalari.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils.timezone import now

from audit.models import ActionLog
from audit.services import log_action
from book_app.models import Item, ItemStatusLog, Rental
from book_app.services import change_item_status
from notifications.models import Notification

from .models import Fine, LibrarySettings, RentalRequest, Reservation
from .services import (
    create_reservation,
    fine_rate_for,
    loan_days_for,
    loan_limit_for,
    mark_fine_paid,
    notify_patron,
    patron_pending_request,
    recalc_patron_counters,
    student_of,
)

OPEN_HOLDS = (Reservation.Status.WAITING, Reservation.Status.AVAILABLE)
MY_LOANS_LINK = '/circulation/my-rentals/'


@dataclass(frozen=True)
class Block:
    """Amalga to'sqinlik qiluvchi bitta sabab."""
    code: str
    message: str
    overridable: bool = True


@dataclass
class Result:
    """Abonement amalining natijasi."""
    ok: bool
    message: str
    rental: Rental | None = None
    blocks: tuple = ()
    # qabul qilishda to'ldiriladi
    fine: Fine | None = None
    days_late: int = 0
    next_hold: Reservation | None = None

    @property
    def can_override(self):
        return bool(self.blocks) and all(block.overridable for block in self.blocks)


#: A'zo holatiga bog'liq, lekin xodim chetlab o'ta oladigan sabablar
_OVERRIDABLE_PATRON = {'blocked', 'expired', 'limit', 'debt'}


def patron_blocks(patron):
    """A'zoning o'ziga bog'liq cheklovlar (kitobdan qat'i nazar)."""
    blocks = [Block(code, message, code in _OVERRIDABLE_PATRON)
              for code, message in patron.borrow_blocks()]

    # Toifada limit berilmagan bo'lsa — umumiy sozlamadagi limit amal qiladi
    if not any(block.code == 'limit' for block in blocks):
        limit = loan_limit_for(patron)
        if limit and Rental.objects.filter(patron=patron, return_date__isnull=True).count() >= limit:
            blocks.append(Block('limit', f"Ijara limiti to'lgan ({limit} ta)."))
    return blocks


def item_blocks(patron, item):
    """Aynan shu nusxani shu a'zoga berishga to'sqinlik qiluvchi sabablar."""
    open_rental = (Rental.objects.filter(copy=item, return_date__isnull=True)
                   .select_related('patron__user').first())
    if open_rental:
        holder = "shu a'zoning o'zida" if open_rental.patron_id == patron.pk \
            else open_rental.borrower_name
        return [Block('on_loan', f"Nusxa hozir ijarada: {holder}.", False)]

    lendable = (Item.Status.AVAILABLE, Item.Status.ON_HOLD_SHELF, Item.Status.NOT_FOR_LOAN)
    if item.status not in lendable:
        return [Block('unavailable',
                      f"Nusxani berib bo'lmaydi — holati: {item.get_status_display()}.", False)]

    blocks = []
    reading_room_only = (item.status == Item.Status.NOT_FOR_LOAN
                         or (item.item_type_id and not item.item_type.is_loanable))
    if reading_room_only and not patron.category.can_borrow_reading_room_items:
        blocks.append(Block('reading_room', "Bu nusxa faqat o'quv zalida foydalanish uchun."))

    if Rental.objects.filter(patron=patron, copy__book_id=item.book_id,
                             return_date__isnull=True).exists():
        blocks.append(Block('same_book', "Bu kitobning boshqa nusxasi a'zoning qo'lida."))

    if item.status != Item.Status.NOT_FOR_LOAN:
        queue_block = _queue_block(patron, item)
        if queue_block:
            blocks.append(queue_block)
    return blocks


def _queue_block(patron, item):
    """Navbatda oldinda turganlarga yetadigan nusxa qolmasa — cheklov."""
    holds = Reservation.objects.filter(book_id=item.book_id, status__in=OPEN_HOLDS)
    own = holds.filter(patron=patron).order_by('created_at').first()
    if own and own.status == Reservation.Status.AVAILABLE:
        return None

    ahead = holds.exclude(patron=patron)
    if own:
        ahead = ahead.filter(created_at__lt=own.created_at) | ahead.filter(
            status=Reservation.Status.AVAILABLE)
    ahead = list(ahead.select_related('patron__user').order_by('created_at'))
    if not ahead:
        return None

    free = Item.objects.filter(
        book_id=item.book_id,
        status__in=(Item.Status.AVAILABLE, Item.Status.ON_HOLD_SHELF)).count()
    if len(ahead) < free:
        return None

    first = next((hold for hold in ahead if hold.status == Reservation.Status.AVAILABLE), ahead[0])
    return Block('held', f"Kitob navbatdagi a'zo uchun ushlab turilibdi: {first.borrower_name} "
                         f"(navbatda {len(ahead)} kishi).")


def _refusal(blocks, override, reason):
    """Cheklovlar amalga ruxsat bermasa — rad javobi, aks holda None."""
    if not blocks:
        return None
    hard = [block for block in blocks if not block.overridable]
    if hard:
        return Result(False, hard[0].message, blocks=tuple(blocks))
    if not override:
        return Result(False, blocks[0].message, blocks=tuple(blocks))
    if not (reason or '').strip():
        return Result(False, "Cheklovni chetlab o'tish uchun sabab yozing.", blocks=tuple(blocks))
    return None


def _log_override(rental, librarian, reason, blocks):
    log_action(ActionLog.Action.OVERRIDE, obj=rental, actor=librarian,
               note=f"{reason.strip()} | " + " ".join(block.message for block in blocks))


@transaction.atomic
def checkout(patron, item, librarian=None, *, due_date=None, override=False, reason='',
             request=None):
    """Nusxani a'zoga beradi."""
    item = (Item.objects.select_for_update(of=('self',))
            .select_related('book', 'item_type').get(pk=item.pk))
    recalc_patron_counters(patron)

    today = now().date()
    if due_date and due_date < today:
        return Result(False, "Qaytarish muddati o'tmishda bo'lishi mumkin emas.")

    blocks = patron_blocks(patron) + item_blocks(patron, item)
    refusal = _refusal(blocks, override, reason)
    if refusal:
        return refusal

    due = due_date or today + timedelta(days=loan_days_for(patron))
    rental = Rental.objects.create(
        copy=item,
        patron=patron,
        student=student_of(patron),
        library_admin_checked=True,
        borrowed_date=today,
        due_date=due,
    )
    # Nusxa holati yagona joydan o'zgaradi: jurnal + audit + ko'rsatkichlar
    change_item_status(item, Item.Status.ON_LOAN,
                       reason=f"Ijaraga berildi — {rental.borrower_name}", by=librarian,
                       audit=False)

    Reservation.objects.filter(patron=patron, book=item.book, status__in=OPEN_HOLDS).update(
        status=Reservation.Status.FULFILLED)

    request = request or patron_pending_request(patron, item.book)
    if request and request.status == RentalRequest.Status.PENDING:
        request.status = RentalRequest.Status.APPROVED
        request.rental = rental
        request.decided_at = now()
        request.decided_by = librarian
        request.save(update_fields=['status', 'rental', 'decided_at', 'decided_by'])

    recalc_patron_counters(patron)

    if request:
        notify_patron(patron, "So'rovingiz tasdiqlandi",
                      f"«{item.book.title}» — kutubxonadan olishingiz mumkin. "
                      f"Qaytarish: {due:%d.%m.%Y}.",
                      type=Notification.Type.REQUEST_APPROVED, link=MY_LOANS_LINK)
    else:
        notify_patron(patron, "Kitob berildi",
                      f"«{item.book.title}» sizga berildi. Qaytarish: {due:%d.%m.%Y}.",
                      type=Notification.Type.GENERAL, link=MY_LOANS_LINK)

    log_action(ActionLog.Action.CHECKOUT, obj=rental, actor=librarian,
               note=f"{item.book.title} — {rental.borrower_name}")
    if blocks:
        _log_override(rental, librarian, reason, blocks)

    return Result(True, f"Berildi. Qaytarish muddati: {due:%d.%m.%Y}.", rental=rental)


def settle_fine(rental, today=None):
    """Kechikish jarimasini bugungi kunga hisoblab yozadi.

    To'langan yoki kechirilgan jarimaga tegilmaydi. Jarima stavkasi 0 bo'lsa va
    ilgari yozuv bo'lmasa — hech narsa yaratilmaydi.
    """
    today = today or now().date()
    existing = Fine.objects.filter(rental=rental).first()
    if not rental.due_date or today <= rental.due_date:
        return existing

    days = (today - rental.due_date).days
    amount = days * fine_rate_for(rental.patron)
    if existing is None:
        if amount <= 0:
            return None
        return Fine.objects.create(
            rental=rental, patron=rental.patron,
            student=rental.student or student_of(rental.patron),
            days_overdue=days, amount=amount)
    if not existing.is_paid:
        existing.days_overdue = days
        existing.amount = amount
        existing.patron = existing.patron or rental.patron
        existing.save(update_fields=['days_overdue', 'amount', 'patron'])
    return existing


def promote_next_hold(book):
    """Navbatdagi birinchi a'zoga kitobni ushlab turadi va xabar beradi."""
    nxt = (Reservation.objects
           .filter(book=book, status=Reservation.Status.WAITING)
           .select_related('patron__user')
           .order_by('created_at')
           .first())
    if nxt is None:
        return None

    days = LibrarySettings.load().reservation_hold_days
    nxt.status = Reservation.Status.AVAILABLE
    nxt.hold_until = now() + timedelta(days=days)
    nxt.save(update_fields=['status', 'hold_until'])

    notify_patron(nxt.patron, "Navbatdagi kitob bo'shadi",
                  f"«{book.title}» bo'shadi — {days} kun ichida kutubxonadan olib keting.",
                  type=Notification.Type.RESERVATION_AVAILABLE, link=f'/books/{book.pk}/')
    return nxt


def _status_before_loan(item):
    """Faqat-zal nusxasi qaytganda yana faqat-zal bo'lib qolsin."""
    last = (ItemStatusLog.objects.filter(item=item, to_status=Item.Status.ON_LOAN)
            .order_by('-pk').first())
    if last and last.from_status == Item.Status.NOT_FOR_LOAN:
        return Item.Status.NOT_FOR_LOAN
    return Item.Status.AVAILABLE


@transaction.atomic
def checkin(rental, librarian=None, *, damaged=False):
    """Ijarani yopadi: jarima hisoblanadi, nusxa bo'shaydi, navbat suriladi."""
    locked = Rental.objects.select_for_update().get(pk=rental.pk)
    if locked.return_date is not None:
        return Result(False, "Bu ijara allaqachon qaytarilgan.", rental=rental)

    today = now().date()
    days_late = max((today - rental.due_date).days, 0) if rental.due_date else 0
    fine = settle_fine(rental, today)

    rental.return_date = today
    rental.save(update_fields=['return_date', 'updated_at'])

    item = rental.copy
    if item.status != Item.Status.WITHDRAWN:
        new_status = Item.Status.DAMAGED if damaged else _status_before_loan(item)
        change_item_status(item, new_status,
                           reason=f"Qaytarildi — {rental.borrower_name}", by=librarian,
                           audit=False)
    item.loan_count = (item.loan_count or 0) + 1
    item.last_seen_at = today
    item.save(update_fields=['loan_count', 'last_seen_at', 'updated_at'])

    recalc_patron_counters(rental.patron)

    next_hold = None
    if item.status == Item.Status.AVAILABLE:
        next_hold = promote_next_hold(item.book)

    log_action(ActionLog.Action.CHECKIN, obj=rental, actor=librarian,
               note=f"{item.book.title} — {rental.borrower_name}"
                    + (" (shikastlangan)" if damaged else ""))
    return Result(True, "Kitob qaytarildi.", rental=rental, fine=fine,
                  days_late=days_late, next_hold=next_hold)


def renewal_blocks(rental):
    """Muddat uzaytirishga to'sqinlik qiluvchi sabablar."""
    if rental.return_date is not None:
        return [Block('returned', "Bu ijara allaqachon qaytarilgan.", False)]

    blocks = []
    if rental.due_date and rental.due_date < now().date():
        # Uzaytirilsa to'planib qolgan jarima yo'qoladi — avval qabul qilinadi
        blocks.append(Block('overdue', "Muddati o'tgan ijara uzaytirilmaydi — "
                                       "qabul qilib, qayta bering.", False))
    patron = rental.patron
    if patron is None:
        return blocks

    blocks += [block for block in patron_blocks(patron) if block.code != 'limit']

    allowed = patron.category.renewals_allowed
    if rental.renewals_count >= allowed:
        blocks.append(Block('renewals', f"Uzaytirish soni tugagan ({allowed} marta mumkin)."))

    if (Reservation.objects.filter(book_id=rental.copy.book_id, status__in=OPEN_HOLDS)
            .exclude(patron=patron).exists()):
        blocks.append(Block('held', "Bu kitobga navbat bor."))
    return blocks


@transaction.atomic
def renew(rental, librarian=None, *, override=False, reason=''):
    """Qaytarish muddatini yana bir ijara muddatiga uzaytiradi."""
    rental = (Rental.objects.select_for_update(of=('self',))
              .select_related('copy__book', 'patron__category', 'patron__user')
              .get(pk=rental.pk))
    if rental.patron:
        recalc_patron_counters(rental.patron)

    blocks = renewal_blocks(rental)
    refusal = _refusal(blocks, override, reason)
    if refusal:
        refusal.rental = rental
        return refusal

    today = now().date()
    old_due = rental.due_date
    rental.due_date = max(today, old_due or today) + timedelta(days=loan_days_for(rental.patron))
    rental.renewals_count += 1
    rental.save(update_fields=['due_date', 'renewals_count', 'updated_at'])

    notify_patron(rental.patron, "Qaytarish muddati uzaytirildi",
                  f"«{rental.copy.book.title}» — yangi muddat: {rental.due_date:%d.%m.%Y}.",
                  type=Notification.Type.GENERAL, link=MY_LOANS_LINK)
    log_action(ActionLog.Action.RENEW, obj=rental, actor=librarian,
               changes={'due_date': [str(old_due), str(rental.due_date)]},
               note=f"{rental.copy.book.title} — {rental.borrower_name}")
    if blocks:
        _log_override(rental, librarian, reason, blocks)
    return Result(True, f"Muddat uzaytirildi: {rental.due_date:%d.%m.%Y}.", rental=rental)


def place_hold(patron, book, librarian=None):
    """Xodim a'zoni navbatga yozadi."""
    reservation, message = create_reservation(patron, book)
    if reservation is None:
        return Result(False, message)
    log_action(ActionLog.Action.HOLD_PLACE, obj=reservation, actor=librarian,
               note=f"{book.title} — {reservation.borrower_name}")
    return Result(True, f"{reservation.borrower_name} navbatga yozildi.")


@transaction.atomic
def cancel_hold(reservation, librarian=None):
    """Navbatni xodim bekor qiladi; ushlab turilgan bo'lsa keyingisiga o'tadi."""
    if reservation.status not in OPEN_HOLDS:
        return Result(False, "Bu navbat allaqachon yopilgan.")

    was_ready = reservation.status == Reservation.Status.AVAILABLE
    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=['status'])

    notify_patron(reservation.patron, "Navbat bekor qilindi",
                  f"«{reservation.book.title}» bo'yicha navbatingiz bekor qilindi.",
                  type=Notification.Type.GENERAL, link=f'/books/{reservation.book_id}/')
    log_action(ActionLog.Action.HOLD_CANCEL, obj=reservation, actor=librarian,
               note=f"{reservation.book.title} — {reservation.borrower_name}")

    next_hold = promote_next_hold(reservation.book) if was_ready else None
    return Result(True, "Navbat bekor qilindi.", next_hold=next_hold)


# --------------------------------------------------------------------------
#  Yo'qolgan kitob va jarima amallari
# --------------------------------------------------------------------------

@transaction.atomic
def declare_lost(rental, librarian=None, *, amount=0, note=''):
    """Kitob yo'qolgan: ijara yopiladi, nusxa «Yo'qolgan», to'lov a'zoga yoziladi.

    `amount` — kitob qiymati uchun to'lov; kechikish jarimasi ustiga qo'shiladi.
    """
    locked = Rental.objects.select_for_update().get(pk=rental.pk)
    if locked.return_date is not None:
        return Result(False, "Bu ijara allaqachon yopilgan.", rental=rental)

    today = now().date()
    fine = settle_fine(rental, today)
    if amount:
        reason = f"Yo'qolgan kitob uchun {amount:.0f} so'm. {note}".strip()[:255]
        if fine is None:
            fine = Fine.objects.create(
                rental=rental, patron=rental.patron,
                student=rental.student or student_of(rental.patron),
                amount=amount, note=reason)
        elif not fine.is_paid:
            fine.amount += amount
            fine.note = reason
            fine.save(update_fields=['amount', 'note'])

    rental.return_date = today
    rental.save(update_fields=['return_date', 'updated_at'])
    change_item_status(rental.copy, Item.Status.LOST,
                       reason=f"Yo'qolgan — {rental.borrower_name}. {note}".strip(),
                       by=librarian)
    recalc_patron_counters(rental.patron)

    log_action(ActionLog.Action.FINE_CHARGE if amount else ActionLog.Action.CHECKIN,
               obj=rental, actor=librarian,
               note=f"Yo'qolgan: {rental.copy.book.title} — {rental.borrower_name}")
    return Result(True, "Kitob yo'qolgan deb belgilandi.", rental=rental, fine=fine)


def collect_fine(fine, librarian=None):
    """To'lov qabul qiladi — faqat kitob qaytgach, summa yakuniy bo'lganda."""
    if fine.rental.return_date is None:
        return False, "Avval kitobni qabul qiling — jarima hali hisoblanmoqda."
    return mark_fine_paid(fine, librarian)


def waive_fine(fine, librarian=None, note=''):
    """Jarimani kechiradi (sabab majburiy)."""
    if fine.is_paid:
        return False, "Bu jarima allaqachon yopilgan."
    if fine.rental.return_date is None:
        return False, "Avval kitobni qabul qiling — jarima hali hisoblanmoqda."
    note = (note or '').strip()
    if not note:
        return False, "Kechirish sababini yozing."

    fine.is_paid = True
    fine.is_waived = True
    fine.paid_at = now()
    fine.note = note[:255]
    fine.save(update_fields=['is_paid', 'is_waived', 'paid_at', 'note'])
    recalc_patron_counters(fine.patron)
    log_action(ActionLog.Action.WAIVE, obj=fine, actor=librarian,
               note=f"{fine.borrower_name} — {fine.amount:.0f} so'm | {note}")
    return True, "Jarima kechirildi."


def adjust_fine(fine, librarian=None, amount=0, note=''):
    """Yakuniy jarima summasini tuzatadi (sabab majburiy)."""
    if fine.is_paid:
        return False, "Yopilgan jarima o'zgartirilmaydi."
    if fine.rental.return_date is None:
        return False, "Avval kitobni qabul qiling — jarima hali hisoblanmoqda."
    note = (note or '').strip()
    if not note:
        return False, "O'zgartirish sababini yozing."
    if amount <= 0:
        return False, "Summa noldan katta bo'lsin. Butunlay bekor qilish uchun — «Kechirish»."

    old = fine.amount
    fine.amount = amount
    fine.note = note[:255]
    fine.save(update_fields=['amount', 'note'])
    recalc_patron_counters(fine.patron)
    log_action(ActionLog.Action.FINE_CHARGE, obj=fine, actor=librarian,
               changes={'amount': [str(old), str(amount)]},
               note=f"{fine.borrower_name} | {note}")
    return True, "Jarima summasi o'zgartirildi."
