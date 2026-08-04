from django.contrib import admin

from .models import FoundClaim, FoundItem, LostAndFoundNotification, LostItem


@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    list_display = ("item_name", "reporter_name", "roll_number", "lost_place", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("item_name", "reporter_name", "roll_number", "lost_place")


@admin.register(FoundItem)
class FoundItemAdmin(admin.ModelAdmin):
    list_display = ("reporter_name", "roll_number", "created_at")
    search_fields = ("reporter_name", "roll_number", "contact_details")


@admin.register(FoundClaim)
class FoundClaimAdmin(admin.ModelAdmin):
    list_display = ("lost_item", "finder_name", "finder_contact", "similarity_score", "created_at")
    list_filter = ("created_at",)
    search_fields = ("lost_item__item_name", "finder_name", "finder_contact")


@admin.register(LostAndFoundNotification)
class LostAndFoundNotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "lost_item", "title", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
