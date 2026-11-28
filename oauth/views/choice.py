"""
Kirish turini tanlash: talaba (student.xiuedu.uz) yoki xodim (hemis.xiuedu.uz).

Himoyalangan sahifaga kirmagan odam shu yerga tushadi (`LOGIN_URL`) — avval
hamma talaba HEMIS'iga yuborilardi va xodim kira olmasdi.
"""
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from user_app.roles import home_url

__all__ = ['LoginChoiceView']

#: Kirgandan keyin qaytiladigan manzil sessiyada shu kalit bilan saqlanadi
NEXT_KEY = 'login_next'


class LoginChoiceView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(home_url(request.user))

        next_url = request.GET.get('next', '')
        # Tashqi saytga yo'naltirib yuborilmasin
        if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            request.session[NEXT_KEY] = next_url
        else:
            request.session.pop(NEXT_KEY, None)
        return render(request, 'oauth/login.html')
