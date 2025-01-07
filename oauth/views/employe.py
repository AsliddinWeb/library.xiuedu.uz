from django.shortcuts import redirect
from django.views import View
from django.http import JsonResponse
from oauth.client import oAuth2Client
from django.conf import settings

class EmployeAuthLoginView(View):
    def get(self, request):
        client = oAuth2Client(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            redirect_uri=settings.REDIRECT_URI,
            authorize_url=settings.EMPLOYE_AUTHORIZE_URL,
            token_url=settings.EMPLOYE_ACCESS_TOKEN_URL,
            resource_owner_url=settings.EMPLOYE_RESOURCE_OWNER_URL
        )

        # Get the authorization URL for employee login
        authorization_url = client.get_authorization_url()

        # Set a cookie indicating this is an employee login request
        response = JsonResponse({'authorization_url': authorization_url})
        response.set_cookie('user_type', 'employee', max_age=3600)  # Cookie expires in 1 hour

        return response
