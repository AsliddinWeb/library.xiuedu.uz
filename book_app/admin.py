from django.contrib import admin
from django.utils.html import format_html

from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import Author, Genre, Book, Copy, Rental


@admin.register(Author)
class AuthorAdmin(ModelAdmin):
    list_display = ("full_name", "short_bio")
    search_fields = ("full_name",)

    @display(description="Tavsif")
    def short_bio(self, obj):
        if not obj.bio:
            return "—"
        return (obj.bio[:80] + "…") if len(obj.bio) > 80 else obj.bio


@admin.register(Genre)
class GenreAdmin(ModelAdmin):
    list_display = ("name", "order", "is_active", "book_count")
    list_editable = ("order", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


class CopyInline(TabularInline):
    model = Copy
    extra = 1
    fields = ("inventory_number", "is_available")


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = ("cover_thumb", "title", "category", "published_year",
                    "mode_badge", "rating_display", "is_active")
    list_display_links = ("cover_thumb", "title")
    search_fields = ("title", "isbn")
    list_filter = ("reading_mode", "is_active", "language", "category")
    autocomplete_fields = ("category",)
    filter_horizontal = ("authors",)
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("view_count", "avg_rating", "rating_count", "published_date", "cover_preview")
    list_per_page = 25
    inlines = [CopyInline]

    fieldsets = (
        ("Asosiy", {"fields": ("title", "slug", "authors", "category", "published_year", "language", "isbn")}),
        ("Tavsif va muqova", {"fields": ("description", "cover_image", "cover_preview", "page_count")}),
        ("Raqamli versiyalar", {"fields": ("electronic_version", "audio_version", "reading_mode", "download_allowed")}),
        ("Holat va statistika", {"fields": ("is_active", "view_count", "avg_rating", "rating_count")}),
    )

    @display(description="")
    def cover_thumb(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:44px;width:32px;object-fit:cover;border-radius:4px;">', obj.cover_image.url)
        return format_html('<div style="height:44px;width:32px;border-radius:4px;background:#e8eef7;"></div>')

    @display(description="Muqova")
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:180px;border-radius:8px;">', obj.cover_image.url)
        return "Muqova yo'q"

    @display(description="Turi", label={"Jismoniy": "info", "Raqamli": "success", "Ikkalasi": "warning"})
    def mode_badge(self, obj):
        return obj.get_reading_mode_display()

    @display(description="Reyting")
    def rating_display(self, obj):
        if not obj.rating_count:
            return "—"
        return f"★ {obj.avg_rating} ({obj.rating_count})"


@admin.register(Copy)
class CopyAdmin(ModelAdmin):
    list_display = ("book", "inventory_number", "availability")
    search_fields = ("inventory_number", "book__title")
    list_filter = ("is_available",)
    autocomplete_fields = ("book",)

    @display(description="Holati", label={"Mavjud": "success", "Band": "danger"})
    def availability(self, obj):
        return "Mavjud" if obj.is_available else "Band"


@admin.register(Rental)
class RentalAdmin(ModelAdmin):
    list_display = ("copy", "student", "borrowed_date", "due_date", "status_badge")
    search_fields = ("copy__inventory_number", "copy__book__title",
                     "student__user__username", "student__user__first_name")
    list_filter = ("borrowed_date", "due_date", "return_date")
    autocomplete_fields = ("copy", "student")
    date_hierarchy = "borrowed_date"

    @display(description="Holati", label={"Qaytarilgan": "success", "Faol": "info", "Muddati o'tgan": "danger"})
    def status_badge(self, obj):
        if obj.return_date:
            return "Qaytarilgan"
        return "Muddati o'tgan" if obj.is_overdue else "Faol"
