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

        code = request.GET.get('code')
        if code is None: return JsonResponse({'error': 'code is missing!'})

        client = oAuth2Client(
            client_id = settings.CLIENT_ID,
            client_secret = settings.CLIENT_SECRET,
            redirect_uri = settings.REDIRECT_URI,
            authorize_url = settings.AUTHORIZE_URL,
            token_url = settings.ACCESS_TOKEN_URL,
            resource_owner_url = settings.RESOURCE_OWNER_URL
        )
        access_token_response = client.get_access_token(code)

        full_info = {}
        if 'access_token' in access_token_response:
            access_token = access_token_response['access_token']
            user_details = client.get_user_details(access_token)
            full_info['details'] = user_details
            full_info['token'] = access_token
            return JsonResponse(full_info)
        else:
            return JsonResponse(
                {
                    'status': False,
                    'error': 'Failed to obtain access token'
                },
                status=400
            )