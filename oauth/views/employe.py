from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View

from oauth.client import oAuth2Client


class EmployeAuthLoginView(View):
    def get(self, request):
        if not settings.EMPLOYE_AUTHORIZE_URL:
            return HttpResponse(
                "HEMIS oAuth (xodim) sozlanmagan. Lokal sinov uchun /admin orqali kiring.",
                status=503,
            )
        client = oAuth2Client(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            redirect_uri=settings.REDIRECT_URI,
            authorize_url=settings.EMPLOYE_AUTHORIZE_URL,
            token_url=settings.EMPLOYE_ACCESS_TOKEN_URL,
            resource_owner_url=settings.EMPLOYE_RESOURCE_OWNER_URL
        )

        # Talaba oqimi bilan izchil: to'g'ridan-to'g'ri HEMIS'ga yo'naltiramiz
        response = redirect(client.get_authorization_url())
        response.set_cookie('user_type', 'employee', max_age=3600)
        return response
