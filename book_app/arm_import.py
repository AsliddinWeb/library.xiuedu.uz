"""
Universitet kitoblar bazasidan (arm-admin) katalogga import.

Qoidalar:
  * qayta ishga tushirish xavfsiz: manbadagi har yozuv `ExternalRecord` bilan
    kitobga bog'lanadi va ikkinchi marta kitob ochilmaydi;
  * katalogda bor kitob nom, yil va muallif bo'yicha topiladi (kirill va lotin
    yozuvi bir xil hisoblanadi) — nusxa ochilmaydi, faqat bo'sh maydonlari to'ladi;
  * nomi bir xil, lekin fayli boshqa yozuvlar alohida kitob (jild, nashr);
  * kutubxonachi kiritgan ma'lumot ustiga yozilmaydi, hech narsa o'chirilmaydi;
  * PDF standart holda ko'chirilmaydi — o'quvchi birinchi ochganda yuklanadi.

«Solishtirish» rejimi (`dry`) hech narsa yozmasdan natijani sanaydi.
"""
import json
import logging
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from django.utils.timezone import now

from audit.models import JobRun
from core import background
from core.autojobs import exclusive

from . import remote
from .models import Author, Book, ExternalRecord, Genre
from .translit import normalize

logger = logging.getLogger('arm')

JOB_NAME = 'arm_import'
SOURCE = 'arm'
#: pg_advisory_lock kaliti ("ARM1")
LOCK_KEY = 0x41524D31
ATTEMPTS = 4
TIMEOUT = 60
#: Manbani charchatmaslik uchun sahifalar orasidagi eng kam vaqt
MIN_INTERVAL = 0.2
COVER_WORKERS = 4
SAMPLES = 8
DEFAULT_CATEGORY = "Boshqa"


class SourceError(Exception):
    """Xodimga ko'rsatsa bo'ladigan xato matni."""


class ArmClient:
    def __init__(self, url=None, session=None, sleep=time.sleep):
        self.url = url or settings.ARM_API_URL
        self.session = session or requests.Session()
        self.sleep = sleep
        self._last = 0.0

    def page(self, number):
        """Sahifa: `{'count', 'next', 'results'}`; sahifalar tugagan bo'lsa `None`."""
        problem = ''
        for attempt in range(ATTEMPTS):
            if attempt:
                self.sleep(2 ** attempt)
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            try:
                response = self.session.get(self.url, params={'page': number}, timeout=TIMEOUT)
            except requests.RequestException as exc:
                problem = f"Manba bilan bog'lanib bo'lmadi ({type(exc).__name__})."
                continue
            if response.status_code == 404 and number > 1:
                return None
            if response.status_code == 429 or response.status_code >= 500:
                problem = f"Manba vaqtincha javob bermayapti ({response.status_code})."
                continue
            if response.status_code == 403:
                # Manba serveri ayrim mijozlarni bloklaydi. Bu to'siq chetlab o'tilmaydi:
                # ruxsatni manba administratori beradi.
                raise SourceError(
                    "Manba server kutubxonaga ruxsat bermadi (403). arm-admin administratori "
                    "kutubxona serverining IP manzilini ruxsat ro'yxatiga qo'shishi kerak.")
            if response.status_code != 200:
                raise SourceError(f"Manba kutilmagan javob qaytardi ({response.status_code}).")
            try:
                data = response.json()
            except ValueError:
                raise SourceError("Manba JSON o'rniga boshqa javob qaytardi.") from None
            if not isinstance(data, dict) or not isinstance(data.get('results'), list):
                raise SourceError("Manba javobida kitoblar ro'yxati yo'q — API o'zgargan bo'lishi mumkin.")
            return data
        raise SourceError(problem)


