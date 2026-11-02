from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.models import AuditLog, record_event
from apps.competitions.models import CompetitionLevel, CompetitionSeason, Syllabus
from .forms import AnnouncementForm, FAQForm, HeroSlideForm, SiteSettingsForm
from .models import Announcement, FAQ, FAQCategory, HeroSlide, PublicResource, PublicationStatus, SiteSettings


def home(request):
    announcements = Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
    ).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now()))
    current_season = CompetitionSeason.objects.filter(is_current=True).first()
    return render(
        request,
        "public/home.html",
        {
            "hero": HeroSlide.objects.filter(
                status=PublicationStatus.PUBLISHED,
            ).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())).first(),
            "levels": CompetitionLevel.objects.all(),
            "current_season": current_season,
            "announcements": announcements[:3],
        },
    )


def announcement_list(request):
    announcements = Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
    ).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now()))
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    year = request.GET.get("year", "")
    if search:
        announcements = announcements.filter(
            Q(title__icontains=search) | Q(summary__icontains=search) | Q(content__icontains=search)
        )
    if category in Announcement.Category.values:
        announcements = announcements.filter(category=category)
    if year.isdigit() and len(year) == 4:
        announcements = announcements.filter(published_at__year=year)
    years = (
        Announcement.objects.filter(status=PublicationStatus.PUBLISHED, published_at__isnull=False, published_at__lte=timezone.now())
        .order_by("-published_at__year")
        .values_list("published_at__year", flat=True)
        .distinct()
    )
    page = Paginator(announcements, 9).get_page(request.GET.get("page"))
    return render(
        request,
        "public/announcements.html",
        {
            "page_obj": page,
            "search": search,
            "selected_category": category,
            "selected_year": year,
            "categories": Announcement.Category.choices,
            "years": years,
        },
    )


def announcement_detail(request, slug):
    now = timezone.now()
    announcement = get_object_or_404(
        Announcement.objects.filter(status=PublicationStatus.PUBLISHED).filter(
            Q(published_at__isnull=True) | Q(published_at__lte=now)
        ),
        slug=slug,
    )
    related = Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
        category=announcement.category,
    ).filter(Q(published_at__isnull=True) | Q(published_at__lte=now)).exclude(pk=announcement.pk)[:3]
    return render(request, "public/announcement_detail.html", {"announcement": announcement, "related": related})


def faq_page(request):
    categories = FAQCategory.objects.filter(is_active=True).prefetch_related("questions")
    categories = [
        (category, [faq for faq in category.questions.all() if faq.status == PublicationStatus.PUBLISHED])
        for category in categories
    ]
    return render(
        request,
        "public/faq.html",
        {"categories": categories, "has_faqs": any(faqs for _, faqs in categories)},
    )


def syllabus_page(request):
    syllabuses = list(Syllabus.objects.filter(status=PublicationStatus.PUBLISHED).select_related(
        "division__level", "division__season"
    ).prefetch_related("topics"))
    levels = list(CompetitionLevel.objects.all())
    syllabuses_by_level = {level.pk: [] for level in levels}
    for syllabus in syllabuses:
        syllabuses_by_level[syllabus.division.level_id].append(syllabus)
    return render(
        request,
        "public/syllabus.html",
        {
            "syllabuses": syllabuses,
            "levels": levels,
            "level_sections": [
                {"level": level, "syllabuses": syllabuses_by_level[level.pk]}
                for level in levels
            ],
        },
    )


def questions_page(request):
    resources = PublicResource.objects.filter(status=PublicationStatus.PUBLISHED).filter(
        Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())
    )
    resource_groups = [
        (kind, label, resources.filter(kind=kind))
        for kind, label in PublicResource.Kind.choices
    ]
    return render(
        request,
        "public/questions.html",
        {"resources": resources, "resource_groups": resource_groups},
    )


@login_required
@permission_required("cms.view_announcement", raise_exception=True)
def content_dashboard(request):
    search = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    announcements = Announcement.objects.all()
    faqs = FAQ.objects.select_related("category")
    if search:
        announcements = announcements.filter(
            Q(title__icontains=search) | Q(summary__icontains=search) | Q(slug__icontains=search)
        )
        faqs = faqs.filter(Q(question__icontains=search) | Q(answer__icontains=search))
    if status_filter in PublicationStatus.values:
        announcements = announcements.filter(status=status_filter)
        faqs = faqs.filter(status=status_filter)
    return render(
        request,
        "cms/dashboard.html",
        {
            "announcements": Paginator(announcements, 10).get_page(request.GET.get("announcement_page")),
            "faqs": Paginator(faqs, 10).get_page(request.GET.get("faq_page")),
            "hero_slides": HeroSlide.objects.all(),
            "can_publish_announcements": request.user.has_perm("cms.publish_announcement"),
            "can_publish_faqs": request.user.has_perm("cms.publish_faq"),
            "can_publish_hero": request.user.has_perm("cms.publish_heroslide"),
            "can_change_site_settings": request.user.has_perm("cms.change_sitesettings"),
            "can_view_audit": request.user.has_perm("audit.view_auditlog"),
            "search": search,
            "status_filter": status_filter,
            "publication_statuses": PublicationStatus.choices,
        },
    )


