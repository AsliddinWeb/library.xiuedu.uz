from functools import wraps

from django.shortcuts import redirect, render

from .roles import Roles, effective_role


def role_required(*allowed_roles):
    """Foydalanuvchining amaldagi roli `allowed_roles` ichida bo'lishini talab qiladi.

    - autentifikatsiyadan o'tmagan -> login sahifasiga yo'naltiradi
    - roli mos kelmasa             -> 403 sahifa
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('student_login')

            if effective_role(request.user) in allowed_roles:
                return view_func(request, *args, **kwargs)

            return render(request, '403.html', status=403)

        return _wrapped_view

    return decorator


def student_role_required(view_func):
    return role_required(Roles.STUDENT)(view_func)


def employee_role_required(view_func):
    return role_required(Roles.EMPLOYEE, Roles.LIBRARIAN, Roles.ADMIN)(view_func)


def admin_role_required(view_func):
    return role_required(Roles.ADMIN)(view_func)


def library_admin_role_required(view_func):
    # Kutubxonachi bo'limlariga LibraryAdmin va Admin kira oladi
    return role_required(Roles.LIBRARIAN, Roles.ADMIN)(view_func)
