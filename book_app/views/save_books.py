from django.shortcuts import redirect

from user_app.utils import library_admin_role_required


@library_admin_role_required
def save_books(request):
    # Eski import sahifasi — endi kutubxonachi paneli (/panel/import/) bilan almashtirildi
    return redirect('panel:import_books')
