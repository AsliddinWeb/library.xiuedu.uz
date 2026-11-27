from django.shortcuts import redirect

from user_app.permissions import Perms, require_perm


@require_perm(Perms.REPORTS_VIEW)
def analytics(request):
    # Eski sahifa — endi kutubxonachi paneli (/panel/analytics/) bilan almashtirildi
    return redirect('panel:analytics')
