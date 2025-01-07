from django.http import JsonResponse

from user_app.utils import student_role_required

@student_role_required
def student_dashboard(request):
    return JsonResponse({'message': 'Talaba boshqaruv paneliga xush kelibsiz'})