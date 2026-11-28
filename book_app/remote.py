"""
Universitet kitoblar bazasidagi muqova va PDF'larni yuklash.

Xavfsizlik: faqat `ARM_API_URL` serveridan olinadi (manzil bazadan yoki
formadan kelsa ham boshqa serverga so'rov yuborilmaydi), yo'naltirishga
ergashilmaydi, hajm cheklangan va fayl turi mazmunidan tekshiriladi.
"""
import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.files import File
from django.db import connection
from PIL import Image

from core import background

from .models import Book

logger = logging.getLogger('arm')

MAX_PDF = 300 * 1024 * 1024
MAX_COVER = 10 * 1024 * 1024
TIMEOUT = (10, 60)
IMAGE_TYPES = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}
#: pg_advisory_lock sinfi ("ARMF"); ikkinchi kalit — kitob raqami
LOCK_CLASS = 0x41524D46


class FetchError(Exception):
    """Foydalanuvchiga ko'rsatsa bo'ladigan xato matni."""


def source_url(url) -> str:
    """Manba serveriga tegishli manzil (kerak bo'lsa https'ga o'tkazilgan) yoki ''."""
    parts = urlsplit(str(url or '').strip())
    source = urlsplit(settings.ARM_API_URL)
    if parts.scheme not in ('http', 'https') or parts.hostname != source.hostname:
        return ''
    return urlunsplit((source.scheme, source.netloc, parts.path, parts.query, ''))


def free_bytes() -> int:
    root = Path(settings.MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(root).free


def has_room() -> bool:
    return free_bytes() > settings.MEDIA_MIN_FREE_GB * 1024 ** 3


def local_file(address):
    """arm-admin shu serverda bo'lsa — manzilga mos fayl yo'li, aks holda `None`."""
    root = Path(settings.ARM_MEDIA_ROOT)
    path = unquote(urlsplit(address).path)
    if not root.is_dir() or not path.startswith('/media/'):
        return None
    root = root.resolve()
    candidate = (root / path[len('/media/'):]).resolve()
    # «../» bilan papkadan tashqariga chiqib bo'lmaydi
    if root not in candidate.parents:
        raise FetchError("Fayl manzili noto'g'ri.")
    return candidate


def download(url, max_bytes):
    """Faylni ochiq holda qaytaradi: lokal papkadan yoki manba serveridan yuklab."""
    address = source_url(url)
    if not address:
        raise FetchError("Manzil universitet kitoblar bazasiniki emas.")
    local = local_file(address)
    if local is not None:
        if not local.is_file():
            raise FetchError("Fayl arm-admin papkasida topilmadi.")
        if local.stat().st_size > max_bytes:
            raise FetchError("Fayl juda katta.")
        return local.open('rb')
    target = tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024)  # noqa: SIM115
    try:
        with requests.get(address, stream=True, timeout=TIMEOUT, allow_redirects=False) as response:
            if response.status_code != 200:
                raise FetchError(f"Manba {response.status_code} javobini qaytardi.")
            size = 0
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError("Fayl juda katta.")
                target.write(chunk)
    except requests.RequestException as exc:
        target.close()
        raise FetchError(f"Manbaga ulanib bo'lmadi ({type(exc).__name__}).") from exc
    except FetchError:
        target.close()
        raise
    target.seek(0)
    return target


def fetch_cover(url):
    """`(fayl, kengaytma)` — mazmuni haqiqatan rasm bo'lsa."""
    data = download(url, MAX_COVER)
    try:
        with Image.open(data) as image:
            kind = image.format
            image.verify()
    except Exception as exc:
        raise FetchError("Muqova fayli rasm emas.") from exc
    if kind not in IMAGE_TYPES:
        raise FetchError("Muqova rasm turi qo'llanmaydi.")
    data.seek(0)
    return data, IMAGE_TYPES[kind]


def save_cover(book_id, data, extension):
    book = Book.objects.only('id', 'cover_image').get(pk=book_id)
    book.cover_image.save(f'arm-{book_id}.{extension}', File(data), save=False)
    Book.objects.filter(pk=book_id).update(cover_image=book.cover_image.name)


def save_ebook(book):
    """`remote_file_url` dagi PDF'ni serverga saqlaydi."""
    data = download(book.remote_file_url, MAX_PDF)
    if data.read(5) != b'%PDF-':
        raise FetchError("Manbadagi fayl PDF emas.")
    data.seek(0)
    book.electronic_version.save(f'arm-{book.pk}.pdf', File(data), save=False)
    Book.objects.filter(pk=book.pk).update(
        electronic_version=book.electronic_version.name, remote_file_error='')


@contextmanager
def _book_lock(book_id):
    if connection.vendor != 'postgresql':
        yield True
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s, %s)', [LOCK_CLASS, book_id])
        locked = cursor.fetchone()[0]
    try:
        yield locked
    finally:
        if locked:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s, %s)', [LOCK_CLASS, book_id])


def fetch_ebook(book_id):
    """Bitta kitobning faylini yuklaydi; xato kitob yozuviga tushadi."""
    with _book_lock(book_id) as locked:
        if not locked:
            return                      # boshqa so'rov hozir yuklayapti
        book = Book.objects.get(pk=book_id)
        if book.electronic_version or not book.remote_file_url:
            return
        try:
            if not has_room():
                raise FetchError("Serverda joy tugayapti — administratorga xabar bering.")
            save_ebook(book)
        except FetchError as exc:
            Book.objects.filter(pk=book_id).update(remote_file_error=str(exc)[:200])
        except Exception:
            logger.exception("Kitob faylini saqlab bo'lmadi: book=%s", book_id)
            Book.objects.filter(pk=book_id).update(remote_file_error="Faylni saqlab bo'lmadi.")


def start_ebook_fetch(book):
    """O'quvchi kutib qolmasin — yuklash fonda ketadi."""
    return background.in_thread(fetch_ebook, book.pk)
