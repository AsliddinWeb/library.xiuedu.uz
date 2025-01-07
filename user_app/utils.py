from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist

def role_required(role_name):
    """
    Dekorator foydalanuvchining current_role ni tekshiradi va belgilangan ro'l bilan solishtiradi.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if user.is_authenticated:
                try:
                    # Try to access the user's employe_profile and current_role
                    current_role = user.employe_profile.current_role

                    if current_role.name == role_name:
                        return view_func(request, *args, **kwargs)
                    else:
                        return JsonResponse({'error': "Bu bo'limga kirishga sizda ruhsat yo'q!"}, status=403)
                except ObjectDoesNotExist:
                    return JsonResponse({'error': 'Employee profile mavjud emas!'}, status=404)
            else:
                return JsonResponse({'error': 'Avtorizatsiya xatosi!'}, status=401)

        return _wrapped_view

    return decorator


def student_role_required(view_func):
    return role_required('Student')(view_func)


def employee_role_required(view_func):
    return role_required('Employee')(view_func)


def admin_role_required(view_func):
    return role_required('Admin')(view_func)


def library_admin_role_required(view_func):
    return role_required('LibraryAdmin')(view_func)
