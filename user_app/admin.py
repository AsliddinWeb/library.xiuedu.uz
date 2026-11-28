from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Q
from unfold.admin import ModelAdmin, StackedInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm
from unfold.forms import UserChangeForm as BaseUserChangeForm
from unfold.forms import UserCreationForm as BaseUserCreationForm
from unfold.widgets import UnfoldAdminCheckboxSelectMultiple, UnfoldAdminSelectWidget

from .models import EmployeProfile, Patron, PatronCategory, Role, StudentProfile, User
from .permissions import ALL_PERMISSIONS, PERMISSION_GROUPS
from .roles import AccountKind, Roles, account_kind, staff_user_q


class RoleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, role):
        return Roles.LABELS.get(role.name, role.name)


def _role_field():
    return RoleChoiceField(
        queryset=Role.objects.exclude(name=Roles.STUDENT), required=False,
        label="Rol (xodim turidagi foydalanuvchi uchun)",
        help_text="«Kutubxona xodimi» tanlansa kutubxona paneli ochiladi va kitob olish "
                  "yopiladi. O'quvchiga qaytarish uchun «O'qituvchi / xodim (o'quvchi)»ni "
                  "tanlang. Administrator uchun «Admin panelga kirish» belgisini ham yoqing.",
        widget=UnfoldAdminSelectWidget(),
    )


class AccountKindFilter(admin.SimpleListFilter):
    """Foydalanuvchilarni kim ekaniga qarab ajratadi (menyudagi bandlar ham shu)."""
    title = "Hisob turi"
    parameter_name = 'kind'

    def lookups(self, request, model_admin):
        return [('student', "Talabalar"), ('employee', "O'qituvchi va xodimlar (o'quvchi)"),
                ('librarian', "Kutubxona xodimlari"), ('admin', "Administratorlar")]

    def queryset(self, request, queryset):
        staff = staff_user_q()
        admins = Q(is_superuser=True) | staff_user_q(admins=True)
        value = self.value()
        if value == 'admin':
            return queryset.filter(admins)
        if value == 'librarian':
            return queryset.filter(staff).exclude(admins)
        types = {'student': User.UserType.STUDENT, 'employee': User.UserType.EMPLOYE}
        if value in types:
            return queryset.filter(user_type=types[value]).exclude(staff | admins)
        return queryset


# --- Rol tanlashli formalar (xodim rolini bir qadamda biriktirish) ---

class UserCreationForm(BaseUserCreationForm):
    assigned_role = _role_field()

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("username", "user_type", "first_name", "second_name", "third_name", "email", "phone")


class UserChangeForm(BaseUserChangeForm):
    assigned_role = _role_field()

    class Meta(BaseUserChangeForm.Meta):
        model = User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, 'instance', None)
        profile = getattr(inst, 'employe_profile', None) if inst and inst.pk else None
        if profile and profile.current_role_id:
            self.fields['assigned_role'].initial = profile.current_role_id

# Group'ni unfold ko'rinishida qayta ro'yxatdan o'tkazamiz
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


# --- Profil inline'lari ---

class StudentProfileInline(StackedInline):
    model = StudentProfile
    can_delete = False
    max_num = 1
    extra = 0
    verbose_name_plural = "Talaba profili"
    readonly_fields = ("created_at", "updated_at")


