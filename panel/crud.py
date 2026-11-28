"""
Ma'lumotnomalar uchun umumiy CRUD: ro'yxat, qidiruv, yaratish, tahrirlash,
o'chirish, yoqib-o'chirish, takroriy yozuvlarni birlashtirish va CSV eksport.

Yangi ma'lumotnoma qo'shish — `resources.py` da bitta `Resource` e'lon qilish:
view'lar, manzillar va ruxsat tekshiruvi shu yerdan hosil bo'ladi.

URL nomlari: ro'yxat — `<name>`, qolganlari — `<single>_create`, `<single>_edit`,
`<single>_delete`, `<single>_toggle`, `<single>_merge`.
"""
from collections.abc import Callable
from dataclasses import dataclass

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from audit.models import ActionLog
from audit.services import log_action, log_change, snapshot
from user_app.permissions import Perms, has_perm, require_perm

from .exports import csv_response, wants_csv
from .htmx import render_partial_or_page, toast

PER_PAGE = 25


@dataclass(frozen=True)
class Column:
    label: str
    value: Callable
    numeric: bool = False


@dataclass(eq=False)
class Resource:
    name: str                       # ro'yxat manzili va URL nomi: 'authors'
    single: str                     # qolgan URL nomlari boshi: 'author'
    model: type
    form_class: type
    title: str                      # "Mualliflar"
    label: str                      # "muallif"
    columns: tuple
    search: tuple                   # qidiriladigan maydonlar
    ordering: tuple
    icon: str = 'folder'
    subtitle: str = ''
    usage: str = ''                 # bog'liqliklarni sanash uchun teskari bog'lanish
    usage_label: str = 'Kitoblar'
    usage_link: Callable | None = None   # yozuvga tegishli ro'yxat manzili
    toggle: str = ''                # mantiqiy maydon (masalan, is_active)
    merge: Callable | None = None   # merge(source, target) — takrorlarni birlashtirish
    view_perm: str = Perms.CATALOG_VIEW
    edit_perm: str = Perms.CATALOG_EDIT
    delete_perm: str = Perms.CATALOG_DELETE
    audit_action: str = ''          # bo'sh bo'lsa BIBLIO_* ishlatiladi

    # ------------------------------------------------------------ yordamchilar

    def queryset(self):
        qs = self.model.objects.all()
        if self.usage:
            qs = qs.annotate(used=Count(self.usage, distinct=True))
        return qs

    def filtered(self, query):
        qs = self.queryset()
        for word in query.split():
            condition = Q()
            for field in self.search:
                condition |= Q(**{f'{field}__icontains': word})
            qs = qs.filter(condition)
        return qs.order_by(*self.ordering, 'pk')

    def url(self, action='', *args):
        name = self.name if not action else f'{self.single}_{action}'
        return reverse(f'panel:{name}', args=args)

    def blocker(self, obj):
        """O'chirishga to'sqinlik qiluvchi sabab (bo'sh — o'chirsa bo'ladi)."""
        used = getattr(obj, 'used', 0)
        if used:
            hint = " Avval boshqa yozuvga birlashtiring." if self.merge else ""
            return f"Bu yozuv {used} ta joyda ishlatilgan — o'chirib bo'lmaydi.{hint}"
        return ''

    def log(self, kind, obj, **kwargs):
        action = self.audit_action or getattr(ActionLog.Action, f'BIBLIO_{kind}')
        log_action(action, obj=obj, **kwargs)

    # ------------------------------------------------------------ view'lar

    def _context(self, request, **extra):
        user = request.user
        return {
            'resource': self,
            'active': self.name,
            'page_title': self.title,
            'can_edit': has_perm(user, self.edit_perm),
            'can_delete': has_perm(user, self.delete_perm),
            **extra,
        }

    def _list_context(self, request):
        query = (request.POST.get('q') or request.GET.get('q') or '').strip()
        number = request.POST.get('page') or request.GET.get('page') or 1
        page = Paginator(self.filtered(query), PER_PAGE).get_page(number)
        rows = [{
            'obj': obj,
            'cells': [(column, column.value(obj)) for column in self.columns],
            'used': getattr(obj, 'used', None),
            'usage_url': self.usage_link(obj) if self.usage_link else '',
            'is_on': getattr(obj, self.toggle) if self.toggle else None,
            'edit_url': self.url('edit', obj.pk),
            'delete_url': self.url('delete', obj.pk),
            'toggle_url': self.url('toggle', obj.pk) if self.toggle else '',
            'merge_url': self.url('merge', obj.pk) if self.merge else '',
        } for obj in page]
        return self._context(
            request, rows=rows, page_obj=page, q=query,
            list_url=self.url(), create_url=self.url('create'),
            query='&' + urlencode({'q': query}) if query else '',
            export_query=urlencode({'q': query, 'export': 'csv'}))

    def _export(self, request):
        header = [column.label for column in self.columns]
        if self.usage:
            header.append(self.usage_label)
        rows = ([column.value(obj) for column in self.columns]
                + ([obj.used] if self.usage else [])
                for obj in self.filtered(request.GET.get('q', '').strip()))
        return csv_response(request, self.name, header, rows)

    def _form(self, request, obj=None):
        before = snapshot(obj) if obj else None
        form = self.form_class(request.POST or None, request.FILES or None, instance=obj)
        if request.method == 'POST' and form.is_valid():
            saved = form.save()
            if before is None:
                self.log('CREATE', saved)
                messages.success(request, f"«{saved}» qo'shildi.")
            else:
                action = self.audit_action or ActionLog.Action.BIBLIO_EDIT
                log_change(action, saved, before)
                messages.success(request, "Saqlandi.")
            if 'save_and_new' in request.POST:
                return redirect(self.url('create'))
            back = request.POST.get('next', '')
            if back and url_has_allowed_host_and_scheme(back, {request.get_host()},
                                                        request.is_secure()):
                return redirect(back)
            return redirect(self.url())
        heading = f"{self.label.capitalize()}ni tahrirlash" if obj else f"Yangi {self.label}"
        return render(request, 'panel/crud/form.html', self._context(
            request, form=form, object=obj, page_title=heading, list_url=self.url()))

    def _delete(self, request, pk):
        obj = get_object_or_404(self.queryset(), pk=pk)
        blocker = self.blocker(obj)
        if request.method == 'POST' and not blocker:
            name = str(obj)
            try:
                with transaction.atomic():
                    self.log('DELETE', obj)
                    obj.delete()
            except (ProtectedError, IntegrityError):
                messages.error(request, "Bog'langan yozuvlar bor — o'chirib bo'lmadi.")
            else:
                messages.success(request, f"«{name}» o'chirildi.")
            return redirect(self.url())
        return render(request, 'panel/crud/delete.html', self._context(
            request, object=obj, blocker=blocker, list_url=self.url(),
            merge_url=self.url('merge', obj.pk) if self.merge else '',
            page_title=f"{self.label.capitalize()}ni o'chirish"))

    def _merge(self, request, pk):
        source = get_object_or_404(self.queryset(), pk=pk)
        query = (request.POST.get('q') or request.GET.get('q') or '').strip()

        target_pk = request.POST.get('target', '')
        if request.method == 'POST' and target_pk.isdigit() and int(target_pk) != source.pk:
            target = get_object_or_404(self.model, pk=target_pk)
            name = str(source)
            with transaction.atomic():
                log_action(self.audit_action or ActionLog.Action.BIBLIO_EDIT, obj=target,
                           note=f"Birlashtirildi: «{name}» (#{source.pk}) -> «{target}»")
                self.merge(source, target)
            messages.success(request, f"«{name}» «{target}» bilan birlashtirildi.")
            return redirect(self.url())

        # Taklif: so'rov bo'yicha, bo'lmasa nomning eng uzun so'zi bo'yicha o'xshashlar
        words = sorted(str(source).split(), key=len, reverse=True)
        guess = query or (words[0] if words else '')
        candidates = self.filtered(guess).exclude(pk=source.pk)[:20]
        return render(request, 'panel/crud/merge.html', self._context(
            request, object=source, candidates=candidates, q=guess, list_url=self.url(),
            page_title=f"{self.label.capitalize()}ni birlashtirish"))

    def urls(self):
        @require_perm(self.view_perm)
        def list_view(request):
            if wants_csv(request):
                return self._export(request)
            return render_partial_or_page(
                request, 'panel/crud/list.html', 'panel/crud/_table.html',
                self._list_context(request))

        @require_perm(self.edit_perm)
        def create_view(request):
            return self._form(request)

        @require_perm(self.edit_perm)
        def edit_view(request, pk):
            return self._form(request, get_object_or_404(self.model, pk=pk))

        @require_perm(self.delete_perm)
        def delete_view(request, pk):
            return self._delete(request, pk)

        routes = [
            path(f'{self.name}/', list_view, name=self.name),
            path(f'{self.name}/new/', create_view, name=f'{self.single}_create'),
            path(f'{self.name}/<int:pk>/edit/', edit_view, name=f'{self.single}_edit'),
            path(f'{self.name}/<int:pk>/delete/', delete_view, name=f'{self.single}_delete'),
        ]

        if self.toggle:
            @require_POST
            @require_perm(self.edit_perm)
            def toggle_view(request, pk):
                obj = get_object_or_404(self.model, pk=pk)
                setattr(obj, self.toggle, not getattr(obj, self.toggle))
                obj.save(update_fields=[self.toggle])
                state = "yoqildi" if getattr(obj, self.toggle) else "o'chirib qo'yildi"
                self.log('EDIT', obj, note=state)
                response = render(request, 'panel/crud/_table.html', self._list_context(request))
                return toast(response, f"«{obj}» {state}.")

            routes.append(path(f'{self.name}/<int:pk>/toggle/', toggle_view,
                               name=f'{self.single}_toggle'))

        if self.merge:
            # Birlashtirish yozuvni o'chiradi — shuning uchun o'chirish ruxsati
            @require_perm(self.delete_perm)
            def merge_view(request, pk):
                return self._merge(request, pk)

            routes.append(path(f'{self.name}/<int:pk>/merge/', merge_view,
                               name=f'{self.single}_merge'))
        return routes
