from django.http import JsonResponse

from user_app.utils import employee_role_required

@employee_role_required
def employee_dashboard(request):
    return JsonResponse({'message': 'Xodim boshqaruv paneliga xush kelibsiz'})