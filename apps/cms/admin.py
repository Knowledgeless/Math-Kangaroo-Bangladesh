from django.contrib import admin

from apps.audit.models import record_event
from .forms import AboutPageImageForm, AnnouncementImageForm
from .models import (
    AboutPage,
    AboutPageImage,
    Announcement,
    AnnouncementImage,
    FAQ,
    FAQCategory,
    PublicResource,
    PublicationStatus,
    SiteSettings,
)


class AboutPageImageInline(admin.TabularInline):
    model = AboutPageImage
    form = AboutPageImageForm
    extra = 1


@admin.register(AboutPage)
class AboutPageAdmin(admin.ModelAdmin):
    inlines = [AboutPageImageInline]


class AnnouncementImageInline(admin.TabularInline):
    model = AnnouncementImage
    form = AnnouncementImageForm
    extra = 1


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "pinned", "published_at")
    list_filter = ("status", "category", "pinned")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("status", "published_at", "author", "created_at", "updated_at")
    inlines = [AnnouncementImageInline]

    def save_model(self, request, obj, form, change):
        obj.status = PublicationStatus.DRAFT
        obj.published_at = None
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)
        record_event(request, action="announcement.admin_saved_draft", instance=obj)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "status", "display_order")
    list_filter = ("status", "category")
    search_fields = ("question", "answer")
    readonly_fields = ("status", "updated_at")

    def save_model(self, request, obj, form, change):
        obj.status = PublicationStatus.DRAFT
        super().save_model(request, obj, form, change)
        record_event(request, action="faq.admin_saved_draft", instance=obj)


@admin.register(PublicResource)
class PublicResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "status")
    list_filter = ("kind", "status")
    readonly_fields = ("status", "published_at", "created_at")

    def save_model(self, request, obj, form, change):
        obj.status = PublicationStatus.DRAFT
        obj.published_at = None
        super().save_model(request, obj, form, change)
        record_event(request, action="resource.admin_saved_draft", instance=obj)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at",)

    def has_add_permission(self, _request):
        return not SiteSettings.objects.filter(pk=1).exists()

    def has_delete_permission(self, _request, _obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(request, action="site_settings.admin_updated", instance=obj)


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(request, action="faq_category.admin_saved", instance=obj)
