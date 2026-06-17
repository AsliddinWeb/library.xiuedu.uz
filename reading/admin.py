from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ReadingProgress, ReadingHistory


@admin.register(ReadingProgress)
class ReadingProgressAdmin(ModelAdmin):
    list_display = ("user", "book", "mode", "percent", "updated_at")
    list_filter = ("mode",)
    search_fields = ("user__username", "book__title")


@admin.register(ReadingHistory)
class ReadingHistoryAdmin(ModelAdmin):
    list_display = ("user", "book", "opened_at")
    search_fields = ("user__username", "book__title")
