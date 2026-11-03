from django.contrib import admin

from apps.audit.models import record_event
from .models import (
    CompetitionDivision,
    CompetitionLevel,
    CompetitionRegistration,
    CompetitionSeason,
    RegistrationSequence,
    Syllabus,
    SyllabusTopic,
)


class SyllabusTopicInline(admin.TabularInline):
    model = SyllabusTopic
    extra = 1


@admin.register(CompetitionSeason)
class CompetitionSeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "year", "status", "is_current")
    list_filter = ("status", "is_current")
    prepopulated_fields = {"slug": ("name",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(request, action="competition_season.admin_saved", instance=obj)

    def has_delete_permission(self, _request, _obj=None):
        return False


@admin.register(CompetitionLevel)
class CompetitionLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "min_grade", "max_grade", "display_order")
    prepopulated_fields = {"code": ("name",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(request, action="competition_level.admin_saved", instance=obj)

    def has_delete_permission(self, _request, _obj=None):
        return False


@admin.register(CompetitionDivision)
class CompetitionDivisionAdmin(admin.ModelAdmin):
    list_display = ("season", "level", "grade", "ranking_group")
    list_filter = ("season", "level")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(request, action="competition_division.admin_saved", instance=obj)

    def has_delete_permission(self, _request, _obj=None):
        return False


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    list_display = ("title", "division", "status", "updated_at")
    list_filter = ("status", "division__season")
    inlines = [SyllabusTopicInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(request, action="syllabus.admin_saved", instance=obj)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        record_event(request, action="syllabus_topics.admin_saved", instance=form.instance)

    def has_delete_permission(self, _request, _obj=None):
        return False


@admin.register(CompetitionRegistration)
class CompetitionRegistrationAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "student", "season", "grade", "school_name", "status")
    list_filter = ("season", "status", "division__level")
    search_fields = ("registration_number", "student__username", "student__first_name", "student__last_name")
    readonly_fields = ("registration_number", "student", "season", "division", "school_name", "grade", "created_at")

    def has_add_permission(self, _request):
        return False

    def has_delete_permission(self, _request, _obj=None):
        return False


@admin.register(RegistrationSequence)
class RegistrationSequenceAdmin(admin.ModelAdmin):
    list_display = ("season", "next_number")

    def has_add_permission(self, _request):
        return False

    def has_delete_permission(self, _request, _obj=None):
        return False
