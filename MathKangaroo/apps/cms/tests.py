from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.audit.models import AuditLog
from .admin import AnnouncementAdmin
from .forms import HeroSlideForm
from .models import Announcement, FAQ, FAQCategory, PublicationStatus, PublicResource

User = get_user_model()


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

    def test_hero_form_accepts_local_links_and_rejects_script_urls(self):
        local_link = HeroSlideForm({"title": "Welcome", "button_1_url": "#levels", "display_order": 1})
        unsafe_link = HeroSlideForm(
            {"title": "Welcome", "button_1_url": "javascript:alert(1)", "display_order": 1}
        )
        self.assertTrue(local_link.is_valid(), local_link.errors)
        self.assertFalse(unsafe_link.is_valid())

    def test_staff_groups_are_seeded_with_separated_draft_and_publish_rights(self):
        editor = Group.objects.get(name="Content Editor")
        publisher = Group.objects.get(name="Content Publisher")
        editor_permissions = set(editor.permissions.values_list("codename", flat=True))
        publisher_permissions = set(publisher.permissions.values_list("codename", flat=True))
        self.assertIn("add_announcement", editor_permissions)
        self.assertNotIn("publish_announcement", editor_permissions)
        self.assertIn("publish_announcement", publisher_permissions)
