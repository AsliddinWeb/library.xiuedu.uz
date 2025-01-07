from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Change password
from django.urls import reverse
from django.utils.html import format_html

# Unfold
from unfold.admin import ModelAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin

from .models import User, EmployeProfile, StudentProfile, Role

# Unregister
admin.site.unregister(Group)

@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass

# User Admin
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ("username", "email", "phone", "user_type", "is_staff", "is_active", "password_change_link")
    list_filter = ("user_type", "is_staff", "is_active", "gender")
    search_fields = ("username", "email", "phone", "first_name", "second_name", "third_name")
    ordering = ("username",)
    filter_horizontal = ()

    fieldsets = (
        ("Asosiy ma'lumotlar", {
            "fields": ("username", "password",)
        }),
        ("Shaxsiy ma'lumotlar", {
            "fields": ("email", "phone", "first_name", "second_name", "third_name", "birth_day", "gender", "image")
        }),
        ("Manzil ma'lumotlari", {
            "fields": ("country", "province", "district", "address")
        }),
        # ("Identifikatsiya", {
        #     "fields": ("passport_number", "jshshir")
        # }),
        ("Ruxsatnomalar", {
            "fields": ("user_type", "is_staff", "is_active", "is_superuser", "groups", "user_permissions")
        }),
        ("Muhim sanalar", {
            "fields": ("last_login",)
        }),
    )

    filter_horizontal = ("groups", "user_permissions")

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "user_type", "is_staff", "is_active")
        }),
    )

    def password_change_link(self, obj):
        if obj.id:
            url = reverse('admin:auth_user_password_change', args=[obj.id])
            return format_html(
                f'<a href="../user/{obj.id}/password">Parolni yangilash</a>',
                url
            )
        return "Parolni o'zgartirish havolasi mavjud emas."

    password_change_link.short_description = "Parolni o'zgartirish"

# EmployeProfile Admin
class EmployeProfileAdmin(ModelAdmin):
    list_display = ("user", "department", "position", "current_role")
    search_fields = ("user__username", "user__email", "department", "position")
    list_filter = ("roles",)
    filter_horizontal = ("roles", )

# StudentProfile Admin
class StudentProfileAdmin(ModelAdmin):
    list_display = ("user", "faculty", "group", "level", "semester", "education_form", "education_type", "payment_form")
    search_fields = ("user__username", "user__email", "faculty", "group")
    list_filter = ("faculty", "education_form", "education_type")

# Role Admin
class RoleAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

# Register models
admin.site.register(User, UserAdmin)
admin.site.register(EmployeProfile, EmployeProfileAdmin)
admin.site.register(StudentProfile, StudentProfileAdmin)
admin.site.register(Role, RoleAdmin)

