from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import LibrarySettings, RentalRequest, Reservation, Fine


@admin.register(LibrarySettings)
class LibrarySettingsAdmin(ModelAdmin):
    list_display = ("__str__", "rental_days", "reservation_hold_days", "fine_per_day", "max_active_rentals")

    def has_add_permission(self, request):
        # Yagona yozuv — qo'shimcha yaratishni taqiqlaymiz
        return not LibrarySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RentalRequest)
class RentalRequestAdmin(ModelAdmin):
    list_display = ("book", "student", "status", "created_at", "decided_at")
    list_filter = ("status", "created_at")
    search_fields = ("book__title", "student__user__username")
    autocomplete_fields = ("student", "book", "rental", "decided_by")
    readonly_fields = ("created_at",)


@admin.register(Reservation)
class ReservationAdmin(ModelAdmin):
    list_display = ("book", "student", "status", "hold_until", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("book__title", "student__user__username")
    autocomplete_fields = ("student", "book")


@admin.register(Fine)
class FineAdmin(ModelAdmin):
    list_display = ("student", "amount", "days_overdue", "is_paid", "created_at")
    list_filter = ("is_paid", "created_at")
    search_fields = ("student__user__username", "rental__copy__book__title")
    autocomplete_fields = ("student", "rental")
