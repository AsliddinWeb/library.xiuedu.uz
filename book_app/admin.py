from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Author,
    Book,
    Contributor,
    CourseReserve,
    CourseReserveItem,
    Genre,
    Item,
    ItemStatusLog,
    Publisher,
    Rental,
    Series,
    Subject,
)


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


class ContributorInline(TabularInline):
    """Mualliflar endi rol bilan biriktiriladi (M2M o'rniga through-model)."""
    model = Contributor
    extra = 1
    fields = ("author", "role", "order")
    autocomplete_fields = ("author",)


class ItemInline(TabularInline):
    model = Item
    extra = 1
    fields = ("barcode", "inventory_number", "item_type", "library", "shelf_location", "status")
    show_change_link = True


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = ("cover_thumb", "title", "category", "published_year",
                    "mode_badge", "rating_display", "is_active")
    list_display_links = ("cover_thumb", "title")
    search_fields = ("title", "subtitle", "isbn", "udc", "authors__full_name")
    list_filter = ("record_type", "reading_mode", "is_active", "is_textbook",
                   "language", "category")
    autocomplete_fields = ("category",)
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("view_count", "loan_count", "items_count", "available_count",
                       "avg_rating", "rating_count", "published_date", "cover_preview")
    list_per_page = 25
    inlines = [ContributorInline, ItemInline]

    fieldsets = (
        ("Asosiy", {"fields": ("record_type", "title", "subtitle", "parallel_title", "slug",
                               "category", "subjects")}),
        ("Nashr", {"fields": ("publisher", "place_of_publication", "published_year",
                              "edition_statement", "series", "series_number", "page_count")}),
        ("Identifikatorlar va klassifikatsiya", {
            "fields": ("isbn", "issn", "doi", "udc", "bbk", "author_sign"),
        }),
        ("Mazmun", {"fields": ("description", "annotation", "contents_note", "target_audience",
                               "language", "original_language")}),
        ("Universitet", {"fields": ("faculty", "department", "is_textbook")}),
        ("Muqova", {"fields": ("cover_image", "cover_preview")}),
        ("Raqamli versiyalar", {"fields": ("electronic_version", "audio_version",
                                           "reading_mode", "download_allowed")}),
        ("Holat va statistika", {"fields": ("is_active", "view_count", "loan_count",
                                            "items_count", "available_count",
                                            "avg_rating", "rating_count")}),
    )
    filter_horizontal = ("subjects",)

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


@admin.register(Item)
class ItemAdmin(ModelAdmin):
    list_display = ("barcode", "book", "inventory_number", "item_type", "library",
                    "shelf_location", "status_badge")
    list_display_links = ("barcode", "book")
    search_fields = ("barcode", "inventory_number", "book__title", "call_number")
    list_filter = ("status", "item_type", "library", "condition", "acquisition_source")
    autocomplete_fields = ("book",)
    list_select_related = ("book", "item_type", "library", "shelf_location")
    readonly_fields = ("is_available", "loan_count", "created_at", "updated_at")
    list_per_page = 50

    fieldsets = (
        ("Identifikatsiya", {"fields": ("book", "barcode", "inventory_number", "call_number",
                                        "volume_number", "copy_number")}),
        ("Joylashuv", {"fields": ("library", "item_type", "shelf_location")}),
        ("Holat", {"fields": ("status", "is_available", "not_for_loan_reason",
                              "condition", "condition_note")}),
        ("Qabul va moliya", {"fields": ("acquired_on", "acquisition_source", "price",
                                        "replacement_price")}),
        ("Hisob", {"fields": ("last_seen_at", "loan_count", "withdrawn_on",
                              "created_at", "updated_at")}),
    )

    @display(description="Holati", label={
        "Mavjud": "success", "Ijarada": "info", "Ushlab turilgan": "warning",
        "Yo'lda": "warning", "Qayta ishlashda": "info", "Shikastlangan": "danger",
        "Yo'qolgan": "danger", "Hisobdan chiqarilgan": "danger", "Faqat zalda": "info",
    })
    def status_badge(self, obj):
        return obj.get_status_display()


@admin.register(ItemStatusLog)
class ItemStatusLogAdmin(ModelAdmin):
    list_display = ("changed_at", "item", "from_status", "to_status", "reason", "changed_by")
    list_filter = ("to_status", "changed_at")
    search_fields = ("item__barcode", "item__inventory_number", "reason", "document_no")
    list_select_related = ("item", "changed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Publisher)
class PublisherAdmin(ModelAdmin):
    list_display = ("name", "city", "books_count")
    search_fields = ("name", "city")

    @display(description="Kitoblar")
    def books_count(self, obj):
        return obj.books.count()


@admin.register(Series)
class SeriesAdmin(ModelAdmin):
    list_display = ("name", "issn", "publisher")
    search_fields = ("name", "issn")
    autocomplete_fields = ("publisher",)


@admin.register(Subject)
class SubjectAdmin(ModelAdmin):
    list_display = ("name", "kind", "code", "parent", "books_count")
    list_filter = ("kind",)
    search_fields = ("name", "code")
    autocomplete_fields = ("parent",)


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


class CourseReserveItemInline(TabularInline):
    model = CourseReserveItem
    extra = 0
    autocomplete_fields = ("book",)


@admin.register(CourseReserve)
class CourseReserveAdmin(ModelAdmin):
    list_display = ("course_name", "teacher", "faculty", "semester", "is_active")
    list_filter = ("is_active", "semester")
    search_fields = ("course_name", "course_code", "search_text")
    autocomplete_fields = ("teacher",)
    exclude = ("created_by",)
    inlines = [CourseReserveItemInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
