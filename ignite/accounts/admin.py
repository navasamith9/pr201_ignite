from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "branch", "academic_year", "is_staff")
    list_filter = ("role", "branch", "academic_year", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Institute profile", {"fields": ("role", "branch", "academic_year")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Institute profile", {"fields": ("email", "role", "branch", "academic_year")}),
    )
