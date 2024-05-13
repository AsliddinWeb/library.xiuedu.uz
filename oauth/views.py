from django.views import View
from django.http import JsonResponse

from .client import oAuth2Client
from django.conf import settings


class AuthLoginView(View):
    def get(self, request):
        client = oAuth2Client(
            client_id = settings.CLIENT_ID,
            client_secret = settings.CLIENT_SECRET,
            redirect_uri = settings.REDIRECT_URI,
            authorize_url = settings.AUTHORIZE_URL,
            token_url = settings.ACCESS_TOKEN_URL,
            resource_owner_url = settings.RESOURCE_OWNER_URL
        )
        authorization_url = client.get_authorization_url()

        return JsonResponse({'authorization_url': authorization_url})


class AuthCallbackView(View):
    def get(self, request):

        params = request.GET

        return JsonResponse({'code': params.get('code')})