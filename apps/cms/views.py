from html import unescape
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags

from apps.audit.models import AuditLog, record_event
from apps.competitions.models import CompetitionLevel, CompetitionSeason, Syllabus
from .forms import (
    AboutPageForm,
    AboutPageImageFormSet,
    AnnouncementForm,
    AnnouncementImageFormSet,
    FAQForm,
    HeroSlideForm,
    HeroSlideOrderForm,
    QuestionPaperForm,
    SiteSettingsForm,
    SyllabusForm,
    SyllabusTopicFormSet,
)
from .content_sanitizer import sanitize_about_content
from .models import (
    AboutPage,
    Announcement,
    FAQ,
    FAQCategory,
    HeroSlide,
    PublicResource,
    PublicationStatus,
    QuestionPaper,
    SiteSettings,
)


def home(request):
    return render(request, "public/home.html", _home_context(request))


@login_required
@permission_required("cms.add_heroslide", raise_exception=True)
@permission_required("cms.publish_heroslide", raise_exception=True)
def hero_slide_create(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method != "POST":
        raise Http404
    form = HeroSlideForm(request.POST, request.FILES)
    if form.is_valid():
        slide = form.save(commit=False)
        slide.created_by = request.user
        slide.status = PublicationStatus.PUBLISHED
        slide.published_at = timezone.now()
        slide.save()
        record_event(request, action="hero.published", instance=slide)
        messages.success(request, "Homepage slider image published.")
        return redirect("home")
    errors = " ".join(
        str(error)
        for field_errors in form.errors.values()
        for error in field_errors
    )
    messages.warning(request, errors or "The cover photo could not be saved.")
    return redirect("home")


@login_required
@permission_required("cms.change_heroslide", raise_exception=True)
def hero_slide_order(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method != "POST":
        raise Http404
    slide = get_object_or_404(HeroSlide, pk=pk)
    form = HeroSlideOrderForm(request.POST)
    if form.is_valid():
        slide.display_order = form.cleaned_data["display_order"]
        slide.save(update_fields=["display_order"])
        record_event(request, action="hero.reordered", instance=slide)
        messages.success(request, "Slider display order updated.")
    else:
        errors = " ".join(str(error) for field_errors in form.errors.values() for error in field_errors)
        messages.warning(request, errors or "The display order could not be saved.")
    return redirect("home")


@login_required
@permission_required("cms.change_heroslide", raise_exception=True)
def hero_slide_archive(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method != "POST":
        raise Http404
    slide = get_object_or_404(HeroSlide, pk=pk)
    slide.status = PublicationStatus.ARCHIVED
    slide.save(update_fields=["status"])
    record_event(request, action="hero.archived", instance=slide)
    messages.success(request, "Slider image removed from the homepage.")
    return redirect("home")


def _home_context(request):
    announcements = Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
    ).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())).prefetch_related("images")
    current_season = CompetitionSeason.objects.filter(is_current=True).first()
    can_manage_hero = (
        request.user.is_authenticated
        and request.user.is_staff
        and (
            request.user.has_perm("cms.add_heroslide")
            or request.user.has_perm("cms.change_heroslide")
        )
    )
    slides = HeroSlide.objects.exclude(image="").exclude(status=PublicationStatus.ARCHIVED)
    return {
        "hero_slides": slides.filter(
            status=PublicationStatus.PUBLISHED,
        ).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())),
        "managed_hero_slides": (
            slides
            if can_manage_hero and request.user.has_perm("cms.change_heroslide")
            else ()
        ),
        "can_manage_hero": can_manage_hero,
        "can_change_hero_slide": (
            can_manage_hero and request.user.has_perm("cms.change_heroslide")
        ),
        "can_add_hero_slide": (
            can_manage_hero
            and request.user.has_perm("cms.add_heroslide")
            and request.user.has_perm("cms.publish_heroslide")
        ),
        "levels": CompetitionLevel.objects.all(),
        "current_season": current_season,
        "announcements": announcements[:3],
    }


def announcement_list(request):
    announcements = Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
    ).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())).prefetch_related("images")
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
        Announcement.objects.filter(status=PublicationStatus.PUBLISHED)
        .filter(Q(published_at__isnull=True) | Q(published_at__lte=now))
        .prefetch_related("images"),
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


