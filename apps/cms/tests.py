from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.audit.models import AuditLog
from .admin import AnnouncementAdmin
from .forms import HeroSlideForm
from .models import Announcement, FAQ, FAQCategory, HeroSlide, PublicationStatus, PublicResource

User = get_user_model()


def uploaded_hero_image(width=1200, height=630):
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(72, 112, 78)).save(buffer, format="JPEG")
    return SimpleUploadedFile("hero.jpg", buffer.getvalue(), content_type="image/jpeg")


class PublicContentTests(TestCase):
    def setUp(self):
        self.published = Announcement.objects.create(
            title="Competition dates announced",
            slug="competition-dates",
            summary="Save the date.",
            content="The competition date is published.",
            category=Announcement.Category.COMPETITION,
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now() - timedelta(hours=1),
        )
        self.draft = Announcement.objects.create(
            title="Internal planning note",
            slug="internal-planning",
            summary="Not public.",
            content="Internal content.",
            status=PublicationStatus.DRAFT,
        )
        self.scheduled = Announcement.objects.create(
            title="Future registration update",
            slug="future-registration",
            summary="Not public yet.",
            content="This is scheduled.",
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now() + timedelta(days=1),
        )

    def test_public_list_excludes_drafts_and_future_publications(self):
        response = self.client.get(reverse("announcement-list"))
        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.draft.title)
        self.assertNotContains(response, self.scheduled.title)

    def test_draft_and_scheduled_detail_urls_return_404(self):
        for slug in (self.draft.slug, self.scheduled.slug):
            with self.subTest(slug=slug):
                response = self.client.get(reverse("announcement-detail", args=[slug]))
                self.assertEqual(response.status_code, 404)
                self.assertContains(response, "A small detour", status_code=404)

    def test_filters_search_category_and_year(self):
        response = self.client.get(reverse("announcement-list"), {"q": "dates", "category": "competition"})
        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.scheduled.title)

    def test_draft_faq_and_resource_are_not_public(self):
        category = FAQCategory.objects.create(name="Families", slug="families")
        FAQ.objects.create(category=category, question="Draft question?", answer="Not public.")
        PublicResource.objects.create(
            title="Unreleased paper",
            slug="unreleased-paper",
            kind=PublicResource.Kind.PAST_PAPER,
            status=PublicationStatus.DRAFT,
        )
        self.assertNotContains(self.client.get(reverse("faq")), "Draft question?")
        self.assertNotContains(self.client.get(reverse("questions")), "Unreleased paper")

    def test_faq_and_question_pages_have_clear_empty_states(self):
        self.assertContains(self.client.get(reverse("faq")), "Answers are on their way")
        self.assertContains(self.client.get(reverse("questions")), "Practice materials are on their way")

    def test_public_resource_grade_range_is_validated(self):
        resource = PublicResource(
            title="Practice",
            slug="practice",
            kind=PublicResource.Kind.PRACTICE,
            grade_min=9,
            grade_max=5,
        )
        with self.assertRaises(ValidationError):
            resource.full_clean()

    def test_announcement_images_require_accessible_alt_text(self):
        announcement = Announcement(
            title="Image update",
            slug="image-update",
            summary="An image is included.",
            content="Public announcement.",
            cover_image_url="https://images.example.org/competition.jpg",
        )
        with self.assertRaises(ValidationError) as error:
            announcement.full_clean()
        self.assertIn("cover_image_alt_text", error.exception.message_dict)


class ContentWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="editor0001", email="editor@example.org", password="Sensible-family-pass-849!")
        content_type = ContentType.objects.get_for_model(Announcement)
        permissions = Permission.objects.filter(
            content_type=content_type,
            codename__in=("view_announcement", "add_announcement", "change_announcement", "publish_announcement"),
        )
        self.user.user_permissions.add(*permissions)

    def test_publisher_can_publish_and_action_is_audited(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("cms-announcement-create"),
            {
                "title": "Registration opens",
                "slug": "registration-opens",
                "summary": "Applications are open.",
                "content": "Families can now register.",
                "category": "registration",
                "action": "publish",
            },
        )
        self.assertRedirects(response, reverse("cms-dashboard"))
        announcement = Announcement.objects.get(slug="registration-opens")
        self.assertEqual(announcement.status, PublicationStatus.PUBLISHED)
        self.assertIsNotNone(announcement.published_at)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.user,
                action="announcement.published",
                object_id=str(announcement.pk),
            ).exists()
        )

    def test_editor_cannot_publish_without_publish_permission(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="publish_announcement"))
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("cms-announcement-create"),
            {
                "title": "Private draft",
                "slug": "private-draft",
                "summary": "Not ready.",
                "content": "Should not publish.",
                "category": "general",
                "action": "publish",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Announcement.objects.filter(slug="private-draft").exists())

    def test_editor_can_save_draft_but_it_stays_private(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="publish_announcement"))
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("cms-announcement-create"),
            {
                "title": "Draft update",
                "slug": "draft-update",
                "summary": "Still in review.",
                "content": "Not public.",
                "category": "general",
                "action": "draft",
            },
        )
        self.assertRedirects(response, reverse("cms-dashboard"))
        self.assertEqual(Announcement.objects.get(slug="draft-update").status, PublicationStatus.DRAFT)

    def test_staff_can_reach_older_announcements_through_pagination(self):
        self.client.force_login(self.user)
        for index in range(11):
            Announcement.objects.create(
                title=f"Management entry {index}",
                slug=f"management-entry-{index}",
                summary="Staff-only listing fixture.",
                content="Private draft.",
            )
        response = self.client.get(reverse("cms-dashboard"), {"announcement_page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Management entry 0")
        self.assertNotContains(response, "Management entry 10")

    def test_admin_edits_of_live_announcements_return_them_to_draft_and_audit(self):
        announcement = Announcement.objects.create(
            title="Live news",
            slug="live-news",
            summary="Current published information.",
            content="Public copy.",
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        request = RequestFactory().post("/admin/cms/announcement/")
        request.user = self.user

        AnnouncementAdmin(Announcement, AdminSite()).save_model(
            request, announcement, form=None, change=True
        )

        announcement.refresh_from_db()
        self.assertEqual(announcement.status, PublicationStatus.DRAFT)
        self.assertIsNone(announcement.published_at)
        self.assertTrue(AuditLog.objects.filter(action="announcement.admin_saved_draft").exists())

    def test_cms_dashboard_requires_explicit_view_permission(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="view_announcement"))
        self.client.force_login(self.user)
        response = self.client.get(reverse("cms-dashboard"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "A little boundary", status_code=403)

    def test_audit_log_is_limited_to_auditors(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("audit-dashboard")).status_code, 403)

        auditor = User.objects.create_user(username="auditor0001", email="auditor@example.org", password="Sensible-family-pass-849!")
        auditor.groups.add(Group.objects.get(name="Auditor"))
        response = self.client.get(reverse("audit-dashboard"))
        self.assertEqual(response.status_code, 403)
        self.client.force_login(auditor)
        self.assertEqual(self.client.get(reverse("audit-dashboard")).status_code, 200)

    def test_hero_form_accepts_only_required_image_ratio_and_size(self):
        valid = HeroSlideForm(
            {"display_order": 1},
            {"image": uploaded_hero_image()},
        )
        wrong_ratio = HeroSlideForm(
            {"display_order": 1},
            {"image": uploaded_hero_image(width=1200, height=600)},
        )
        too_large = HeroSlideForm(
            {"display_order": 1},
            {"image": SimpleUploadedFile(
                "oversized.jpg",
                b"x" * HeroSlide.MAX_IMAGE_SIZE,
                content_type="image/jpeg",
            )},
        )

        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(wrong_ratio.is_valid())
        self.assertIn("1200 × 630", str(wrong_ratio.errors))
        self.assertFalse(too_large.is_valid())
        self.assertIn("smaller than 300 KB", str(too_large.errors))

    def test_staff_groups_are_seeded_with_separated_draft_and_publish_rights(self):
        editor = Group.objects.get(name="Content Editor")
        publisher = Group.objects.get(name="Content Publisher")
        editor_permissions = set(editor.permissions.values_list("codename", flat=True))
        publisher_permissions = set(publisher.permissions.values_list("codename", flat=True))
        self.assertIn("add_announcement", editor_permissions)
        self.assertNotIn("publish_announcement", editor_permissions)
        self.assertIn("publish_heroslide", editor_permissions)
        self.assertIn("publish_announcement", publisher_permissions)

    def test_content_dashboard_and_django_admin_do_not_manage_hero_slides(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("cms-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Homepage hero")
        self.assertNotContains(response, "Add a hero slide")
        self.assertFalse(admin.site.is_registered(HeroSlide))


class HeroSlideManagementTests(TestCase):
    def setUp(self):
        media_directory = TemporaryDirectory()
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_directory.cleanup)
        self.addCleanup(media_settings.disable)

        self.staff = User.objects.create_user(
            username="sliderstaff",
            email="sliderstaff@example.org",
            is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label="cms",
            codename__in=("add_heroslide", "change_heroslide", "publish_heroslide"),
        )
        self.staff.user_permissions.add(*permissions)

    def test_staff_can_add_order_and_remove_homepage_images(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("hero-slide-create"),
            {"display_order": 3, "image": uploaded_hero_image()},
        )

        self.assertRedirects(response, reverse("home"))
        slide = HeroSlide.objects.get(created_by=self.staff)
        self.assertEqual(slide.display_order, 3)
        self.assertEqual(slide.status, PublicationStatus.PUBLISHED)
        self.assertEqual(slide.created_by, self.staff)
        self.assertTrue(AuditLog.objects.filter(action="hero.published", object_id=str(slide.pk)).exists())
        self.assertContains(self.client.get(reverse("home")), slide.image.url)
        self.assertTrue(slide.image.storage.exists(slide.image.name))
        with override_settings(DEBUG=True):
            image_response = self.client.get(slide.image.url)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response["Content-Type"], "image/jpeg")

        response = self.client.post(
            reverse("hero-slide-order", args=[slide.pk]),
            {"display_order": 1},
        )
        self.assertRedirects(response, reverse("home"))
        slide.refresh_from_db()
        self.assertEqual(slide.display_order, 1)

        response = self.client.post(reverse("hero-slide-remove", args=[slide.pk]))
        self.assertRedirects(response, reverse("home"))
        slide.refresh_from_db()
        self.assertEqual(slide.status, PublicationStatus.ARCHIVED)
        self.assertTrue(HeroSlide.objects.filter(pk=slide.pk).exists())
        self.assertNotContains(self.client.get(reverse("home")), slide.image.url)
        self.assertTrue(AuditLog.objects.filter(action="hero.archived", object_id=str(slide.pk)).exists())

    def test_homepage_shows_image_slider_and_manager_only_to_authorized_staff(self):
        slide = HeroSlide.objects.create(
            title="Legacy hero title",
            image=uploaded_hero_image(),
            display_order=1,
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        draft = HeroSlide.objects.create(
            image=uploaded_hero_image(),
            display_order=2,
            status=PublicationStatus.DRAFT,
        )
        scheduled = HeroSlide.objects.create(
            image=uploaded_hero_image(),
            display_order=3,
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now() + timedelta(days=1),
        )

        self.client.force_login(self.staff)
        staff_response = self.client.get(reverse("home"))
        self.assertContains(staff_response, "hero-image-slider")
        self.assertContains(staff_response, "Change cover photo")
        self.assertContains(staff_response, "1200 × 630")
        self.assertContains(staff_response, slide.image.url)
        self.assertNotContains(staff_response, "Legacy hero title")
        self.assertEqual(staff_response.context["hero_slides"].count(), 1)

        self.client.logout()
        public_response = self.client.get(reverse("home"))
        self.assertContains(public_response, "hero-image-slider")
        self.assertContains(public_response, slide.image.url)
        self.assertNotContains(public_response, draft.image.url)
        self.assertNotContains(public_response, scheduled.image.url)
        self.assertNotContains(public_response, "Manage the slider")
        self.assertNotContains(public_response, "Add slider image")

    def test_homepage_uses_image_only_placeholder_when_no_slide_is_published(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "images/homepage-hero-classroom.jpg")
        self.assertNotContains(response, "Think boldly.")
        self.assertNotContains(response, "Solve joyfully.")

    def test_upload_errors_show_toasts_without_creating_a_slide(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("hero-slide-create"),
            {"display_order": 0, "image": uploaded_hero_image(width=1200, height=600)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "toast-warning")
        self.assertContains(response, "1200 × 630")
        self.assertNotContains(response, "field-error")
        self.assertFalse(HeroSlide.objects.filter(created_by=self.staff).exists())

    def test_invalid_display_order_is_reported_only_in_a_toast(self):
        slide = HeroSlide.objects.create(
            image=uploaded_hero_image(),
            display_order=1,
            status=PublicationStatus.PUBLISHED,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("hero-slide-order", args=[slide.pk]),
            {"display_order": -1},
            follow=True,
        )

        self.assertContains(response, "toast-warning")
        self.assertContains(response, "Ensure this value is greater than or equal to 0.")
        self.assertNotContains(response, "field-error")
        slide.refresh_from_db()
        self.assertEqual(slide.display_order, 1)

    def test_non_staff_cannot_manage_slides_even_with_model_permissions(self):
        student = User.objects.create_user(
            username="notstaff",
            email="notstaff@example.org",
        )
        permissions = Permission.objects.filter(
            content_type__app_label="cms",
            codename__in=("add_heroslide", "change_heroslide", "publish_heroslide"),
        )
        student.user_permissions.add(*permissions)
        self.client.force_login(student)

        response = self.client.post(
            reverse("hero-slide-create"),
            {"display_order": 0, "image": uploaded_hero_image()},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(HeroSlide.objects.filter(created_by=student).exists())
