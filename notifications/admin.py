from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ("title", "user", "type", "read_badge", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("title", "message", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)

    @display(description="Holati", label={"O'qilgan": "success", "Yangi": "warning"})
    def read_badge(self, obj):
        return "O'qilgan" if obj.is_read else "Yangi"
