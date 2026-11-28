from django.shortcuts import redirect

from user_app.permissions import Perms, require_perm


@require_perm(Perms.CATALOG_IMPORT)
def save_books(request):
    # Eski import sahifasi — endi kutubxonachi paneli (/panel/import/) bilan almashtirildi
    return redirect('panel:import_books')
