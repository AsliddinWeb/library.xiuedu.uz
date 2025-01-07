from datetime import datetime
import requests
from django.core.files.base import ContentFile

from django.shortcuts import redirect
from django.views import View
from django.http import JsonResponse
from django.contrib.auth import login
from django.db.models import Q

from oauth.client import oAuth2Client
from django.conf import settings

from user_app.models import User, StudentProfile, EmployeProfile, Role


class AuthLoginView(View):
    def get(self, request):
        user_type = 'student'
        client = oAuth2Client(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            redirect_uri=settings.REDIRECT_URI,
            authorize_url=settings.AUTHORIZE_URL,
            token_url=settings.ACCESS_TOKEN_URL,
            resource_owner_url=settings.RESOURCE_OWNER_URL
        )

        authorization_url = client.get_authorization_url()

        response = redirect(authorization_url)
        response.set_cookie('user_type', user_type, max_age=3600)
        return response

class AuthCallbackView(View):
    def get(self, request):
        code = request.GET.get('code')
        user_type = request.COOKIES.get('user_type', 'student')

        if not code:
            return JsonResponse({'error': 'Code is missing!'}, status=400)

        if user_type == "employee":
            authorize_url = settings.EMPLOYE_AUTHORIZE_URL
            token_url = settings.EMPLOYE_ACCESS_TOKEN_URL
            resource_owner_url = settings.EMPLOYE_RESOURCE_OWNER_URL
        elif user_type == "student":
            authorize_url = settings.AUTHORIZE_URL
            token_url = settings.ACCESS_TOKEN_URL
            resource_owner_url = settings.RESOURCE_OWNER_URL
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

        if 'access_token' in access_token_response:
            access_token = access_token_response['access_token']
            user_details = client.get_user_details(access_token)

            if user_type == "student":
                user = self.process_student(user_details)
            else:
                user = self.process_employee(user_details)

            if user:
                login(request, user)


                return redirect('dashboard')

        return JsonResponse({'status': False, 'error': 'Failed to obtain access token'}, status=400)

    def process_student(self, user_details):
        student_data = user_details.get('data', {})

        group = student_data.get('group', {})
        faculty = student_data.get('faculty', {})

        birth_date = student_data.get('birth_date', None)
        if isinstance(birth_date, int):
            birth_date = datetime.fromtimestamp(birth_date).date()
        elif isinstance(birth_date, str):
            try:
                birth_date = datetime.strptime(birth_date, "%d-%m-%Y").date()
            except ValueError:
                return JsonResponse({'error': 'Invalid birth date format. It must be DD-MM-YYYY.'}, status=400)
        elif isinstance(birth_date, datetime):
            birth_date = birth_date.date()

        user, created = User.objects.update_or_create(
            username=student_data.get('student_id_number'),
            defaults={
                'first_name': student_data.get('first_name', ''),
                'second_name': student_data.get('second_name', ''),
                'third_name': student_data.get('third_name', ''),
                'email': student_data.get('email', ''),
                'phone': student_data.get('phone', ''),
                'image': student_data.get('image', ''),
                'birth_day': birth_date,
                'gender': student_data.get('gender', {}).get('name', ''),
                'user_type': User.UserType.STUDENT,
                'country': student_data.get('country', {}).get('name', ''),
                'province': student_data.get('province', {}).get('name', ''),
                'district': student_data.get('district', {}).get('name', ''),
                'address': student_data.get('address', ''),
            }
        )

        picture_url = student_data.get('image', '')
        if picture_url:
            try:
                img_data = requests.get(picture_url).content
                user.image.save(f'{user.username}_profile_pic.jpg', ContentFile(img_data), save=True)
            except requests.exceptions.RequestException as e:
                return JsonResponse({'error': f'Image download failed: {str(e)}'}, status=400)


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
        department = employe_data.get('departments', [{}])[0].get('department', {}).get('name', '')
        position = employe_data.get('departments', [{}])[0].get('staffPosition', {}).get('name', '')

        birth_date = employe_data.get('birth_date', None)
        if isinstance(birth_date, str):
            try:
                birth_date = datetime.strptime(birth_date, "%d-%m-%Y").date()
            except ValueError:
                return JsonResponse({'error': 'Invalid birth date format. It must be DD-MM-YYYY.'}, status=400)
        elif isinstance(birth_date, datetime):
            birth_date = birth_date.date()

        user, created = User.objects.update_or_create(
            username=employe_data.get('employee_id_number'),
            defaults={
                'first_name': employe_data.get('firstname', ''),
                'second_name': employe_data.get('surname', ''),
                'third_name': employe_data.get('patronymic', ''),
                'email': employe_data.get('email', ''),
                'phone': employe_data.get('phone', ''),
                'image': employe_data.get('picture', ''),
                'birth_day': birth_date,
                'user_type': User.UserType.EMPLOYE,
            }
        )

        picture_url = employe_data.get('picture', '')
        if picture_url:
            try:
                img_data = requests.get(picture_url).content
                user.image.save(f'{user.username}_profile_pic.jpg', ContentFile(img_data), save=True)
            except requests.exceptions.RequestException as e:
                return JsonResponse({'error': f'Image download failed: {str(e)}'}, status=400)

        employee_role, created = Role.objects.get_or_create(name="Employee")

        EmployeProfile.objects.update_or_create(
            user=user,
            defaults={
                'department': department,
                'position': position,
                'current_role': employee_role
            }
        )

        employe_profile = EmployeProfile.objects.get(user=user)
        if not employe_profile.roles.filter(Q(name="Employee")).exists():
            employe_profile.roles.add(employee_role)

        return user
