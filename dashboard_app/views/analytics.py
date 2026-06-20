from django.shortcuts import redirect

from user_app.utils import library_admin_role_required


@library_admin_role_required
def analytics(request):
    # Eski sahifa — endi kutubxonachi paneli (/panel/analytics/) bilan almashtirildi
    return redirect('panel:analytics')
