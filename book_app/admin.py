from django.contrib import admin

# Unfold
from unfold.admin import ModelAdmin

from .models import Author, Genre, Book, Copy, Rental

@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = ("full_name", "bio")
    search_fields = ("full_name",)
    list_filter = ()


@admin.register(Genre)
class GenreAdmin(ModelAdmin):
    list_display = ("name", "order", "is_active", "book_count")
    list_editable = ("order", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = (
        "title",
        "category",
        "published_year",
        "reading_mode",
        "is_active",
        "view_count",
    )
    search_fields = ("title", "isbn")
    list_filter = ("reading_mode", "is_active", "language", "category")
    filter_horizontal = ("authors", )
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("view_count", "avg_rating", "rating_count", "published_date")


@admin.register(Copy)
class CopyAdmin(ModelAdmin):
    list_display = ("book", "inventory_number", "is_available")
    search_fields = ("inventory_number", "book__title")
    list_filter = ("is_available",)


@admin.register(Rental)
class RentalAdmin(ModelAdmin):
    list_display = (
        "copy",
        "student",
        "borrowed_date",
        "return_date",
    )
    search_fields = (
        "copy__inventory_number",
        "copy__book__title",
        "student__user__first_name",
        "student__user__last_name",
    )
    list_filter = ("borrowed_date", "return_date")
