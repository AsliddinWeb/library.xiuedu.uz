"""
Xodim paneli — A'ZOLAR moduli.

Ilgari bu bo'lim faqat talabalarni (`StudentProfile`) ko'rsatardi. Endi u
**kutubxona a'zolari** (`Patron`) bilan ishlaydi: talaba, magistrant, doktorant,
o'qituvchi, xodim va qo'lda qo'shilgan tashqi o'quvchi — hammasi bitta ro'yxatda.

Imkoniyatlar: qidiruv (ism/bilet/HEMIS ID/guruh), toifa va holat filtri,
a'zo kartasi (ijaralar, so'rovlar, navbatlar, jarimalar), bloklash/ochish,
qo'lda a'zo qo'shish va tahrirlash.
"""
from datetime import date

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from audit.models import ActionLog
from audit.services import log_action, log_change, snapshot
from book_app.models import Rental
from circulation.models import Fine, RentalRequest, Reservation
from circulation.services import recalc_patron_counters
from user_app.models import Patron, PatronCategory
from user_app.permissions import Perms, require_perm
from user_app.services import membership_expiry, next_card_number

from ..exports import csv_response, wants_csv

PER_PAGE = 25


class PatronForm(forms.ModelForm):
    """Qo'lda a'zo qo'shish/tahrirlash (odatda tashqi o'quvchi).

    HEMIS orqali kirgan a'zoning ismi `User`dan olinadi, shuning uchun bu
    formadagi ism maydonlari faqat HEMIS'siz a'zolar uchun.
    """

    class Meta:
        model = Patron
        fields = ('card_number', 'category', 'status', 'full_name', 'phone', 'email',
                  'birth_date', 'address', 'photo', 'expires_on', 'deposit_amount', 'note')
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'expires_on': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'note': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = PatronCategory.objects.filter(is_active=True)
        if not self.instance.pk:
            self.fields['card_number'].initial = next_card_number()
            self.fields['card_number'].help_text = "Avtomatik taklif qilindi — o'zgartirsa ham bo'ladi."
        # Tailwind komponent klasslari
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'select')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'textarea')
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'checkbox')
            else:
                widget.attrs.setdefault('class', 'input')

    def clean(self):
        data = super().clean()
        if not self.instance.user_id and not data.get('full_name'):
            self.add_error('full_name', "HEMIS'siz a'zo uchun F.I.Sh. majburiy.")
        return data


def _members_ctx(request):
    qs = (Patron.objects
          .select_related('user', 'category')
          .order_by('-created_at'))

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()

    if q:
        qs = qs.filter(
            Q(card_number__icontains=q) |
            Q(full_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__second_name__icontains=q) |
            Q(user__hemis_uuid__icontains=q) |
            Q(user__student_profile__group__icontains=q) |
            Q(user__student_profile__faculty__icontains=q)
        )
    if category:
        qs = qs.filter(category__code=category)
    if status:
        qs = qs.filter(status=status)

    page = Paginator(qs, PER_PAGE).get_page(request.GET.get('page', 1))

    filters = {key: value for key, value in
               (('q', q), ('category', category), ('status', status)) if value}
    query = '&' + urlencode(filters) if filters else ''

    return {
        'active': 'members',
        'page_title': "Kutubxona a'zolari",
        'members': page,
        'page_obj': page,
        'q': q,
        'category': category,
        'status': status,
        'categories': PatronCategory.objects.filter(is_active=True),
        'statuses': Patron.Status.choices,
        'query': query,
        'export_query': urlencode({**filters, 'export': 'csv'}),
        'filtered': qs,
        'total': qs.count(),
    }


@require_perm(Perms.PATRONS_VIEW)
def members(request):
    ctx = _members_ctx(request)
    if wants_csv(request):
        rows = ((p.card_number, p.display_name, p.category.name, p.get_status_display(),
                 p.contact_phone, p.contact_email, p.registered_on, p.expires_on,
                 p.active_loans_count, p.overdue_count, p.balance)
                for p in ctx['filtered'].iterator(chunk_size=500))
        return csv_response(request, 'azolar',
                            ['Bilet', 'F.I.Sh.', 'Toifa', 'Holat', 'Telefon', 'E-pochta',
                             "Ro'yxatga olingan", 'Amal qiladi', 'Ijarada', 'Kechikkan',
                             "Qarz (so'm)"], rows)
    template = ('panel/members/_table.html' if getattr(request, 'htmx', False)
                else 'panel/members/list.html')
    return render(request, template, ctx)


def _can_delete(patron):
    """Faqat qo'lda qo'shilgan va hech qanday izi yo'q a'zo o'chiriladi."""
    return not patron.user_id and not any(
        model.objects.filter(patron=patron).exists()
        for model in (Rental, RentalRequest, Reservation, Fine))


@require_perm(Perms.PATRONS_VIEW)
def member_detail(request, pk):
    patron = get_object_or_404(
        Patron.objects.select_related('user', 'category', 'user__student_profile',
                                      'user__employe_profile'),
        pk=pk)

    # Ko'rsatkichlar har ochilganda qayta hisoblanadi — karta doim haqiqatni ko'rsatsin
    recalc_patron_counters(patron)
    patron.refresh_from_db()

    rentals = (Rental.objects.filter(patron=patron)
               .select_related('copy__book').order_by('-id')[:30])
    requests_qs = (RentalRequest.objects.filter(patron=patron)
                   .select_related('book').order_by('-created_at')[:20])
    reservations = (Reservation.objects.filter(patron=patron)
                    .select_related('book').order_by('-created_at')[:20])
    fines = (Fine.objects.filter(patron=patron)
             .select_related('rental__copy__book').order_by('-created_at'))
    history = (ActionLog.objects
               .filter(object_type='user_app.Patron', object_id=str(patron.pk))
               .order_by('-at')[:15])

    can_borrow, block_reason = patron.can_borrow()

    return render(request, 'panel/members/detail.html', {
        'active': 'members',
        'page_title': patron.display_name,
        'breadcrumb': [{'label': "A'zolar", 'url': '/panel/members/'},
                       {'label': patron.card_number}],
        'patron': patron,
        'rentals': rentals,
        'requests': requests_qs,
        'reservations': reservations,
        'fines': fines,
        'history': history,
        'can_borrow': can_borrow,
        'block_reason': block_reason,
        'can_delete': _can_delete(patron),
        'active_rentals': [r for r in rentals if r.is_active],
        'unpaid_fines': [f for f in fines if not f.is_paid],
    })


