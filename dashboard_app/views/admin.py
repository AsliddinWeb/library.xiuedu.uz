from django.http import JsonResponse
from django.shortcuts import render

from user_app.utils import admin_role_required

@admin_role_required
def admin_dashboard(request):
    return JsonResponse({'message': 'Admin boshqaruv paneliga xush kelibsiz'})