def about_page(request):
    about = AboutPage.objects.filter(pk=1).first()
    title_default = AboutPage._meta.get_field("title").get_default()
    introduction_default = AboutPage._meta.get_field("introduction").get_default()
    about_title = about.title if about and about.title != title_default else ""
    about_introduction = (
        about.introduction
        if about and about.introduction != introduction_default
        else ""
    )
    content_html = sanitize_about_content(about.content) if about else ""
    lead_match = (
        re.match(r"(?s)(<h2>.*?</h2>)", content_html)
        if not (about_title or about_introduction)
        else None
    )
    lead_html = lead_match.group(1).strip() if lead_match else ""
    remaining_content_html = content_html[len(lead_match.group(1)):].strip() if lead_match else content_html
    page_heading = re.search(r"<h2>(.*?)</h2>", lead_html or content_html)
    lead_body_match = (
        re.match(r"(?s)(<p>.*?</p>)", remaining_content_html)
        if lead_match
        else None
    )
    lead_body_html = lead_body_match.group(1) if lead_body_match else ""
    if lead_body_match:
        remaining_content_html = remaining_content_html[len(lead_body_match.group(1)):].strip()
    about_sections = []
    if remaining_content_html:
        section_blocks = re.split(r"(?=<h2>)", remaining_content_html)
        for section_block in section_blocks:
            section_match = re.match(r"(?s)<h2>(.*?)</h2>(.*)", section_block)
            heading_html = f"<h2>{section_match.group(1)}</h2>" if section_match else ""
            body_html = section_match.group(2).strip() if section_match else section_block.strip()
            if heading_html or body_html:
                about_sections.append({"heading_html": heading_html, "body_html": body_html})
    document_title = about_title or (
        unescape(strip_tags(page_heading.group(1))) if page_heading else ""
    )
    return render(
        request,
        "public/about.html",
        {
            "about": about,
            "about_title": about_title,
            "about_introduction": about_introduction,
            "about_document_title": document_title,
            "about_lead_html": lead_body_html,
            "about_feature_heading_html": lead_html,
            "about_content_html": remaining_content_html,
            "about_sections": about_sections,
            "about_images": about.images.all() if about else (),
        },
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
    public_papers = QuestionPaper.objects.filter(status=PublicationStatus.PUBLISHED).filter(
        Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())
    )
    available_years = list(public_papers.order_by("-year").values_list("year", flat=True).distinct())
    available_categories = list(
        public_papers.order_by("category").values_list("category", flat=True).distinct()
    )
    selected_year = request.GET.get("year", "")
    selected_category = request.GET.get("category", "")
    if selected_year.isdigit() and int(selected_year) in available_years:
        public_papers = public_papers.filter(year=int(selected_year))
    else:
        selected_year = ""
    if selected_category in available_categories:
        public_papers = public_papers.filter(category=selected_category)
    else:
        selected_category = ""
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
        {
            "resources": resources,
            "resource_groups": resource_groups,
            "question_papers": public_papers,
            "paper_years": available_years,
            "paper_categories": available_categories,
            "selected_year": selected_year,
            "selected_category": selected_category,
        },
    )


