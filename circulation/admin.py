from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from . import services
from .models import LibrarySettings, RentalRequest, Reservation, Fine


@admin.register(LibrarySettings)
class LibrarySettingsAdmin(ModelAdmin):
    list_display = ("__str__", "rental_days", "reservation_hold_days", "fine_per_day", "max_active_rentals")

    def has_add_permission(self, request):
        return not LibrarySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RentalRequest)
class RentalRequestAdmin(ModelAdmin):
    list_display = ("book", "student", "status_badge", "created_at", "decided_at")
    list_filter = ("status", "created_at")
    search_fields = ("book__title", "student__user__username")
    autocomplete_fields = ("student", "book", "rental", "decided_by")
    readonly_fields = ("created_at", "decided_at")
    date_hierarchy = "created_at"

    @display(description="Holati", label={
        "Kutilmoqda": "warning", "Tasdiqlangan": "success",
        "Rad etilgan": "danger", "Bekor qilingan": "info"})
    def status_badge(self, obj):
        return obj.get_status_display()


@admin.register(Reservation)
class ReservationAdmin(ModelAdmin):
    list_display = ("book", "student", "status_badge", "hold_until", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("book__title", "student__user__username")
    autocomplete_fields = ("student", "book")

    @display(description="Holati", label={
        "Navbatda": "info", "Bo'shadi (ushlab turilmoqda)": "success",
        "Bajarildi": "success", "Muddati o'tdi": "danger", "Bekor qilingan": "info"})
    def status_badge(self, obj):
        return obj.get_status_display()


@admin.register(Fine)
class FineAdmin(ModelAdmin):
    list_display = ("student", "amount", "days_overdue", "paid_badge", "created_at")
    list_filter = ("is_paid", "created_at")
    search_fields = ("student__user__username", "rental__copy__book__title")
    autocomplete_fields = ("student", "rental")
    actions = ["mark_paid"]

    @display(description="To'lov", label={"To'langan": "success", "To'lanmagan": "danger"})
    def paid_badge(self, obj):
        return "To'langan" if obj.is_paid else "To'lanmagan"

    @admin.action(description="To'langan deb belgilash")
    def mark_paid(self, request, queryset):
        for fine in queryset:
            services.mark_fine_paid(fine)
