import requests
from urllib.parse import urlencode


class oAuth2Client:
    def __init__(self, client_id, client_secret, redirect_uri, authorize_url, token_url, resource_owner_url):
        self.client_secret = client_secret
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.resource_owner_url = resource_owner_url

    def get_authorization_url(self):
        payload = {
            'clientId': self.client_id,
            'clientSecret': self.client_secret,
            'redirectUri': self.redirect_uri,
            'grand_type': 'authorization_code'
            # 'urlAccessToken': self.token_url,
            # 'urlResourceOwnerDetails': self.resource_owner_url,
        }

        url = self.authorize_url + "?" + urlencode(payload)

        return url

    def get_access_token(self, auth_code):
        print("A"*90)
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': auth_code,
            'redirect_uri': self.redirect_uri,
            # 'grant_type': 'authorization_code'
            'grant_type': 'one_code'
        }
        response = requests.post(self.token_url, data=payload)
        print(response.status_code)
        print(response.json())
        return response.json()

    def get_user_details(self, access_token):
        response = requests.get(self.resource_owner_url, headers={'Authorization': f'Bearer {access_token}'})
        return response.json()