from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_name", "object_id", "ip_address")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("actor__email", "action", "model_name", "object_id")
    readonly_fields = ("actor", "action", "model_name", "object_id", "ip_address", "user_agent", "created_at")

    def has_add_permission(self, _request):
        return False

    def has_change_permission(self, _request, _obj=None):
        return False

    def has_delete_permission(self, _request, _obj=None):
        return False
