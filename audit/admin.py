from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ActionLog, JobRun


@admin.register(ActionLog)
class ActionLogAdmin(ModelAdmin):
    list_display = ('at', 'actor_label', 'action', 'object_repr', 'ip')
    list_filter = ('action', 'at')
    search_fields = ('actor_label', 'object_repr', 'object_id', 'note', 'path')
    date_hierarchy = 'at'
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JobRun)
class JobRunAdmin(ModelAdmin):
    list_display = ('name', 'status', 'started_at', 'duration_ms', 'message')
    list_filter = ('name', 'status', 'started_at')
    search_fields = ('name', 'message', 'error')
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