@require_perm(Perms.PATRONS_EDIT)
def member_create(request):
    form = PatronForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        patron = form.save(commit=False)
        if not patron.expires_on:
            patron.expires_on = membership_expiry(patron.category)
        patron.save()
        log_action(ActionLog.Action.PATRON_CREATE, obj=patron,
                   note=f"Qo'lda qo'shildi — {patron.category.name}")
        messages.success(request, f"A'zo qo'shildi: {patron.display_name} ({patron.card_number})")
        return redirect('panel:member_detail', pk=patron.pk)

    return render(request, 'panel/members/form.html', {
        'active': 'members',
        'page_title': "Yangi a'zo",
        'breadcrumb': [{'label': "A'zolar", 'url': '/panel/members/'}, {'label': "Yangi"}],
        'form': form,
        'is_create': True,
    })


@require_perm(Perms.PATRONS_EDIT)
def member_edit(request, pk):
    patron = get_object_or_404(Patron, pk=pk)
    before = snapshot(patron)
    form = PatronForm(request.POST or None, request.FILES or None, instance=patron)

    if request.method == 'POST' and form.is_valid():
        patron = form.save()
        log_change(ActionLog.Action.PATRON_EDIT, patron, before)
        messages.success(request, "A'zo ma'lumotlari saqlandi.")
        return redirect('panel:member_detail', pk=patron.pk)

    return render(request, 'panel/members/form.html', {
        'active': 'members',
        'page_title': f"Tahrirlash — {patron.display_name}",
        'breadcrumb': [{'label': "A'zolar", 'url': '/panel/members/'},
                       {'label': patron.card_number, 'url': f'/panel/members/{patron.pk}/'},
                       {'label': "Tahrirlash"}],
        'form': form,
        'patron': patron,
        'is_create': False,
    })


@require_POST
@require_perm(Perms.PATRONS_BLOCK)
def member_block(request, pk):
    patron = get_object_or_404(Patron, pk=pk)
    reason = (request.POST.get('reason') or '').strip()
    raw_until = (request.POST.get('until') or '').strip()
    try:
        until = date.fromisoformat(raw_until) if raw_until else None
    except ValueError:
        until = False
    if until is False or (until and until < now().date()):
        messages.error(request, "Blok muddati noto'g'ri — bugundan keyingi sana tanlang.")
        return redirect('panel:member_detail', pk=patron.pk)

    patron.status = Patron.Status.BLOCKED
    patron.block_reason = reason[:255]
    patron.blocked_until = until
    patron.save(update_fields=['status', 'block_reason', 'blocked_until', 'updated_at'])

    log_action(ActionLog.Action.PATRON_BLOCK, obj=patron,
               note="Bloklandi: " + (reason or "sabab ko'rsatilmagan"))
    messages.warning(request, f"{patron.display_name} bloklandi.")
    return redirect('panel:member_detail', pk=patron.pk)


@require_POST
@require_perm(Perms.PATRONS_BLOCK)
def member_unblock(request, pk):
    patron = get_object_or_404(Patron, pk=pk)
    patron.status = (Patron.Status.EXPIRED if patron.is_expired else Patron.Status.ACTIVE)
    patron.block_reason = ''
    patron.blocked_until = None
    patron.save(update_fields=['status', 'block_reason', 'blocked_until', 'updated_at'])

    log_action(ActionLog.Action.PATRON_BLOCK, obj=patron, note="Blok olib tashlandi")
    messages.success(request, f"{patron.display_name} blokdan chiqarildi.")
    return redirect('panel:member_detail', pk=patron.pk)


@require_POST
@require_perm(Perms.PATRONS_EDIT)
def member_renew(request, pk):
    """A'zolik muddatini toifadagi muddatga uzaytiradi."""
    patron = get_object_or_404(Patron, pk=pk)
    expiry = membership_expiry(patron.category, now().date())

    patron.expires_on = expiry
    if patron.status == Patron.Status.EXPIRED:
        patron.status = Patron.Status.ACTIVE
    patron.save(update_fields=['expires_on', 'status', 'updated_at'])

    log_action(ActionLog.Action.PATRON_EDIT, obj=patron,
               note=f"A'zolik uzaytirildi: {expiry or 'muddatsiz'}")
    messages.success(request, "A'zolik muddati uzaytirildi.")
    return redirect('panel:member_detail', pk=patron.pk)


@require_POST
@require_perm(Perms.PATRONS_EDIT)
def member_delete(request, pk):
    patron = get_object_or_404(Patron, pk=pk)
    if not _can_delete(patron):
        messages.error(request, "Bu a'zoni o'chirib bo'lmaydi: HEMIS hisobi yoki tarixi bor. "
                                "Kerak bo'lsa bloklang.")
        return redirect('panel:member_detail', pk=patron.pk)
    name = patron.display_name
    log_action(ActionLog.Action.PATRON_EDIT, obj=patron, note="A'zo o'chirildi")
    patron.delete()
    messages.success(request, f"A'zo o'chirildi: {name}")
    return redirect('panel:members')