@login_required
def content_dashboard(request):
    if not (
        request.user.has_perm("cms.view_announcement")
        or request.user.has_perm("competitions.view_syllabus")
    ):
        raise PermissionDenied
    search = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    can_view_content = request.user.has_perm("cms.view_announcement")
    can_view_syllabuses = request.user.has_perm("competitions.view_syllabus")
    announcements = Announcement.objects.all() if can_view_content else Announcement.objects.none()
    faqs = FAQ.objects.select_related("category") if can_view_content else FAQ.objects.none()
    syllabuses = (
        Syllabus.objects.select_related("division__season", "division__level").prefetch_related("topics")
        if can_view_syllabuses
        else Syllabus.objects.none()
    )
    if search:
        announcements = announcements.filter(
            Q(title__icontains=search) | Q(summary__icontains=search) | Q(slug__icontains=search)
        )
        faqs = faqs.filter(Q(question__icontains=search) | Q(answer__icontains=search))
        syllabuses = syllabuses.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if status_filter in PublicationStatus.values:
        announcements = announcements.filter(status=status_filter)
        faqs = faqs.filter(status=status_filter)
        syllabuses = syllabuses.filter(status=status_filter)
    question_papers = (
        QuestionPaper.objects.all() if request.user.has_perm("cms.view_questionpaper") else QuestionPaper.objects.none()
    )
    if search:
        question_papers = question_papers.filter(
            Q(title__icontains=search) | Q(description__icontains=search) | Q(category__icontains=search)
        )
    if status_filter in PublicationStatus.values:
        question_papers = question_papers.filter(status=status_filter)
    return render(
        request,
        "cms/dashboard.html",
        {
            "announcements": Paginator(announcements, 10).get_page(request.GET.get("announcement_page")),
            "faqs": Paginator(faqs, 10).get_page(request.GET.get("faq_page")),
            "syllabuses": syllabuses,
            "question_papers": question_papers,
            "can_view_content": can_view_content,
            "can_view_syllabuses": can_view_syllabuses,
            "can_publish_announcements": request.user.has_perm("cms.publish_announcement"),
            "can_publish_faqs": request.user.has_perm("cms.publish_faq"),
            "can_publish_question_papers": request.user.has_perm("cms.publish_questionpaper"),
            "can_publish_syllabuses": request.user.has_perm("competitions.publish_syllabus"),
            "can_manage_about": request.user.has_perm("cms.manage_aboutpage"),
            "can_manage_question_papers": request.user.has_perm("cms.add_questionpaper")
            or request.user.has_perm("cms.change_questionpaper"),
            "can_manage_syllabuses": request.user.has_perm("competitions.add_syllabus")
            or request.user.has_perm("competitions.change_syllabus"),
            "can_change_site_settings": request.user.has_perm("cms.change_sitesettings"),
            "can_view_audit": request.user.has_perm("audit.view_auditlog"),
            "search": search,
            "status_filter": status_filter,
            "publication_statuses": PublicationStatus.choices,
        },
    )


@login_required
@permission_required("cms.manage_aboutpage", raise_exception=True)
def about_page_edit(request):
    about, _ = AboutPage.objects.get_or_create(pk=1)
    form = AboutPageForm(request.POST or None, instance=about)
    bind_images = request.method == "POST" and (
        "images-TOTAL_FORMS" in request.POST or bool(request.FILES)
    )
    image_formset = AboutPageImageFormSet(
        request.POST if bind_images else None,
        request.FILES if bind_images else None,
        instance=about,
        prefix="images",
    )
    if request.method == "POST" and form.is_valid() and (
        not image_formset.is_bound or image_formset.is_valid()
    ):
        with transaction.atomic():
            about = form.save()
            if image_formset.is_bound:
                image_formset.instance = about
                image_formset.save()
        record_event(request, action="about_page.updated", instance=about)
        messages.success(request, "About page updated.")
        return redirect("cms-dashboard")
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(request, "cms/about_form.html", {"form": form, "image_formset": image_formset})


@login_required
@permission_required("cms.add_questionpaper", raise_exception=True)
def question_paper_create(request):
    return question_paper_edit(request, None)


@login_required
@permission_required("cms.change_questionpaper", raise_exception=True)
def question_paper_update(request, pk):
    return question_paper_edit(request, get_object_or_404(QuestionPaper, pk=pk))


def question_paper_edit(request, instance):
    creating = instance is None
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    if request.method == "POST" and action == "publish" and not request.user.has_perm(
        "cms.publish_questionpaper"
    ):
        raise PermissionDenied
    form = QuestionPaperForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        paper = form.save(commit=False)
        paper.status = (
            PublicationStatus.PUBLISHED if action == "publish" else PublicationStatus.DRAFT
        )
        paper.published_at = timezone.now() if action == "publish" else None
        if creating:
            paper.created_by = request.user
        paper.save()
        record_event(
            request,
            action="question_paper.published" if action == "publish" else "question_paper.saved_draft",
            instance=paper,
        )
        messages.success(
            request,
            "Question PDF published." if action == "publish" else "Question PDF draft saved.",
        )
        return redirect("cms-dashboard")
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "cms/question_paper_form.html",
        {
            "form": form,
            "creating": creating,
            "instance": instance,
            "can_publish": request.user.has_perm("cms.publish_questionpaper"),
        },
    )


