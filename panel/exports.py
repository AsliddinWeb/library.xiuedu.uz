"""
CSV eksport — Excel'da to'g'ri ochiladigan ko'rinishda.

UTF-8 BOM va `;` ajratuvchi: o'zbek/rus sozlamali Excel faylni ustunlarga
o'zi bo'ladi va kirill/lotin harflarini buzmaydi.
"""
import csv

from django.http import HttpResponse
from django.utils.timezone import localtime, now

from audit.models import ActionLog
from audit.services import log_action
from user_app.permissions import Perms, has_perm

#: Excel katak boshidagi bu belgilarni formula deb o'qiydi
_FORMULA_STARTS = ('=', '+', '-', '@', '\t', '\r')


def wants_csv(request):
    return request.GET.get('export') == 'csv' and has_perm(request.user, Perms.REPORTS_EXPORT)


def _cell(value):
    if value is None:
        return ''
    if hasattr(value, 'hour'):
        return localtime(value).strftime('%d.%m.%Y %H:%M')
    if hasattr(value, 'strftime'):
        return value.strftime('%d.%m.%Y')
    if isinstance(value, str) and value.startswith(_FORMULA_STARTS):
        return "'" + value
    return value


def csv_response(request, name, header, rows):
    """`rows` — qatorlar iteratori. Har eksport audit jurnaliga yoziladi."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"{name}-{now():%Y%m%d-%H%M}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('﻿')

    writer = csv.writer(response, delimiter=';')
    writer.writerow(header)
    count = 0
    for row in rows:
        writer.writerow([_cell(value) for value in row])
        count += 1

    log_action(ActionLog.Action.EXPORT, actor=request.user, note=f"{filename}: {count} qator")
    return response
