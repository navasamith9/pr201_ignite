from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "branch", "academic_year", "is_staff")
    list_filter = ("role", "branch", "academic_year", "is_staff", "is_global_admin_grant", "is_lhtc_admin", "is_phc_admin", "is_bus_admin", "is_canteen_admin")
    fieldsets = UserAdmin.fieldsets + (
        ("Institute profile", {"fields": ("role", "branch", "academic_year")}),
        ("Service administrator access", {"fields": ("is_lhtc_admin", "is_phc_admin", "is_bus_admin", "is_canteen_admin")}),
        ("Global administrator grant state", {"fields": ("is_global_admin_grant", "global_admin_previous_role", "global_admin_previous_staff")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Institute profile", {"fields": ("email", "role", "branch", "academic_year")}),
        ("Service administrator access", {"fields": ("is_lhtc_admin", "is_phc_admin", "is_bus_admin", "is_canteen_admin")}),
        ("Global administrator grant state", {"fields": ("is_global_admin_grant", "global_admin_previous_role", "global_admin_previous_staff")}),
    )
