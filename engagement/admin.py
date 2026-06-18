from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from . import services
from .models import Review, Favorite


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ("book", "user", "stars", "approved_badge", "created_at")
    list_filter = ("is_approved", "rating")
    search_fields = ("book__title", "user__username", "text")
    autocomplete_fields = ("book", "user")
    readonly_fields = ("created_at", "updated_at")
    actions = ["approve_selected"]

    @display(description="Baho")
    def stars(self, obj):
        return "★" * obj.rating + "☆" * (5 - obj.rating)

    @display(description="Holati", label={"Tasdiqlangan": "success", "Moderatsiyada": "warning"})
    def approved_badge(self, obj):
        return "Tasdiqlangan" if obj.is_approved else "Moderatsiyada"

    @admin.action(description="Tanlangan sharhlarni tasdiqlash")
    def approve_selected(self, request, queryset):
        for review in queryset:
            services.approve_review(review)


@admin.register(Favorite)
class FavoriteAdmin(ModelAdmin):
    list_display = ("user", "book", "created_at")
    search_fields = ("user__username", "book__title")
    autocomplete_fields = ("user", "book")
