from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import ReadingProgress, ReadingHistory


@admin.register(ReadingProgress)
class ReadingProgressAdmin(ModelAdmin):
    list_display = ("user", "book", "mode_badge", "progress", "updated_at")
    list_filter = ("mode",)
    search_fields = ("user__username", "book__title")
    autocomplete_fields = ("user", "book")
    readonly_fields = ("updated_at",)

    @display(description="Turi", label={"O'qish": "info", "Tinglash": "success"})
    def mode_badge(self, obj):
        return obj.get_mode_display()

    @display(description="Jarayon")
    def progress(self, obj):
        return f"{obj.percent}%"


@admin.register(ReadingHistory)
class ReadingHistoryAdmin(ModelAdmin):
    list_display = ("user", "book", "opened_at")
    search_fields = ("user__username", "book__title")
    autocomplete_fields = ("user", "book")
    date_hierarchy = "opened_at"
