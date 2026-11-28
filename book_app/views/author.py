from django.shortcuts import redirect

from user_app.permissions import Perms, require_perm

# Eski muallif sahifalari — endi kutubxonachi paneli (/panel/authors/) bilan almashtirildi.


@require_perm(Perms.CATALOG_VIEW)
def authors_list(request):
    return redirect('panel:authors')


@require_perm(Perms.CATALOG_EDIT)
def author_create(request):
    return redirect('panel:author_create')


@require_perm(Perms.CATALOG_EDIT)
def author_edit(request, author_id):
    return redirect('panel:author_edit', pk=author_id)


@require_perm(Perms.CATALOG_DELETE)
def author_delete(request, author_id):
    return redirect('panel:author_delete', pk=author_id)
