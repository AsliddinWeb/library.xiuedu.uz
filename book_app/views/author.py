from django.shortcuts import redirect

from user_app.utils import library_admin_role_required

# Eski muallif sahifalari — endi kutubxonachi paneli (/panel/authors/) bilan almashtirildi.


@library_admin_role_required
def authors_list(request):
    return redirect('panel:authors')


@library_admin_role_required
def author_create(request):
    return redirect('panel:author_create')


@library_admin_role_required
def author_edit(request, author_id):
    return redirect('panel:author_edit', pk=author_id)


@library_admin_role_required
def author_delete(request, author_id):
    return redirect('panel:author_delete', pk=author_id)
