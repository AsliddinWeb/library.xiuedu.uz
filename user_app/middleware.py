"""
Xodim hududini yopib turadigan qo'shimcha qulf.

Har bir view o'z ruxsatini `require_perm` bilan tekshiradi. Bu middleware esa
"dekorator unutilib qolgan" holatdan himoya qiladi: `/panel/` ostidagi hech bir
sahifa mehmon yoki o'quvchiga ochilmaydi.
"""
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render

from .roles import is_library_staff

STAFF_PREFIXES = ('/panel/', '/_design/')


class StaffAreaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(STAFF_PREFIXES):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not is_library_staff(request.user):
                return render(request, '403.html', status=403)
        return self.get_response(request)
