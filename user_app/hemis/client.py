"""
HEMIS «Backend API» (`/rest/v1/data/...`) mijozi.

Hujjat (HEMIS UNIVERSITY API, 1-guruh) talablari:
  * `Authorization: Bearer <token>` — token HEMIS admin panelida «API User»
    roli berilgan foydalanuvchidan olinadi;
  * `limit` ko'pi bilan 200;
  * bitta IP'dan sekundiga 10 ta so'rovdan oshmasin;
  * faqat server tomondan chaqiriladi.

Token hech qachon jurnalga yoki xato matniga yozilmaydi.
"""
import time

import requests
from django.conf import settings

PAGE_SIZE = 200
#: Ikki so'rov orasidagi eng kam vaqt (sekundiga 10 ta chegarasidan pastda)
MIN_INTERVAL = 0.15
TIMEOUT = 60
ATTEMPTS = 4
#: Himoya: sahifalash ma'lumoti noto'g'ri kelsa ham aylanish tugaydi
MAX_PAGES = 2000


class HemisError(Exception):
    """Xodimga ko'rsatsa bo'ladigan xato matni."""


def _first(value):
    """Hujjatda ayrim bloklar massiv ichida ko'rsatilgan — ikkalasini qabul qilamiz."""
    if isinstance(value, list):
        value = value[0] if value else {}
    return value if isinstance(value, dict) else {}


class HemisClient:
    def __init__(self, token, base_url=None, session=None, sleep=time.sleep):
        token = (token or '').strip()
        if not token:
            raise HemisError("HEMIS tokeni kiritilmagan.")
        if not token.isascii() or any(char.isspace() for char in token):
            raise HemisError("Token noto'g'ri ko'rinishda: unda bo'sh joy yoki ortiqcha belgi bor.")
        self.base_url = (base_url or settings.HEMIS_API_URL).rstrip('/')
        self.session = session or requests.Session()
        self.headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        self.sleep = sleep
        self._last = 0.0

    def _throttle(self):
        wait = MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            self.sleep(wait)
        self._last = time.monotonic()

    def _get(self, path, params):
        url = f'{self.base_url}/{path}'
        problem = ''
        for attempt in range(ATTEMPTS):
            if attempt:
                self.sleep(2 ** attempt)
            self._throttle()
            try:
                response = self.session.get(url, params=params, headers=self.headers, timeout=TIMEOUT)
            except requests.RequestException as exc:
                problem = f"HEMIS bilan bog'lanib bo'lmadi ({type(exc).__name__})."
                continue

            if response.status_code in (401, 403):
                raise HemisError(
                    f"HEMIS tokenni qabul qilmadi ({response.status_code}). HEMIS admin panelida "
                    "«API User» roli bor foydalanuvchining tokeni kerak.")
            if response.status_code == 429 or response.status_code >= 500:
                problem = f"HEMIS vaqtincha javob bermayapti ({response.status_code})."
                continue
            if response.status_code != 200:
                raise HemisError(f"HEMIS kutilmagan javob qaytardi ({response.status_code}): {url}")

            try:
                payload = response.json()
            except ValueError:
                raise HemisError(f"HEMIS JSON o'rniga boshqa javob qaytardi: {url}") from None
            if not isinstance(payload, dict) or payload.get('success') is False:
                error = payload.get('error') if isinstance(payload, dict) else ''
                raise HemisError(f"HEMIS so'rovni rad etdi: {str(error)[:200]}")
            return payload
        raise HemisError(problem)

    def page(self, path, number=1, limit=PAGE_SIZE, **params):
        """Bitta sahifa: `(yozuvlar, sahifalash)`."""
        payload = self._get(path, {**params, 'page': number, 'limit': limit})
        data = _first(payload.get('data'))
        items = data.get('items')
        if not isinstance(items, list):
            raise HemisError("HEMIS javobida ro'yxat topilmadi — API o'zgargan bo'lishi mumkin.")
        return items, _first(data.get('pagination'))

    def pages(self, path, **params):
        """Barcha sahifalar bo'ylab `(yozuvlar, sahifalash)`."""
        for number in range(1, MAX_PAGES + 1):
            items, pagination = self.page(path, number, **params)
            if items:
                yield items, pagination
            last = pagination.get('pageCount')
            if not items or (last and number >= int(last)) or (not last and len(items) < PAGE_SIZE):
                return
