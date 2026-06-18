import logging
from datetime import datetime

import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views import View

from oauth.client import oAuth2Client
from user_app.models import EmployeProfile, Role, StudentProfile, User

logger = logging.getLogger(__name__)


def _parse_birth_date(value):
    """HEMIS'dan kelgan turli formatdagi sanani date'ga aylantiradi.
    Aniqlab bo'lmasa None qaytaradi (login to'xtamasligi uchun)."""
    if isinstance(value, bool) or value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, int):
        try:
            return datetime.fromtimestamp(value).date()
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            logger.warning("Birth date formati noto'g'ri: %r", value)
            return None
    return None


def _download_profile_image(user, picture_url):
    """Profil rasmini tashqi URL'dan yuklab oladi. Xatolik login'ni to'xtatmaydi."""
    if not picture_url:
        return
    try:
        resp = requests.get(picture_url, timeout=10)
        resp.raise_for_status()
        user.image.save(f'{user.username}_profile_pic.jpg', ContentFile(resp.content), save=True)
    except requests.exceptions.RequestException as e:
        logger.warning("Profil rasmini yuklab bo'lmadi (%s): %s", user.username, e)


class AuthLoginView(View):
    def get(self, request):
        if not settings.AUTHORIZE_URL:
            return HttpResponse(
                "HEMIS oAuth sozlanmagan (AUTHORIZE_URL yo'q). "
                "Lokal sinov uchun /admin orqali kiring.",
                status=503,
            )
        client = oAuth2Client(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            redirect_uri=settings.REDIRECT_URI,
            authorize_url=settings.AUTHORIZE_URL,
            token_url=settings.ACCESS_TOKEN_URL,
            resource_owner_url=settings.RESOURCE_OWNER_URL
        )

        response = redirect(client.get_authorization_url())
        response.set_cookie('user_type', 'student', max_age=3600)
        return response


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('home')

    post = get


class AuthCallbackView(View):
    def get(self, request):
        code = request.GET.get('code')
        user_type = request.COOKIES.get('user_type', 'student')

        if not code:
            return JsonResponse({'error': 'Code is missing!'}, status=400)

        if user_type == "employee":
            token_url = settings.EMPLOYE_ACCESS_TOKEN_URL
            resource_owner_url = settings.EMPLOYE_RESOURCE_OWNER_URL
            authorize_url = settings.EMPLOYE_AUTHORIZE_URL
        elif user_type == "student":
            token_url = settings.ACCESS_TOKEN_URL
            resource_owner_url = settings.RESOURCE_OWNER_URL
            authorize_url = settings.AUTHORIZE_URL
        else:
            return JsonResponse({'error': 'Invalid user type in cookie!'}, status=400)

        client = oAuth2Client(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            redirect_uri=settings.REDIRECT_URI,
            authorize_url=authorize_url,
            token_url=token_url,
            resource_owner_url=resource_owner_url
        )

        access_token_response = client.get_access_token(code)
        access_token = access_token_response.get('access_token')
        if not access_token:
            return JsonResponse({'status': False, 'error': 'Failed to obtain access token'}, status=400)

        user_details = client.get_user_details(access_token)

        if user_type == "student":
            user = self.process_student(user_details)
        else:
            user = self.process_employee(user_details)

        if not user:
            return JsonResponse({'status': False, 'error': "Foydalanuvchi ma'lumotlarini qayta ishlashda xatolik"}, status=400)

        login(request, user)
        return redirect('dashboard')

    def process_student(self, user_details):
        student_data = user_details.get('data', {})
        if not student_data.get('student_id_number'):
            logger.warning("Student callback: student_id_number yo'q")
            return None

        group = student_data.get('group', {})
        faculty = student_data.get('faculty', {})

        user, _ = User.objects.update_or_create(
            username=student_data.get('student_id_number'),
            defaults={
                'first_name': student_data.get('first_name', ''),
                'second_name': student_data.get('second_name', ''),
                'third_name': student_data.get('third_name', ''),
                'email': student_data.get('email', ''),
                'phone': student_data.get('phone', ''),
                'birth_day': _parse_birth_date(student_data.get('birth_date')),
                'gender': student_data.get('gender', {}).get('name', ''),
                'user_type': User.UserType.STUDENT,
                'hemis_uuid': student_data.get('uuid') or None,
                'university_id': str(student_data.get('university_id') or '') or None,
                'country': student_data.get('country', {}).get('name', ''),
                'province': student_data.get('province', {}).get('name', ''),
                'district': student_data.get('district', {}).get('name', ''),
                'address': student_data.get('address', ''),
            }
        )

        _download_profile_image(user, student_data.get('image', ''))

        StudentProfile.objects.update_or_create(
            user=user,
            defaults={
                'faculty': faculty.get('name', ''),
                'group': group.get('name', ''),
                'level': student_data.get('level', {}).get('name', ''),
                'semester': student_data.get('semester', {}).get('name', ''),
                'education_form': student_data.get('educationForm', {}).get('name', ''),
                'education_type': student_data.get('educationType', {}).get('name', ''),
                'payment_form': student_data.get('paymentForm', {}).get('name', ''),
            }
        )

        return user

    def process_employee(self, user_details):
        employe_data = user_details
        if not employe_data.get('employee_id_number'):
            logger.warning("Employee callback: employee_id_number yo'q")
            return None

        departments = employe_data.get('departments') or [{}]
        department = departments[0].get('department', {}).get('name', '')
        position = departments[0].get('staffPosition', {}).get('name', '')

        user, _ = User.objects.update_or_create(
            username=employe_data.get('employee_id_number'),
            defaults={
                'first_name': employe_data.get('firstname', ''),
                'second_name': employe_data.get('surname', ''),
                'third_name': employe_data.get('patronymic', ''),
                'email': employe_data.get('email', ''),
                'phone': employe_data.get('phone', ''),
                'birth_day': _parse_birth_date(employe_data.get('birth_date')),
                'user_type': User.UserType.EMPLOYE,
                'hemis_uuid': employe_data.get('uuid') or None,
                'university_id': str(employe_data.get('university_id') or '') or None,
            }
        )

        _download_profile_image(user, employe_data.get('picture', ''))

        employee_role, _ = Role.objects.get_or_create(name="Employee")

        profile, _ = EmployeProfile.objects.update_or_create(
            user=user,
            defaults={
                'department': department,
                'position': position,
            }
        )
        # current_role faqat birinchi marta o'rnatiladi (mavjudini bekor qilmaslik uchun)
        if profile.current_role is None:
            profile.current_role = employee_role
            profile.save(update_fields=['current_role'])
        if not profile.roles.filter(name="Employee").exists():
            profile.roles.add(employee_role)

        return user