class FileClient:
    """`bin/arm_export.py` yozgan fayl — arm-admin shu serverda bo'lganda."""

    PAGE_SIZE = 200

    def __init__(self, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            rows = data['results']
            if not isinstance(rows, list):
                raise TypeError
        except (OSError, ValueError, KeyError, TypeError):
            raise SourceError("Eksport faylini o'qib bo'lmadi — uni qaytadan yarating.") from None
        self.rows = [self._addressed(row) for row in rows]

    @staticmethod
    def _addressed(row):
        """Nisbiy fayl yo'llarini manba manziliga aylantiradi (API bergani kabi)."""
        if not isinstance(row, dict):
            return row
        source = urlsplit(settings.ARM_API_URL)
        row = dict(row)
        for key in ('source', 'photo'):
            name = row.get(key)
            if name and '://' not in name:
                row[key] = f"{source.scheme}://{source.netloc}/media/{quote(name.lstrip('/'))}"
        return row

    def page(self, number):
        start = (number - 1) * self.PAGE_SIZE
        chunk = self.rows[start:start + self.PAGE_SIZE]
        if not chunk and number > 1:
            return None
        return {'count': len(self.rows), 'results': chunk,
                'next': start + len(chunk) < len(self.rows)}


def default_client():
    """Eksport fayli bor bo'lsa — undan, bo'lmasa API'dan."""
    path = Path(settings.ARM_EXPORT_FILE)
    return FileClient(path) if path.is_file() else ArmClient()


# --------------------------------------------------------------------------
#  Manba yozuvi
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Record:
    external_id: str
    title: str
    authors: tuple
    category: str
    year: int | None
    description: str
    file_url: str
    cover_url: str
    updated_at: str


def _clean(value, limit=None):
    text = ' '.join(str(value or '').split())
    return text[:limit] if limit else text


def _authors(value):
    """Bir maydondagi bir nechta muallifni ajratadi.

    «Р.Расулов ,С.Атиязов» — ikki kishi; «Qodiriy, Abdulla» — bitta (bo'laklarda
    na bo'sh joy, na bosh harf nuqtasi bor).
    """
    names = []
    for chunk in str(value or '').split(';'):
        parts = [_clean(part) for part in chunk.split(',') if _clean(part)]
        if len(parts) > 1 and all(' ' in part or '.' in part for part in parts):
            names += parts
        elif parts:
            names.append(', '.join(parts))
    return tuple(name[:200] for name in names)


def _field(block, *names):
    block = block if isinstance(block, dict) else {}
    return next((block[name] for name in names if block.get(name)), '')


def parse(raw):
    """Manbadagi yozuv; ID yoki nomi bo'lmasa `None`."""
    if not isinstance(raw, dict) or raw.get('id') in (None, ''):
        return None
    title = _clean(_field(raw, 'title', 'title_uz', 'title_ru', 'title_en'), 500)
    if not title:
        return None
    try:
        year = int(str(raw.get('year')).strip())
    except (TypeError, ValueError):
        year = None
    if year is not None and not 1000 <= year <= now().year + 1:
        year = None
    file_url = remote.source_url(raw.get('source'))
    if not file_url.split('?')[0].lower().endswith('.pdf') or len(file_url) > 500:
        file_url = ''
    return Record(
        external_id=str(raw['id'])[:40], title=title,
        authors=_authors(_field(raw.get('author'), 'name', 'name_uz', 'name_ru')),
        category=_clean(_field(raw.get('category'), 'title', 'title_uz', 'title_ru'), 100)
        or DEFAULT_CATEGORY,
        year=year,
        description=str(_field(raw, 'description', 'description_uz', 'description_ru')).strip(),
        file_url=file_url, cover_url=remote.source_url(raw.get('photo')),
        updated_at=str(raw.get('updated_at') or '')[:40])


# --------------------------------------------------------------------------
#  Katalogda bor kitobni topish
# --------------------------------------------------------------------------

def _person(name):
    """Ism so'zlari to'plami: «Yusupova Dilnavoz» va «Дилнавоз Юсупова» bir xil."""
    return frozenset(normalize(name).split())


def _surnames(names):
    """Mualliflarni solishtirish uchun so'zlar (bosh harflarsiz).

    Eski import bir nechta muallifni bitta nom qilib yozgan bo'lishi mumkin,
    shuning uchun kishilar emas, ism so'zlari solishtiriladi.
    """
    return {word for name in names for word in _person(name) if len(word) > 2}


@dataclass
class Candidate:
    book_id: int | None
    people: set = field(default_factory=set)
    files: set = field(default_factory=set)


class Index:
    def __init__(self):
        self.titles = defaultdict(list)
        self.books = {}

    @classmethod
    def load(cls):
        index = cls()
        books = Book.objects.only('id', 'title', 'published_year').prefetch_related('authors')
        for book in books.order_by('pk').iterator(chunk_size=1000):
            index.add(book.pk, book.title, book.published_year,
                      [author.full_name for author in book.authors.all()])
        for book_id, url in (ExternalRecord.objects.filter(source=SOURCE)
                             .exclude(file_url='').values_list('book_id', 'file_url')):
            if book_id in index.books:
                index.books[book_id].files.add(url)
        return index

    def add(self, book_id, title, year, authors, file_url=''):
        candidate = self.books.get(book_id) if book_id else None
        if candidate is None:
            candidate = Candidate(book_id, _surnames(authors))
            self.titles[(normalize(title), year)].append(candidate)
            if book_id:
                self.books[book_id] = candidate
        if file_url:
            candidate.files.add(file_url)
        return candidate

    def find(self, record):
        title = normalize(record.title)
        people = _surnames(record.authors)
        keys = [(title, record.year)]
        if record.year is not None:
            keys.append((title, None))           # katalogda yili yozilmagan kitob
        for key in keys:
            for candidate in self.titles.get(key, ()):
                # Fayli boshqa yozuv allaqachon bog'langan — bu boshqa jild yoki nashr
                if candidate.files and record.file_url and record.file_url not in candidate.files:
                    continue
                if people and candidate.people and not people & candidate.people:
                    continue
                return candidate
        return None


# --------------------------------------------------------------------------
#  Yozish
# --------------------------------------------------------------------------

class Writer:
    def __init__(self):
        self.authors = {}
        for pk, name in Author.objects.order_by('pk').values_list('pk', 'full_name'):
            self.authors.setdefault(_person(name), pk)
        self.genres = {}
        for pk, name in Genre.objects.order_by('-is_active', 'pk').values_list('pk', 'name'):
            self.genres.setdefault(normalize(name), pk)

    def _author(self, name):
        key = _person(name)
        pk = self.authors.get(key)
        if pk is None or not Author.objects.filter(pk=pk).exists():
            pk = self.authors[key] = Author.objects.create(full_name=name).pk
        return pk

    def _genre(self, name):
        key = normalize(name)
        pk = self.genres.get(key)
        if pk is None or not Genre.objects.filter(pk=pk).exists():
            pk = self.genres[key] = Genre.objects.create(name=name).pk
        return pk

    def create(self, record):
        book = Book.objects.create(
            title=record.title, category_id=self._genre(record.category),
            published_year=record.year, description=record.description,
            remote_file_url=record.file_url,
            reading_mode=(Book.ReadingMode.DIGITAL if record.file_url
                          else Book.ReadingMode.PHYSICAL))
        if record.authors:
            book.authors.set([self._author(name) for name in record.authors])
        book.slug = f"{slugify(book.title)[:280] or 'kitob'}-{book.pk}"
        book.save()
        return book

    def fill(self, book, record, previous_url=''):
        """Bo'sh maydonlarni to'ldiradi; o'zgargan bo'lsa `True`."""
        changed = []
        if not book.published_year and record.year:
            book.published_year = record.year
            changed.append('published_year')
        if not (book.description or '').strip() and record.description:
            book.description = record.description
            changed.append('description')
        replaced = bool(previous_url) and book.remote_file_url == previous_url
        if (record.file_url and not book.electronic_version
                and book.remote_file_url != record.file_url
                and (not book.remote_file_url or replaced)):
            book.remote_file_url = record.file_url
            book.remote_file_error = ''
            changed += ['remote_file_url', 'remote_file_error']
            if book.reading_mode == Book.ReadingMode.PHYSICAL:
                book.reading_mode = (Book.ReadingMode.BOTH if book.items_count
                                     else Book.ReadingMode.DIGITAL)
                changed.append('reading_mode')
        if changed:
            book.save(update_fields=changed + ['updated_at'])
        added = False
        if record.authors and not book.authors.exists():
            book.authors.set([self._author(name) for name in record.authors])
            book.save()                              # qidiruv indeksi yangilansin
            added = True
        return bool(changed) or added


# --------------------------------------------------------------------------
#  Import
# --------------------------------------------------------------------------

class Importer:
    def __init__(self, *, dry=False, covers=True, files=False):
        self.dry, self.covers, self.files = dry, covers and not dry, files and not dry
        self.stats = Counter(dry=int(dry), done=0, new=0, linked=0, updated=0, same=0,
                             skipped=0, failed=0)
        self.samples = {'new': [], 'linked': []}
        self.index = Index.load()
        self.known = {row.external_id: row
                      for row in ExternalRecord.objects.filter(source=SOURCE)}
        self.writer = None if dry else Writer()
        self.without_cover = set(
            Book.objects.filter(Q(cover_image='') | Q(cover_image__isnull=True))
            .values_list('pk', flat=True))

    @transaction.atomic
    def _record(self, record):
        """('new' | 'linked' | 'updated' | 'same', kitob raqami)."""
        known = self.known.get(record.external_id)
        if known:
            if (known.source_updated_at, known.file_url) == (record.updated_at, record.file_url):
                return 'same', known.book_id
            if self.dry:
                return 'updated', known.book_id
            book = Book.objects.get(pk=known.book_id)
            filled = self.writer.fill(book, record, previous_url=known.file_url)
            known.source_updated_at, known.file_url = record.updated_at, record.file_url
            known.save(update_fields=['source_updated_at', 'file_url', 'updated_at'])
            return ('updated' if filled else 'same'), book.pk

        match = self.index.find(record)
        if match:
            result, book_id = 'linked', match.book_id
            if not self.dry:
                self.writer.fill(Book.objects.get(pk=book_id), record)
        else:
            result, book_id = 'new', None
            if not self.dry:
                book_id = self.writer.create(record).pk

        if not self.dry:
            self.known[record.external_id] = ExternalRecord.objects.create(
                book_id=book_id, source=SOURCE, external_id=record.external_id,
                file_url=record.file_url, source_updated_at=record.updated_at)
        if match and not match.book_id:          # shu o'tishdagi takror (solishtirish)
            if record.file_url:
                match.files.add(record.file_url)
        else:
            self.index.add(book_id, record.title, record.year, record.authors, record.file_url)
        if result == 'new' and book_id:
            self.without_cover.add(book_id)
        return result, book_id

    def page(self, rows):
        covers, files = {}, []
        for raw in rows:
            record = parse(raw)
            self.stats['done'] += 1
            if record is None:
                self.stats['skipped'] += 1
                continue
            try:
                result, book_id = self._record(record)
            except Exception:
                self.stats['failed'] += 1
                if self.stats['failed'] <= 5:
                    logger.exception("Kitobni import qilib bo'lmadi: id=%s", record.external_id)
                # Bekor qilingan tranzaksiyada keshga tushgan yozuvlar qolmasin
                self.known.pop(record.external_id, None)
                if self.writer:
                    self.writer = Writer()
                continue
            self.stats[result] += 1
            if result in self.samples and len(self.samples[result]) < SAMPLES:
                self.samples[result].append([record.title[:90], book_id])
            if book_id:
                if self.covers and record.cover_url and book_id in self.without_cover:
                    covers[book_id] = record.cover_url
                if self.files and record.file_url:
                    files.append(book_id)
        self._covers(covers)
        self._files(files)

    def _covers(self, wanted):
        if not wanted:
            return
        if not remote.has_room():
            self.covers, self.stats['disk_full'] = False, 1
            return

        def fetch(entry):
            try:
                return entry[0], remote.fetch_cover(entry[1])
            except remote.FetchError:
                return entry[0], None

        # Oqimlar faqat tarmoqdan oladi; bazaga shu oqimda yoziladi
        with ThreadPoolExecutor(max_workers=COVER_WORKERS) as pool:
            for book_id, result in pool.map(fetch, wanted.items()):
                try:
                    if result is None:
                        raise remote.FetchError('muqova olinmadi')
                    remote.save_cover(book_id, *result)
                except Exception:
                    self.stats['cover_failed'] += 1
                    continue
                self.without_cover.discard(book_id)
                self.stats['covers'] += 1

    def _files(self, book_ids):
        for book in Book.objects.filter(pk__in=book_ids).exclude(remote_file_url=''):
            if not self.files:
                return
            if book.electronic_version:
                continue
            if not remote.has_room():
                self.files, self.stats['disk_full'] = False, 1
                return
            try:
                remote.save_ebook(book)
            except Exception:
                self.stats['file_failed'] += 1
                continue
            self.stats['files'] += 1

    def snapshot(self):
        return {**self.stats, 'samples': self.samples}


def run(*, dry=False, covers=True, files=False, progress=lambda stats: False,
        client=None, max_pages=None):
    """Importni shu oqimda bajaradi va hisoblagichlarni qaytaradi."""
    client = client or default_client()
    with exclusive(LOCK_KEY) as locked:
        if not locked:
            raise SourceError("Boshqa import hozir ishlayapti.")
        importer = Importer(dry=dry, covers=covers, files=files)
        number = 1
        while True:
            data = client.page(number)
            if data is None:
                break
            importer.stats['total'] = data.get('count') or 0
            importer.page(data['results'])
            importer.stats['page'] = number
            if progress(importer.snapshot()):
                importer.stats['stopped'] = 1
                break
            if not data.get('next') or not data['results'] or number == max_pages:
                break
            number += 1
        return importer.snapshot()


def summary(stats):
    head = "Solishtirildi" if stats.get('dry') else "Import"
    if stats.get('stopped'):
        head += " (to'xtatildi)"
    parts = [f"yangi {stats.get('new', 0)}", f"katalogda bor {stats.get('linked', 0)}",
             f"yangilandi {stats.get('updated', 0)}", f"xato {stats.get('failed', 0)}"]
    if stats.get('covers'):
        parts.append(f"muqova {stats['covers']}")
    if stats.get('files'):
        parts.append(f"PDF {stats['files']}")
    if stats.get('disk_full'):
        parts.append("diskda joy tugadi")
    return f"{head}: " + ', '.join(parts)


def execute(record, dry, covers, files):
    """`JobRun` yozuvini yuritib import qiladi (xato yozuvning o'ziga tushadi)."""
    try:
        stats = run(dry=dry, covers=covers, files=files, progress=background.reporter(record))
    except SourceError as exc:
        background.finish(record, JobRun.Status.FAILED, str(exc))
    except Exception as exc:
        logger.exception("Kitob importi xato bilan tugadi")
        background.finish(record, JobRun.Status.FAILED, f"Kutilmagan xato: {type(exc).__name__}")
    else:
        record.stats = stats
        background.finish(record, JobRun.Status.SUCCESS, summary(stats))


def start(*, dry, covers, files):
    """Fonda boshlaydi. Boshqa import ishlayotgan bo'lsa `None`."""
    return background.start(JOB_NAME, execute, dry, covers, files, dry=int(dry))
