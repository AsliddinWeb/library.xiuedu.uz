"""Fan adabiyoti sahifalari (OPAC)."""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import courses
from ..citation import gost
from ..forms import CourseReserveForm
from ..models import Book, CourseReserve, CourseReserveItem
from ..search import search_books

__all__ = [
    'course_list', 'course_detail', 'course_create', 'course_edit', 'course_delete',
    'course_book_search', 'course_add_book', 'course_remove_book', 'course_update_item',
]

PER_PAGE = 24
SEARCH_LIMIT = 8


def _editable(request, pk):
    reserve = get_object_or_404(CourseReserve, pk=pk)
    if not courses.can_edit_reserve(request.user, reserve):
        raise Http404
    return reserve


@login_required
def course_list(request):
    query = request.GET.get('q', '').strip()
    faculty = request.GET.get('faculty', '').strip()
    semester = request.GET.get('semester', '').strip()
    filtered = bool(query or faculty or semester)

    reserves = courses.filter_reserves(courses.published_reserves(), query, faculty, semester)
    page_obj = Paginator(reserves, PER_PAGE).get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'query': query,
        'faculty': faculty,
        'semester': semester,
        'filtered': filtered,
        'faculties': courses.faculty_choices(),
        'semesters': [str(n) for n in range(1, 13)],
        'can_create': courses.can_create_reserve(request.user),
        'query_string': '&' + urlencode({'q': query, 'faculty': faculty, 'semester': semester}),
    }
    if not filtered:
        context['student_reserves'] = courses.reserves_for_student(request.user)[:12]
        if context['can_create']:
            context['own_reserves'] = courses.own_reserves(request.user)[:12]
    return render(request, 'opac/courses.html', context)


def _search_results(reserve, query):
    if not query:
        return []
    found = list(search_books(Book.objects.filter(is_active=True), query)
                 .prefetch_related('authors')[:SEARCH_LIMIT])
    taken = set(reserve.items.values_list('book_id', flat=True))
    for book in found:
        book.in_list = book.pk in taken
    return found


@login_required
def course_detail(request, pk):
    reserve = get_object_or_404(CourseReserve.objects.select_related('teacher'), pk=pk)
    can_edit = courses.can_edit_reserve(request.user, reserve)
    if not reserve.is_active and not can_edit:
        raise Http404

    items = list(reserve.items
                 .select_related('book__publisher', 'book__series')
                 .prefetch_related('book__authors'))
    required = CourseReserveItem.Importance.REQUIRED
    groups = [
        ("Asosiy adabiyotlar", [i for i in items if i.importance == required]),
        ("Qo'shimcha adabiyotlar", [i for i in items if i.importance != required]),
    ]
    book_query = request.GET.get('book_q', '').strip() if can_edit else ''

    return render(request, 'opac/course_detail.html', {
        'reserve': reserve,
        'items': items,
        'groups': [(title, group) for title, group in groups if group],
        'citations': [gost(item.book) for item in items],
        'can_edit': can_edit,
        'importance_choices': CourseReserveItem.Importance.choices,
        'book_query': book_query,
        'results': _search_results(reserve, book_query),
    })


def _course_form(request, reserve=None):
    form = CourseReserveForm(request.POST or None, instance=reserve, user=request.user,
                             curator=courses.is_curator(request.user))
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, "Fan ro'yxati saqlandi." if reserve
                         else "Fan ro'yxati yaratildi — endi kitob qo'shing.")
        return redirect(saved)
    if reserve is not None:
        # Yaroqsiz forma `instance`ni o'zgartirib yuboradi — sahifaga asl yozuvni beramiz
        reserve = CourseReserve.objects.get(pk=reserve.pk)
    return render(request, 'opac/course_form.html', {
        'form': form,
        'reserve': reserve,
        'faculties': courses.faculty_choices(),
    })


@login_required
def course_create(request):
    if not courses.can_create_reserve(request.user):
        return render(request, '403.html', status=403)
    return _course_form(request)


@login_required
def course_edit(request, pk):
    return _course_form(request, _editable(request, pk))


@require_POST
@login_required
def course_delete(request, pk):
    reserve = _editable(request, pk)
    name = reserve.course_name
    reserve.delete()
    messages.success(request, f"«{name}» ro'yxati o'chirildi.")
    return redirect('book_app:course_list')


@login_required
def course_book_search(request, pk):
    """Tahrirlovchi uchun jonli kitob qidiruvi (HTMX)."""
    reserve = _editable(request, pk)
    query = request.GET.get('book_q', '').strip()
    return render(request, 'opac/_course_search.html', {
        'reserve': reserve,
        'book_query': query,
        'results': _search_results(reserve, query),
        'importance_choices': CourseReserveItem.Importance.choices,
    })


@require_POST
@login_required
def course_add_book(request, pk, book_pk):
    reserve = _editable(request, pk)
    book = get_object_or_404(Book, pk=book_pk, is_active=True)
    added, msg = courses.add_book(reserve, book,
                                  importance=request.POST.get('importance', ''),
                                  note=request.POST.get('note', '').strip())
    (messages.success if added else messages.warning)(request, msg)
    # Qidiruv saqlanadi — ketma-ket bir nechta kitob qo'shish qulay bo'lsin
    url = reverse('book_app:course_detail', args=[reserve.pk])
    query = request.POST.get('book_q', '').strip()
    if query:
        url += '?' + urlencode({'book_q': query})
    return redirect(url + '#add-book')


@require_POST
@login_required
def course_remove_book(request, pk, book_pk):
    reserve = _editable(request, pk)
    _, msg = courses.remove_book(reserve, get_object_or_404(Book, pk=book_pk))
    messages.success(request, msg)
    return redirect(reserve)


@require_POST
@login_required
def course_update_item(request, pk, book_pk):
    reserve = _editable(request, pk)
    item = get_object_or_404(reserve.items, book_id=book_pk)
    courses.update_item(item, request.POST.get('importance'), request.POST.get('note'))
    messages.success(request, "O'zgarish saqlandi.")
    return redirect(reserve)
