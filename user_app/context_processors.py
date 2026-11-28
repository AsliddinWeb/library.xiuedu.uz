"""`{{ account }}` — shablonlarda hisob turi (menyu va tugmalar shunga qarab chiqadi)."""
from django.utils.functional import SimpleLazyObject, cached_property

from .roles import AccountKind, Roles, account_kind, home_url, staff_roles


class Account:
    def __init__(self, user):
        self.user = user

    @cached_property
    def kind(self):
        return account_kind(self.user)

    @property
    def is_staff(self):
        """Kutubxona xodimi yoki administrator."""
        return self.kind in (AccountKind.LIBRARIAN, AccountKind.ADMIN)

    @property
    def is_admin(self):
        return self.kind == AccountKind.ADMIN

    @property
    def is_reader(self):
        return self.kind == AccountKind.READER

    @property
    def home(self):
        return home_url(self.user)

    @cached_property
    def label(self):
        if self.kind == AccountKind.ADMIN:
            return "Administrator"
        if self.kind == AccountKind.LIBRARIAN:
            names = [Roles.LABELS.get(role.name, role.name) for role in staff_roles(self.user)]
            return ", ".join(names) or "Kutubxona xodimi"
        if self.kind == AccountKind.READER:
            return "Talaba" if self.user.user_type == 'STUDENT' else "O'qituvchi / xodim"
        return "Mehmon"


def account(request):
    # Lazy: shablon ishlatmasa, so'rov bajarilmaydi
    return {'account': SimpleLazyObject(lambda: Account(getattr(request, 'user', None)))}
