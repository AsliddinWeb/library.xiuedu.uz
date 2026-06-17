"""
Rollar markaziy joyda. Nomlar mavjud DB'dagi `Role.name` qiymatlari bilan
mos kelishi shart (migration qilmaslik uchun o'zgartirilmaydi).
"""


class Roles:
    STUDENT = 'Student'
    EMPLOYEE = 'Employee'
    LIBRARIAN = 'LibraryAdmin'
    ADMIN = 'Admin'

    CHOICES = (STUDENT, EMPLOYEE, LIBRARIAN, ADMIN)


def effective_role(user):
    """Foydalanuvchining amaldagi rolini qaytaradi (xato-bardosh).

    - autentifikatsiyadan o'tmagan        -> None
    - superuser                            -> ADMIN
    - talaba (user_type == STUDENT)        -> STUDENT
    - xodim, current_role bor              -> current_role.name
    - xodim, current_role yo'q             -> EMPLOYEE (standart)
    """
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return Roles.ADMIN
    if user.user_type == 'STUDENT':
        return Roles.STUDENT

    profile = getattr(user, 'employe_profile', None)
    if profile is not None and profile.current_role_id and profile.current_role:
        return profile.current_role.name
    return Roles.EMPLOYEE
