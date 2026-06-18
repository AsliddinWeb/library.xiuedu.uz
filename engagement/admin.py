from django.contrib import admin
from unfold.admin import ModelAdmin

from . import services
from .models import Review, Favorite


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ("book", "user", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
    search_fields = ("book__title", "user__username", "text")
    actions = ["approve_selected"]

    @admin.action(description="Tanlangan sharhlarni tasdiqlash")
    def approve_selected(self, request, queryset):
        for review in queryset:
            services.approve_review(review)


@admin.register(Favorite)
class FavoriteAdmin(ModelAdmin):
    list_display = ("user", "book", "created_at")
    search_fields = ("user__username", "book__title")
