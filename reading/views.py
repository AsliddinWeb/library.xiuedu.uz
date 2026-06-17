import mimetypes
import re

from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import (FileResponse, Http404, StreamingHttpResponse,
                         JsonResponse)
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from book_app.models import Book
from .models import ReadingProgress, ReadingHistory

RANGE_RE = re.compile(r'bytes=(\d+)-(\d*)')


# --------------------------------------------------------------- himoyalangan stream

def _file_iterator(f, length, chunk=8192):
    remaining = length
    while remaining > 0:
        data = f.read(min(chunk, remaining))
        if not data:
            break
        remaining -= len(data)
        yield data


def _serve_protected(request, file_field):
    """Faylni inline (yuklab olmasdan) va Range bilan uzatadi."""
    if not file_field:
        raise Http404("Fayl mavjud emas.")
    try:
        size = file_field.size
        f = file_field.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404("Fayl topilmadi.")

    content_type = mimetypes.guess_type(file_field.name)[0] or 'application/octet-stream'
    range_header = request.headers.get('Range')

    if range_header:
        m = RANGE_RE.match(range_header)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            length = end - start + 1
            f.seek(start)
            resp = StreamingHttpResponse(_file_iterator(f, length), status=206, content_type=content_type)
            resp['Content-Range'] = f'bytes {start}-{end}/{size}'
            resp['Content-Length'] = str(length)
            resp['Accept-Ranges'] = 'bytes'
            resp['Content-Disposition'] = 'inline'
            return resp

    resp = FileResponse(f, content_type=content_type)
    resp['Accept-Ranges'] = 'bytes'
    resp['Content-Disposition'] = 'inline'
    return resp


@login_required
def stream_ebook(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return _serve_protected(request, book.electronic_version)


@login_required
def stream_audio(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return _serve_protected(request, book.audio_version)


# --------------------------------------------------------------- reader / player

def _open_book(request, book, mode):
    """Ko'rishni qayd qiladi va oxirgi joyni qaytaradi."""
    Book.objects.filter(pk=book.pk).update(view_count=F('view_count') + 1)
    ReadingHistory.objects.create(user=request.user, book=book)
    progress = ReadingProgress.objects.filter(user=request.user, book=book, mode=mode).first()
    return progress.position if progress else 0


@login_required
def read_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if not book.electronic_version:
        raise Http404("Bu kitobning elektron versiyasi yo'q.")
    start_page = int(_open_book(request, book, ReadingProgress.Mode.READ) or 0)
    return render(request, "reading/reader.html", {'book': book, 'start_page': start_page})


@login_required
def listen_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if not book.audio_version:
        raise Http404("Bu kitobning audio versiyasi yo'q.")
    start_sec = _open_book(request, book, ReadingProgress.Mode.LISTEN) or 0
    return render(request, "reading/player.html", {'book': book, 'start_sec': start_sec})


@require_POST
@login_required
def save_progress(request, pk):
    book = get_object_or_404(Book, pk=pk)
    mode = request.POST.get('mode', ReadingProgress.Mode.READ)
    if mode not in ReadingProgress.Mode.values:
        mode = ReadingProgress.Mode.READ
    try:
        position = float(request.POST.get('position', 0))
        percent = max(0, min(100, int(float(request.POST.get('percent', 0)))))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False}, status=400)

    ReadingProgress.objects.update_or_create(
        user=request.user, book=book, mode=mode,
        defaults={'position': position, 'percent': percent},
    )
    return JsonResponse({'ok': True})
