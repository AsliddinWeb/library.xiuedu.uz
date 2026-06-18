from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin

from unfold.admin import ModelAdmin, StackedInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import User, EmployeProfile, StudentProfile, Role

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
    list_display = ("username", "full_name_display", "user_type_badge", "phone", "is_active", "is_staff")
    list_filter = ("user_type", "is_staff", "is_active", "gender")
    search_fields = ("username", "email", "phone", "first_name", "second_name", "third_name", "hemis_uuid")
    ordering = ("username",)
    list_filter_submit = True
    readonly_fields = ("last_login", "created_at", "updated_at")

    fieldsets = (
        ("Asosiy", {"fields": ("username", "password", "user_type")}),
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
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "user_type", "is_staff", "is_active"),
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

    @display(description="F.I.Sh")
    def full_name_display(self, obj):
        return obj.get_full_name()

    @display(description="Turi", label={"Talaba": "info", "Xodim": "warning"})
    def user_type_badge(self, obj):
        return obj.get_user_type_display()


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


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
