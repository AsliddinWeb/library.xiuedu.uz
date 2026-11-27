from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import ItemType, Library, ShelfLocation


class ShelfLocationInline(TabularInline):
    model = ShelfLocation
    extra = 1
    fields = ("code", "name", "floor", "zone", "navigation_hint", "is_active")


@admin.register(Library)
class LibraryAdmin(ModelAdmin):
    list_display = ("name", "code", "kind", "items_count", "shelves_count", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "code", "address")
    inlines = [ShelfLocationInline]

    @display(description="Nusxalar")
    def items_count(self, obj):
        return obj.items.count()

    @display(description="Javonlar")
    def shelves_count(self, obj):
        return obj.shelves.count()


@admin.register(ItemType)
class ItemTypeAdmin(ModelAdmin):
    list_display = ("name", "code", "is_loanable", "default_loan_days",
                    "replacement_cost_default", "items_count", "is_active")
    list_filter = ("is_loanable", "is_active")
    search_fields = ("name", "code")
    list_editable = ("is_loanable", "is_active")

    @display(description="Nusxalar")
    def items_count(self, obj):
        return obj.items.count()


@admin.register(ShelfLocation)
class ShelfLocationAdmin(ModelAdmin):
    list_display = ("code", "name", "library", "directions", "items_count", "is_active")
    list_filter = ("library", "is_active")
    search_fields = ("code", "name", "zone", "navigation_hint")
    autocomplete_fields = ("library",)

    @display(description="Yo'nalish")
    def directions(self, obj):
        return obj.directions

    @display(description="Nusxalar")
    def items_count(self, obj):
        return obj.items.count()
