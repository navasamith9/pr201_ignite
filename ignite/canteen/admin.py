from django.contrib import admin

from .models import CanteenOrder, CanteenOrderItem, MenuItem


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available', 'updated_at')
    list_filter = ('category', 'is_available')
    search_fields = ('name', 'category')
    list_editable = ('is_available',)


class CanteenOrderItemInline(admin.TabularInline):
    model = CanteenOrderItem
    extra = 0
    readonly_fields = ('menu_item', 'item_name', 'unit_price', 'quantity')
    can_delete = False


@admin.register(CanteenOrder)
class CanteenOrderAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'student', 'is_paid', 'status', 'total_amount', 'created_at')
    list_filter = ('is_paid', 'status', 'created_at')
    search_fields = ('student__username', 'student__email')
    readonly_fields = ('student', 'token_number', 'total_amount', 'created_at', 'updated_at')
    inlines = (CanteenOrderItemInline,)