class EmployeProfileInline(StackedInline):
    model = EmployeProfile
    can_delete = False
    max_num = 1
    extra = 0
    verbose_name_plural = "Xodim profili"
    filter_horizontal = ("roles",)
    autocomplete_fields = ("current_role",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ("username", "full_name_display", "kind_badge", "phone", "is_active", "is_staff")
    list_filter = (AccountKindFilter, "is_active", "gender")
    search_fields = ("username", "email", "phone", "first_name", "second_name", "third_name", "hemis_uuid")
    ordering = ("username",)
    list_filter_submit = True
    readonly_fields = ("last_login", "created_at", "updated_at")

    fieldsets = (
        ("Asosiy", {"fields": ("username", "password", "user_type", "assigned_role")}),
        ("Shaxsiy ma'lumotlar", {
            "fields": ("first_name", "second_name", "third_name", "email", "phone",
                       "birth_day", "gender", "image"),
        }),
        ("Manzil", {
            "classes": ("collapse",),
            "fields": ("country", "province", "district", "address"),
        }),
        ("HEMIS", {
            "classes": ("collapse",),
            "fields": ("hemis_uuid", "university_id"),
        }),
        ("Ruxsatnomalar", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Sanalar", {
            "classes": ("collapse",),
            "fields": ("last_login", "created_at", "updated_at"),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")

    add_fieldsets = (
        ("Hisob", {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2"),
        }),
        ("Turi va rol", {
            "classes": ("wide",),
            "fields": ("user_type", "assigned_role", "is_active", "is_staff"),
        }),
        ("Shaxsiy ma'lumotlar", {
            "classes": ("wide",),
            "fields": ("first_name", "second_name", "third_name", "email", "phone"),
        }),
    )

    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        inline = StudentProfileInline if obj.user_type == User.UserType.STUDENT else EmployeProfileInline
        return [inline(self.model, self.admin_site)]

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related('employe_profile__current_role')
                .prefetch_related('employe_profile__roles'))

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and 'assigned_role' in form.base_fields:
            # Administrator rolini faqat superuser bera oladi
            field = form.base_fields['assigned_role']
            field.queryset = field.queryset.exclude(name=Roles.ADMIN)
        return form

    def save_related(self, request, form, formsets, change):
        # Profil inline'i saqlangandan KEYIN — aks holda u tanlangan rolni
        # eski qiymatlar bilan qayta yozib yuboradi
        super().save_related(request, form, formsets, change)
        user = form.instance
        if user.user_type != User.UserType.EMPLOYE or 'assigned_role' not in form.changed_data:
            return
        role = form.cleaned_data.get('assigned_role')
        profile, _ = EmployeProfile.objects.get_or_create(user=user)
        profile.current_role = role
        profile.save(update_fields=['current_role'])
        # Tanlangan rol eskilarini ALMASHTIRADI: xodimlikdan chiqarish ham shu yo'l bilan
        profile.roles.set([role] if role else [])

    @display(description="F.I.Sh")
    def full_name_display(self, obj):
        return obj.get_full_name()

    @display(description="Hisob turi", label={
        "Talaba": "info", "O'qituvchi / xodim": "info",
        "Kutubxona xodimi": "success", "Administrator": "danger"})
    def kind_badge(self, obj):
        kind = account_kind(obj)
        if kind == AccountKind.ADMIN:
            return "Administrator"
        if kind == AccountKind.LIBRARIAN:
            return "Kutubxona xodimi"
        return "Talaba" if obj.user_type == User.UserType.STUDENT else "O'qituvchi / xodim"


@admin.register(EmployeProfile)
class EmployeProfileAdmin(ModelAdmin):
    list_display = ("user", "department", "position", "current_role")
    search_fields = ("user__username", "user__email", "department", "position")
    list_filter = ("roles",)
    filter_horizontal = ("roles",)
    autocomplete_fields = ("user", "current_role")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StudentProfile)
class StudentProfileAdmin(ModelAdmin):
    list_display = ("user", "faculty", "group", "level", "semester", "education_form")
    search_fields = ("user__username", "user__email", "faculty", "group")
    list_filter = ("faculty", "education_form", "education_type")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


#: Kod shu nomlarga tayanadi — o'zgartirilmaydi va o'chirilmaydi
SYSTEM_ROLES = (Roles.STUDENT, Roles.EMPLOYEE, Roles.LIBRARIAN, Roles.ADMIN)


class RoleForm(forms.ModelForm):
    """Ruxsatlar kod yozib emas, belgilab tanlanadi."""
    full_access = forms.BooleanField(
        required=False, label="Barcha ruxsatlar",
        help_text="Belgilansa, pastdagi tanlovdan qat'i nazar hammasiga ruxsat beriladi.")
    flags = forms.MultipleChoiceField(
        required=False, label="Ruxsatlar",
        choices=[(group, list(items)) for group, items in PERMISSION_GROUPS],
        widget=UnfoldAdminCheckboxSelectMultiple())

    class Meta:
        model = Role
        fields = ("name", "description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.permissions or []
        self.fields["full_access"].initial = "*" in current
        self.fields["flags"].initial = [flag for flag in current if flag != "*"]

    def save(self, commit=True):
        role = super().save(commit=False)
        if role.name in Roles.READER:
            role.permissions = []          # o'quvchi roli ruxsat bermaydi
        elif self.cleaned_data.get("full_access"):
            role.permissions = ["*"]
        else:
            chosen = set(self.cleaned_data.get("flags") or [])
            role.permissions = [flag for flag in ALL_PERMISSIONS if flag in chosen]
        if commit:
            role.save()
        return role


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    form = RoleForm
    list_display = ("role_name", "description", "permission_summary")
    search_fields = ("name",)
    fields = ("name", "description", "full_access", "flags")

    def get_readonly_fields(self, request, obj=None):
        return ("name",) if obj and obj.name in SYSTEM_ROLES else ()

    def has_delete_permission(self, request, obj=None):
        if obj and obj.name in SYSTEM_ROLES:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)      # tizim rollari o'chib ketmasin
        return actions

    @display(description="Rol")
    def role_name(self, obj):
        return Roles.LABELS.get(obj.name, obj.name)

    @display(description="Ruxsatlar")
    def permission_summary(self, obj):
        perms = obj.permissions or []
        if '*' in perms:
            return "Barcha ruxsatlar"
        return f"{len(perms)} ta" if perms else "—"


# =============================================================================
#  A'zolik (Patron)
# =============================================================================

@admin.register(PatronCategory)
class PatronCategoryAdmin(ModelAdmin):
    list_display = ("name", "code", "default_loan_days", "loan_limit", "hold_limit",
                    "renewals_allowed", "patrons_count", "is_active")
    list_filter = ("is_active", "requires_deposit")
    search_fields = ("name", "code")
    ordering = ("order", "name")
    fieldsets = (
        (None, {"fields": ("code", "name", "description", "order", "is_active")}),
        ("Sirkulyatsiya qoidalari", {
            "fields": ("default_loan_days", "loan_limit", "hold_limit", "renewals_allowed",
                       "fine_per_day", "debt_block_amount", "can_borrow_reading_room_items"),
            "description": "P3'da bu qiymatlar (filial x toifa x nusxa turi) "
                           "matritsasi bilan to'ldiriladi; hozir standart qiymat sifatida ishlaydi.",
        }),
        ("A'zolik", {"fields": ("membership_months", "requires_deposit")}),
    )

    @display(description="A'zolar")
    def patrons_count(self, obj):
        return obj.patrons.count()


@admin.register(Patron)
class PatronAdmin(ModelAdmin):
    list_display = ("card_number", "display_name_col", "category", "status_badge",
                    "active_loans_count", "balance", "expires_on")
    list_filter = ("status", "category", "registered_on")
    search_fields = ("card_number", "full_name", "phone", "email",
                     "user__username", "user__first_name", "user__second_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("registered_on", "created_at", "updated_at",
                       "active_loans_count", "overdue_count", "balance")
    list_select_related = ("user", "category")
    fieldsets = (
        (None, {"fields": ("card_number", "category", "status", "user")}),
        ("HEMIS'siz a'zo ma'lumotlari", {
            "classes": ("collapse",),
            "fields": ("full_name", "phone", "email", "birth_date", "address", "photo"),
            "description": "Faqat qo'lda qo'shilgan (HEMIS'siz) a'zolar uchun to'ldiriladi.",
        }),
        ("A'zolik", {"fields": ("registered_on", "expires_on", "deposit_amount")}),
        ("Cheklov", {"fields": ("block_reason", "blocked_until", "note")}),
        ("Hisob (avtomatik)", {"fields": ("active_loans_count", "overdue_count", "balance")}),
    )

    @display(description="F.I.Sh.")
    def display_name_col(self, obj):
        return obj.display_name

    @display(description="Holati", label={
        "Faol": "success", "Bloklangan": "danger", "Qarzdor": "warning",
        "Muddati o'tgan": "warning", "Yopilgan": "info",
    })
    def status_badge(self, obj):
        return obj.get_status_display()
