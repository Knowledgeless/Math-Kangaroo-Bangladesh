from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import GuardianProfile, StudentProfile, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    ordering = ("username",)
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name", "role", "password1", "password2"),
        }),
    )
    filter_horizontal = ("groups", "user_permissions")


admin.site.register(StudentProfile)


@admin.register(GuardianProfile)
class GuardianProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_language")
    search_fields = ("user__username", "user__email")