@login_required
@permission_required("cms.change_questionpaper", raise_exception=True)
def question_paper_archive(request, pk):
    if request.method != "POST":
        raise Http404
    paper = get_object_or_404(QuestionPaper, pk=pk)
    paper.status = PublicationStatus.ARCHIVED
    paper.save(update_fields=["status", "updated_at"])
    record_event(request, action="question_paper.archived", instance=paper)
    messages.success(request, "Question PDF archived.")
    return redirect("cms-dashboard")


def question_paper_download(request, pk):
    paper = get_object_or_404(QuestionPaper, pk=pk)
    if not paper.is_public():
        raise Http404
    return FileResponse(
        paper.pdf_file.open("rb"),
        as_attachment=True,
        filename=paper.pdf_file.name.rsplit("/", 1)[-1],
        content_type="application/pdf",
    )


@login_required
@permission_required("competitions.add_syllabus", raise_exception=True)
def syllabus_create(request):
    return syllabus_edit(request, None)


@login_required
@permission_required("competitions.change_syllabus", raise_exception=True)
def syllabus_update(request, pk):
    return syllabus_edit(request, get_object_or_404(Syllabus, pk=pk))


def syllabus_edit(request, instance):
    creating = instance is None
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    if request.method == "POST" and action == "publish" and not request.user.has_perm(
        "competitions.publish_syllabus"
    ):
        raise PermissionDenied
    form = SyllabusForm(request.POST or None, instance=instance)
    topic_formset = SyllabusTopicFormSet(
        request.POST or None,
        instance=instance,
        prefix="topics",
    )
    if request.method == "POST" and form.is_valid() and topic_formset.is_valid():
        with transaction.atomic():
            syllabus = form.save(commit=False)
            syllabus.status = (
                Syllabus.Status.PUBLISHED if action == "publish" else Syllabus.Status.DRAFT
            )
            syllabus.save()
            topic_formset.instance = syllabus
            topic_formset.save()
        record_event(
            request,
            action="syllabus.published" if action == "publish" else "syllabus.saved_draft",
            instance=syllabus,
        )
        messages.success(
            request,
            "Syllabus published." if action == "publish" else "Syllabus draft saved.",
        )
        return redirect("cms-dashboard")
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "cms/syllabus_form.html",
        {
            "form": form,
            "topic_formset": topic_formset,
            "creating": creating,
            "can_publish": request.user.has_perm("competitions.publish_syllabus"),
            "can_edit_syllabuses": request.user.has_perm("competitions.change_syllabus"),
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
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
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
    bind_images = request.method == "POST" and (
        "images-TOTAL_FORMS" in request.POST or bool(request.FILES)
    )
    image_formset = AnnouncementImageFormSet(
        request.POST if bind_images else None,
        request.FILES if bind_images else None,
        instance=instance or Announcement(),
        prefix="images",
    )
    if request.method == "POST" and form.is_valid() and (
        not image_formset.is_bound or image_formset.is_valid()
    ):
        with transaction.atomic():
            announcement = form.save(commit=False)
            if creating:
                announcement.author = request.user
            announcement.status = PublicationStatus.PUBLISHED if action == "publish" else PublicationStatus.DRAFT
            announcement.published_at = timezone.now() if action == "publish" else None
            announcement.save()
            if image_formset.is_bound:
                image_formset.instance = announcement
                image_formset.save()
        record_event(
            request,
            action="announcement.published" if action == "publish" else "announcement.saved_draft",
            instance=announcement,
        )
        messages.success(request, "Announcement published." if action == "publish" else "Draft saved.")
        return redirect("cms-dashboard")
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "cms/announcement_form.html",
        {
            "form": form,
            "image_formset": image_formset,
            "creating": creating,
            "can_publish": request.user.has_perm("cms.publish_announcement"),
        },
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
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "cms/faq_form.html",
        {"form": form, "creating": creating, "can_publish": request.user.has_perm("cms.publish_faq")},
    )