@login_required
@permission_required("audit.view_auditlog", raise_exception=True)
def audit_dashboard(request):
    events = AuditLog.objects.select_related("actor")
    action = request.GET.get("action", "").strip()
    if action:
        events = events.filter(action__icontains=action)
    page = Paginator(events, 50).get_page(request.GET.get("page"))
    return render(request, "cms/audit_dashboard.html", {"page_obj": page, "action_filter": action})


@login_required
@permission_required("cms.change_sitesettings", raise_exception=True)
def site_settings_edit(request):
    settings_record, _ = SiteSettings.objects.get_or_create(
        pk=1,
        defaults={"site_name": "Math Kangaroo Bangladesh"},
    )
    form = SiteSettingsForm(request.POST or None, instance=settings_record)
    if request.method == "POST" and form.is_valid():
        settings_record = form.save()
        record_event(request, action="site_settings.updated", instance=settings_record)
        messages.success(request, "Website details updated.")
        return redirect("cms-dashboard")
    return render(request, "cms/site_settings_form.html", {"form": form})


@login_required
@permission_required("cms.add_announcement", raise_exception=True)
def announcement_create(request):
    return announcement_edit(request, None)


@login_required
@permission_required("cms.change_announcement", raise_exception=True)
def announcement_update(request, pk):
    return announcement_edit(request, get_object_or_404(Announcement, pk=pk))


def announcement_edit(request, instance):
    creating = instance is None
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    if request.method == "POST" and action == "publish" and not request.user.has_perm("cms.publish_announcement"):
        raise PermissionDenied
    form = AnnouncementForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        if creating:
            announcement.author = request.user
        announcement.status = PublicationStatus.PUBLISHED if action == "publish" else PublicationStatus.DRAFT
        announcement.published_at = timezone.now() if action == "publish" else None
        announcement.save()
        record_event(
            request,
            action="announcement.published" if action == "publish" else "announcement.saved_draft",
            instance=announcement,
        )
        messages.success(request, "Announcement published." if action == "publish" else "Draft saved.")
        return redirect("cms-dashboard")
    return render(
        request,
        "cms/announcement_form.html",
        {"form": form, "creating": creating, "can_publish": request.user.has_perm("cms.publish_announcement")},
    )


@login_required
@permission_required("cms.change_announcement", raise_exception=True)
def announcement_archive(request, pk):
    if request.method != "POST":
        raise Http404
    announcement = get_object_or_404(Announcement, pk=pk)
    announcement.status = PublicationStatus.ARCHIVED
    announcement.save(update_fields=["status", "updated_at"])
    record_event(request, action="announcement.archived", instance=announcement)
    messages.success(request, "Announcement archived.")
    return redirect("cms-dashboard")


@login_required
@permission_required("cms.add_faq", raise_exception=True)
def faq_create(request):
    return faq_edit(request, None)


@login_required
@permission_required("cms.change_faq", raise_exception=True)
def faq_update(request, pk):
    return faq_edit(request, get_object_or_404(FAQ, pk=pk))


def faq_edit(request, instance):
    creating = instance is None
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    if request.method == "POST" and action == "publish" and not request.user.has_perm("cms.publish_faq"):
        raise PermissionDenied
    form = FAQForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        faq = form.save(commit=False)
        faq.status = PublicationStatus.PUBLISHED if action == "publish" else PublicationStatus.DRAFT
        faq.save()
        record_event(
            request,
            action="faq.published" if action == "publish" else "faq.saved_draft",
            instance=faq,
        )
        messages.success(request, "FAQ published." if action == "publish" else "Draft saved.")
        return redirect("cms-dashboard")
    return render(
        request,
        "cms/faq_form.html",
        {"form": form, "creating": creating, "can_publish": request.user.has_perm("cms.publish_faq")},
    )


@login_required
@permission_required("cms.add_heroslide", raise_exception=True)
def hero_create(request):
    return hero_edit(request, None)


@login_required
@permission_required("cms.change_heroslide", raise_exception=True)
def hero_update(request, pk):
    return hero_edit(request, get_object_or_404(HeroSlide, pk=pk))


def hero_edit(request, instance):
    creating = instance is None
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    if request.method == "POST" and action == "publish" and not request.user.has_perm("cms.publish_heroslide"):
        raise PermissionDenied
    form = HeroSlideForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        slide = form.save(commit=False)
        if creating:
            slide.created_by = request.user
        slide.status = PublicationStatus.PUBLISHED if action == "publish" else PublicationStatus.DRAFT
        slide.published_at = timezone.now() if action == "publish" else None
        slide.save()
        record_event(
            request,
            action="hero.published" if action == "publish" else "hero.saved_draft",
            instance=slide,
        )
        messages.success(request, "Homepage hero published." if action == "publish" else "Draft saved.")
        return redirect("cms-dashboard")
    return render(
        request,
        "cms/hero_form.html",
        {"form": form, "creating": creating, "can_publish": request.user.has_perm("cms.publish_heroslide")},
    )
