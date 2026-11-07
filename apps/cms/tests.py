from io import BytesIO
from pathlib import Path
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
from apps.competitions.models import (
    CompetitionDivision,
    CompetitionLevel,
    CompetitionSeason,
    Syllabus,
    SyllabusTopic,
)
from .admin import AnnouncementAdmin, AnnouncementImageInline
from .forms import AboutPageForm, AnnouncementImageForm, HeroSlideForm, QuestionPaperForm
from .models import (
    AboutPage,
    AboutPageImage,
    Announcement,
    AnnouncementImage,
    FAQ,
    FAQCategory,
    HeroSlide,
    PublicationStatus,
    PublicResource,
    QuestionPaper,
)

User = get_user_model()


def uploaded_hero_image(width=1200, height=630):
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(72, 112, 78)).save(buffer, format="JPEG")
    return SimpleUploadedFile("hero.jpg", buffer.getvalue(), content_type="image/jpeg")


def uploaded_test_image(name="news.jpg", width=1200, height=630, padding=0):
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(72, 112, 78)).save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue() + b"x" * padding, content_type="image/jpeg")


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

    def test_announcement_image_uploads_require_1200_by_630_and_under_300_kb(self):
        valid = AnnouncementImageForm(
            {"alt_text": "Students at the competition", "display_order": "0"},
            {"image": uploaded_test_image()},
        )
        wrong_ratio = AnnouncementImageForm(
            {"alt_text": "Students at the competition", "display_order": "0"},
            {"image": uploaded_test_image(width=1199)},
        )
        oversized = AnnouncementImageForm(
            {"alt_text": "Students at the competition", "display_order": "0"},
            {"image": uploaded_test_image(padding=AnnouncementImage.MAX_IMAGE_SIZE)},
        )

        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(wrong_ratio.is_valid())
        self.assertIn("1200 × 630", str(wrong_ratio.errors))
        self.assertFalse(oversized.is_valid())
        self.assertIn("smaller than 300 KB", str(oversized.errors))

    def test_about_page_uses_managed_content_when_available(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.context["about_title"], "")
        self.assertEqual(response.context["about_introduction"], "")
        self.assertEqual(response.context["about_document_title"], "")
        self.assertNotContains(response, "A joyful mathematics challenge for curious students.")

        AboutPage.objects.create(
            pk=1,
            title="Our journey",
            introduction="Learning through joyful challenges.",
            content="We bring creative mathematics to students.\n\nEvery grade can join.",
        )
        response = self.client.get(reverse("about"))
        self.assertContains(response, "Our journey")
        self.assertContains(response, "Every grade can join.")

    def test_about_page_uses_saved_copy_without_invented_layout_text(self):
        AboutPage.objects.create(
            pk=1,
            content=(
                "What is Math Kangaroo?\n"
                "The world’s largest international mathematics competition.\n\n"
                "History & Origins\n"
                "The story began with a creative idea."
            ),
        )

        response = self.client.get(reverse("about"))

        self.assertContains(response, "<h2>What is Math Kangaroo?</h2>")
        self.assertEqual(response.context["about_document_title"], "What is Math Kangaroo?")
        self.assertContains(response, "The world’s largest international mathematics competition.")
        self.assertContains(response, "<h2>History &amp; Origins</h2>")
        self.assertContains(response, "The story began with a creative idea.")
        self.assertNotContains(response, "Curiosity first")
        self.assertNotContains(response, "From “what if?” to “I got it!”")

    def test_about_page_rich_content_is_sanitized_and_preserves_formatting(self):
        AboutPage.objects.create(
            pk=1,
            content=(
                '<h2>A <strong>bold</strong> idea</h2>'
                '<p><a href="javascript:alert(1)" onclick="alert(1)">Curiosity</a>'
                '<script>alert("unsafe")</script></p>'
                '<p><span data-text-size="large" style="color:red">Think big.</span></p>'
            ),
        )

        response = self.client.get(reverse("about"))

        self.assertContains(response, "<h2>A <strong>bold</strong> idea</h2>")
        self.assertContains(response, "<a>Curiosity</a>")
        self.assertContains(response, '<span data-text-size="large">Think big.</span>')
        self.assertNotContains(response, "javascript:")
        self.assertNotContains(response, "onclick")
        self.assertNotContains(response, "<script>")

    def test_about_form_sanitizes_content_and_formats_legacy_plain_text(self):
        form = AboutPageForm(
            {
                "title": "Our story",
                "introduction": "A challenge for curious learners.",
                "content": '<p><em>Creative thinking</em><b> and bold</b></p><img src=x onerror=alert(1)>',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["content"],
            "<p><em>Creative thinking</em><strong> and bold</strong></p>",
        )

        about = AboutPage.objects.create(content="First paragraph.\n\nSecond paragraph.")
        edit_form = AboutPageForm(instance=about)
        self.assertEqual(
            edit_form.initial["content"],
            "<p>First paragraph.</p><p>Second paragraph.</p>",
        )

    def test_question_papers_filter_and_download_only_published_pdfs(self):
        with TemporaryDirectory() as media_directory, TemporaryDirectory() as private_directory, override_settings(
            MEDIA_ROOT=media_directory, PRIVATE_MEDIA_ROOT=private_directory
        ):
            older = QuestionPaper.objects.create(
                title="2025 Ecolier Questions",
                year=2025,
                category="Ecolier",
                pdf_file=SimpleUploadedFile("ecolier-2025.pdf", b"%PDF-1.4\nolder"),
                status=PublicationStatus.PUBLISHED,
            )
            latest = QuestionPaper.objects.create(
                title="2026 Ecolier Questions",
                year=2026,
                category="Ecolier",
                pdf_file=SimpleUploadedFile("ecolier-2026.pdf", b"%PDF-1.4\nlatest"),
                status=PublicationStatus.PUBLISHED,
            )
            draft = QuestionPaper.objects.create(
                title="Private 2026 Benjamin Questions",
                year=2026,
                category="Benjamin",
                pdf_file=SimpleUploadedFile("private.pdf", b"%PDF-1.4\nprivate"),
            )
            response = self.client.get(reverse("questions"), {"year": "2026", "category": "Ecolier"})
            self.assertContains(response, latest.title)
            self.assertNotContains(response, older.title)
            self.assertNotContains(response, draft.title)

            download = self.client.get(reverse("question-paper-download", args=[latest.pk]))
            self.assertEqual(download["Content-Type"], "application/pdf")
            self.assertIn("attachment", download["Content-Disposition"])
            self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.4\nlatest")
            self.assertEqual(
                self.client.get(reverse("question-paper-download", args=[draft.pk])).status_code,
                404,
            )

    def test_question_paper_upload_requires_pdf_content_and_enforces_size(self):
        valid = QuestionPaperForm(
            {"title": "Sample", "year": 2026, "category": "Ecolier"},
            {"pdf_file": SimpleUploadedFile("sample.pdf", b"%PDF-1.4\ncontents")},
        )
        invalid_content = QuestionPaperForm(
            {"title": "Not a PDF", "year": 2026, "category": "Ecolier"},
            {"pdf_file": SimpleUploadedFile("not-a-pdf.pdf", b"not a pdf")},
        )
        oversized = QuestionPaperForm(
            {"title": "Too large", "year": 2026, "category": "Ecolier"},
            {"pdf_file": SimpleUploadedFile("large.pdf", b"%PDF-" + b"x" * QuestionPaper.MAX_FILE_SIZE)},
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(invalid_content.is_valid())
        self.assertIn("valid PDF", str(invalid_content.errors))
        self.assertFalse(oversized.is_valid())
        self.assertIn("20 MB", str(oversized.errors))


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

    def test_announcement_editor_exposes_repeatable_image_upload_fields(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("cms-announcement-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="images-0-image"')
        self.assertContains(response, "1200 × 630")
        self.assertContains(response, "smaller than 300 KB")
        self.assertContains(response, "data-add-image")

    def test_publisher_can_upload_multiple_announcement_images(self):
        with TemporaryDirectory() as media_directory, override_settings(MEDIA_ROOT=media_directory):
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("cms-announcement-create"),
                {
                    "title": "Competition photo update",
                    "slug": "competition-photo-update",
                    "summary": "Photos from the event.",
                    "content": "The competition brought students together.",
                    "category": "competition",
                    "images-TOTAL_FORMS": "2",
                    "images-INITIAL_FORMS": "0",
                    "images-MIN_NUM_FORMS": "0",
                    "images-MAX_NUM_FORMS": "1000",
                    "images-0-image": uploaded_test_image("event-one.jpg"),
                    "images-0-alt_text": "Students solving a problem",
                    "images-0-display_order": "0",
                    "images-1-image": uploaded_test_image("event-two.jpg"),
                    "images-1-alt_text": "Students sharing their answers",
                    "images-1-display_order": "1",
                    "action": "publish",
                },
            )

            self.assertRedirects(response, reverse("cms-dashboard"))
            announcement = Announcement.objects.get(slug="competition-photo-update")
            self.assertEqual(announcement.images.count(), 2)
            detail = self.client.get(announcement.get_absolute_url())
            self.assertContains(detail, "Students solving a problem")
            self.assertContains(detail, "Students sharing their answers")
            self.assertContains(self.client.get(reverse("announcement-list")), "Students solving a problem")
            self.assertContains(self.client.get(reverse("home")), "Students solving a problem")

    def _announcement_post(self, **image_fields):
        data = {
            "title": "Photo-less update",
            "slug": "photo-less-update",
            "summary": "An update.",
            "content": "Details.",
            "category": "competition",
            "images-TOTAL_FORMS": "1",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "images-0-display_order": "0",
            "action": "publish",
        }
        data.update(image_fields)
        return data

    def test_image_row_without_a_file_is_rejected_instead_of_saved_empty(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("cms-announcement-create"),
            self._announcement_post(**{"images-0-alt_text": "Photo I forgot to attach"}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose an image file for this row")
        self.assertFalse(Announcement.objects.filter(slug="photo-less-update").exists())
        self.assertFalse(AnnouncementImage.objects.exists())

    def test_blank_image_row_is_ignored_and_announcement_saves(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("cms-announcement-create"), self._announcement_post())
        self.assertRedirects(response, reverse("cms-dashboard"))
        announcement = Announcement.objects.get(slug="photo-less-update")
        self.assertEqual(announcement.images.count(), 0)

    def test_existing_image_is_kept_when_editing_without_a_new_upload(self):
        with TemporaryDirectory() as media_directory, override_settings(MEDIA_ROOT=media_directory):
            self.client.force_login(self.user)
            self.client.post(
                reverse("cms-announcement-create"),
                self._announcement_post(**{
                    "images-0-image": uploaded_test_image("kept.jpg"),
                    "images-0-alt_text": "Original photo",
                }),
            )
            announcement = Announcement.objects.get(slug="photo-less-update")
            image = announcement.images.get()
            response = self.client.post(
                reverse("cms-announcement-edit", args=[announcement.pk]),
                self._announcement_post(**{
                    "summary": "Edited summary.",
                    "images-INITIAL_FORMS": "1",
                    "images-0-id": str(image.pk),
                    "images-0-announcement": str(announcement.pk),
                    "images-0-alt_text": "Updated alt text",
                }),
            )
            self.assertRedirects(response, reverse("cms-dashboard"))
            image.refresh_from_db()
            self.assertEqual(image.alt_text, "Updated alt text")
            self.assertTrue(image.image.name.startswith("announcements/kept"))

    def test_admin_inline_rejects_an_image_row_that_has_no_file(self):
        # The Django Admin inline is a second way in, so it needs the same guard
        # as the content desk: a row with alt text but no file must not be saved.
        inline = AnnouncementImageInline(Announcement, AdminSite())
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(
            username="siteadmin0001", email="admin@example.org", password="Sensible-family-pass-849!"
        )
        formset_class = inline.get_formset(request)
        management = {
            "images-TOTAL_FORMS": "1",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "images-0-display_order": "0",
        }
        filled_in = formset_class(data={**management, "images-0-alt_text": "Alt without a file"}, files={})
        self.assertFalse(filled_in.is_valid())
        self.assertIn("image", filled_in.errors[0])
        blank_extra_row = formset_class(data={**management, "images-0-alt_text": ""}, files={})
        self.assertTrue(blank_extra_row.is_valid())

    def test_public_pages_skip_image_rows_that_have_no_file(self):
        # Rows saved without a file by older code must not break public pages.
        announcement = Announcement.objects.create(
            title="Legacy row",
            slug="legacy-row",
            summary="Has an image row without a file.",
            content="Body.",
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        AnnouncementImage.objects.create(announcement=announcement, image="", alt_text="Missing file")
        for url in (reverse("announcement-list"), reverse("home"), announcement.get_absolute_url()):
            response = self.client.get(url)
            self.assertContains(response, "Legacy row")
            self.assertNotContains(response, "Missing file")

    def _grant(self, *codenames):
        self.user.user_permissions.add(
            *Permission.objects.filter(codename__in=codenames)
        )
        self.user = User.objects.get(pk=self.user.pk)

    def test_content_desk_rows_offer_edit_archive_and_delete_icons(self):
        self._grant("delete_announcement", "view_faq", "change_faq", "delete_faq")
        announcement = Announcement.objects.create(
            title="Icon row",
            slug="icon-row",
            summary="Shown in the content desk.",
            content="Body.",
            status=PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        category = FAQCategory.objects.create(name="Families", slug="families")
        faq = FAQ.objects.create(category=category, question="Icon FAQ?", answer="Yes.")
        self.client.force_login(self.user)
        page = self.client.get(reverse("cms-dashboard")).content.decode()
        for url in (
            reverse("cms-announcement-edit", args=[announcement.pk]),
            reverse("cms-announcement-archive", args=[announcement.pk]),
            reverse("cms-announcement-delete", args=[announcement.pk]),
            reverse("cms-faq-edit", args=[faq.pk]),
            reverse("cms-faq-archive", args=[faq.pk]),
            reverse("cms-faq-delete", args=[faq.pk]),
        ):
            self.assertIn(url, page)
        # The controls are icons only, with the wording left to assistive text.
        for icon in ("bi bi-pencil", "bi bi-archive", "bi bi-trash"):
            self.assertIn(icon, page)
        self.assertNotIn(">Edit</a>", page)
        self.assertNotIn(">Archive</button>", page)

    def test_archive_and_delete_actions_refuse_get_and_need_permission(self):
        announcement = Announcement.objects.create(
            title="Guarded", slug="guarded", summary="s", content="c"
        )
        category = FAQCategory.objects.create(name="Families", slug="families")
        faq = FAQ.objects.create(category=category, question="Guarded?", answer="Yes.")
        actions = (
            ("cms-announcement-archive", announcement.pk),
            ("cms-announcement-delete", announcement.pk),
            ("cms-faq-archive", faq.pk),
            ("cms-faq-delete", faq.pk),
        )
        # Without the matching permission the action is refused outright.
        onlooker = User.objects.create_user(username="onlooker0001", password="Sensible-family-pass-849!")
        self.client.force_login(onlooker)
        for name, pk in actions:
            self.assertEqual(self.client.post(reverse(name, args=[pk])).status_code, 403)

        # With permission, a plain link visit still must not change anything:
        # every archive and delete action is POST only.
        self._grant("delete_announcement", "view_faq", "change_faq", "delete_faq")
        self.client.force_login(self.user)
        for name, pk in actions:
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404)
        self.assertTrue(Announcement.objects.filter(pk=announcement.pk).exists())
        self.assertTrue(FAQ.objects.filter(pk=faq.pk).exists())

    def test_archiving_keeps_the_record_and_deleting_removes_it(self):
        self._grant("delete_announcement", "view_faq", "change_faq", "delete_faq")
        self.client.force_login(self.user)
        category = FAQCategory.objects.create(name="Families", slug="families")
        faq = FAQ.objects.create(category=category, question="Archive me?", answer="Yes.")
        response = self.client.post(reverse("cms-faq-archive", args=[faq.pk]))
        self.assertRedirects(response, reverse("cms-dashboard"))
        faq.refresh_from_db()
        self.assertEqual(faq.status, PublicationStatus.ARCHIVED)
        self.assertTrue(AuditLog.objects.filter(action="faq.archived", object_id=str(faq.pk)).exists())

        announcement = Announcement.objects.create(
            title="Delete me", slug="delete-me", summary="s", content="c"
        )
        announcement_pk = announcement.pk
        response = self.client.post(reverse("cms-announcement-delete", args=[announcement_pk]))
        self.assertRedirects(response, reverse("cms-dashboard"))
        self.assertFalse(Announcement.objects.filter(pk=announcement_pk).exists())
        # The audit trail outlives the record it describes.
        self.assertTrue(
            AuditLog.objects.filter(action="announcement.deleted", object_id=str(announcement_pk)).exists()
        )

    def test_deleting_an_announcement_also_removes_its_uploaded_images(self):
        self._grant("delete_announcement")
        with TemporaryDirectory() as media_directory, override_settings(MEDIA_ROOT=media_directory):
            announcement = Announcement.objects.create(
                title="With photo", slug="with-photo", summary="s", content="c"
            )
            image = AnnouncementImage.objects.create(
                announcement=announcement,
                image=uploaded_test_image("doomed.jpg"),
                alt_text="Doomed photo",
            )
            stored = Path(media_directory) / image.image.name
            self.assertTrue(stored.exists())
            self.client.force_login(self.user)
            self.client.post(reverse("cms-announcement-delete", args=[announcement.pk]))
            self.assertFalse(AnnouncementImage.objects.filter(pk=image.pk).exists())
            self.assertFalse(stored.exists())

    def test_announcement_slug_is_built_from_the_title_and_never_asked_for(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse("cms-announcement-create"))
        # Staff never see or fill a slug field.
        self.assertNotContains(page, 'name="slug"')
        response = self.client.post(
            reverse("cms-announcement-create"),
            {
                "title": "Registration Opens In March",
                "summary": "Applications are open.",
                "content": "Families can now register.",
                "category": "registration",
                "action": "publish",
            },
        )
        self.assertRedirects(response, reverse("cms-dashboard"))
        announcement = Announcement.objects.get(title="Registration Opens In March")
        self.assertEqual(announcement.slug, "registration-opens-in-march")

        # A second announcement with the same title still gets its own address.
        twin = Announcement.objects.create(
            title="Registration Opens In March", summary="s", content="c"
        )
        self.assertEqual(twin.slug, "registration-opens-in-march-2")

        # Renaming must not move an address that is already published.
        announcement.title = "A Completely Different Title"
        announcement.save()
        announcement.refresh_from_db()
        self.assertEqual(announcement.slug, "registration-opens-in-march")

    def test_a_title_with_no_latin_letters_still_gets_a_usable_slug(self):
        # Slugifying Bengali yields an empty string, which would break the URL.
        first = Announcement.objects.create(title="গণিত অলিম্পিয়াড", summary="s", content="c")
        second = Announcement.objects.create(title="আরেকটি শিরোনাম", summary="s", content="c")
        self.assertEqual(first.slug, "announcement")
        self.assertEqual(second.slug, "announcement-2")
        self.assertEqual(first.get_absolute_url(), "/announcements/announcement/")

    def test_required_fields_are_starred_and_optional_ones_are_not(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse("cms-announcement-create")).content.decode()
        star = '<span class="required-mark" aria-hidden="true">*</span>'
        # Required: title, summary, content, category.
        self.assertIn("Title" + star, page)
        self.assertIn("Summary" + star, page)
        self.assertIn("Content" + star, page)
        # Optional: the cover image and search-engine fields carry no star.
        self.assertIn("Cover image url</label>", page)
        self.assertIn("Meta title</label>", page)
        self.assertNotIn("Cover image url" + star, page)
        self.assertNotIn("Meta title" + star, page)

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


class NewContentManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="contentmgr", password="test-pass-12345")
        permission_codenames = (
            "view_announcement",
            "manage_aboutpage",
            "add_questionpaper",
            "change_questionpaper",
            "publish_questionpaper",
            "view_questionpaper",
            "view_syllabus",
            "add_syllabus",
            "change_syllabus",
            "publish_syllabus",
        )
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label__in=("cms", "competitions"),
                codename__in=permission_codenames,
            )
        )

    def test_about_page_can_be_updated_from_the_content_desk(self):
        self.client.force_login(self.user)
        dashboard = self.client.get(reverse("cms-dashboard"))
        self.assertContains(dashboard, "Manage About page")
        edit_page = self.client.get(reverse("cms-about-edit"))
        self.assertContains(edit_page, 'name="images-0-image"')
        self.assertContains(edit_page, "data-add-image")

        response = self.client.post(
            reverse("cms-about-edit"),
            {
                "title": "Our Math Kangaroo story",
                "introduction": "A challenge for curious learners.",
                "content": "We make room for creative thinking.",
            },
        )
        self.assertRedirects(response, reverse("cms-dashboard"))
        self.assertContains(self.client.get(reverse("about")), "Our Math Kangaroo story")

    def test_about_page_image_can_be_uploaded_and_removed_in_the_content_desk(self):
        with TemporaryDirectory() as media_directory, override_settings(MEDIA_ROOT=media_directory):
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("cms-about-edit"),
                {
                    "title": "About Math Kangaroo Bangladesh",
                    "introduction": "A joyful mathematics challenge for curious students.",
                    "content": "What is Math Kangaroo?\n\nA competition for curious learners.",
                    "images-TOTAL_FORMS": "1",
                    "images-INITIAL_FORMS": "0",
                    "images-MIN_NUM_FORMS": "0",
                    "images-MAX_NUM_FORMS": "1000",
                    "images-0-image": uploaded_test_image("about.jpg"),
                    "images-0-alt_text": "Students exploring mathematics",
                    "images-0-display_order": "0",
                    "action": "save",
                },
            )

            self.assertRedirects(response, reverse("cms-dashboard"))
            about_image = AboutPageImage.objects.get(alt_text="Students exploring mathematics")
            page = self.client.get(reverse("about"))
            self.assertContains(page, about_image.image.url)
            self.assertContains(page, "Students exploring mathematics")

            response = self.client.post(
                reverse("cms-about-edit"),
                {
                    "title": "About Math Kangaroo Bangladesh",
                    "introduction": "A joyful mathematics challenge for curious students.",
                    "content": "What is Math Kangaroo?\n\nA competition for curious learners.",
                    "images-TOTAL_FORMS": "2",
                    "images-INITIAL_FORMS": "1",
                    "images-MIN_NUM_FORMS": "0",
                    "images-MAX_NUM_FORMS": "1000",
                    "images-0-id": str(about_image.pk),
                    "images-0-about_page": str(about_image.about_page_id),
                    "images-0-alt_text": about_image.alt_text,
                    "images-0-display_order": "0",
                    "images-0-DELETE": "on",
                    "images-1-alt_text": "",
                    "images-1-display_order": "0",
                },
            )

            self.assertRedirects(response, reverse("cms-dashboard"))
            self.assertFalse(AboutPageImage.objects.filter(pk=about_image.pk).exists())

    def test_about_page_rich_content_can_be_saved_and_rendered(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("cms-about-edit"),
            {
                "title": "Our story",
                "introduction": "For curious learners.",
                "content": (
                    '<h2>A <strong>joyful</strong> challenge</h2>'
                    '<p><span data-text-size="xlarge">Think boldly.</span> '
                    '<a href="javascript:alert(1)">Explore</a>'
                    '<script>alert("unsafe")</script></p>'
                ),
            },
        )

        self.assertRedirects(response, reverse("cms-dashboard"))
        page = self.client.get(reverse("about"))
        self.assertContains(page, "<h2>A <strong>joyful</strong> challenge</h2>")
        self.assertContains(page, '<span data-text-size="xlarge">Think boldly.</span>')
        self.assertContains(page, "<a>Explore</a>")
        self.assertNotContains(page, "javascript:")
        self.assertNotContains(page, "<script>")

    def test_question_pdf_can_be_uploaded_and_published_from_the_content_desk(self):
        with TemporaryDirectory() as media_directory, TemporaryDirectory() as private_directory, override_settings(
            MEDIA_ROOT=media_directory, PRIVATE_MEDIA_ROOT=private_directory
        ):
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("cms-question-paper-create"),
                {
                    "title": "2026 Ecolier challenge",
                    "description": "Released practice questions",
                    "year": "2026",
                    "category": "Ecolier",
                    "pdf_file": SimpleUploadedFile("ecolier-2026.pdf", b"%PDF-1.4\nquestions"),
                    "action": "publish",
                },
            )
            self.assertRedirects(response, reverse("cms-dashboard"))
            paper = QuestionPaper.objects.get(title="2026 Ecolier challenge")
            self.assertEqual(paper.status, PublicationStatus.PUBLISHED)
            self.assertContains(self.client.get(reverse("questions")), paper.title)
            self.assertTrue(
                AuditLog.objects.filter(action="question_paper.published", object_id=str(paper.pk)).exists()
            )

    def test_syllabus_and_topics_can_be_created_from_the_content_desk(self):
        season = CompetitionSeason.objects.create(name="2026 Olympiad", year=2026, slug="2026")
        level = CompetitionLevel.objects.create(
            name="CMS Test Ecolier",
            code="ecolier-test",
            min_grade=3,
            max_grade=4,
        )
        division = CompetitionDivision.objects.create(season=season, level=level, grade=3)
        CompetitionDivision.objects.create(season=season, level=level, grade=4)
        self.client.force_login(self.user)
        dashboard = self.client.get(reverse("cms-dashboard"))
        self.assertContains(dashboard, "Syllabus management")
        form_page = self.client.get(reverse("cms-syllabus-create"))
        self.assertContains(form_page, "2026 Olympiad")
        self.assertContains(form_page, "CMS Test Ecolier — Grades 3–4")
        self.assertContains(form_page, "data-syllabus-category-picker")
        self.assertContains(form_page, "data-category-option")
        self.assertRegex(form_page.content.decode(), r"<select[^>]*\shidden(?:\s|>)")
        self.assertContains(form_page, "class=\"syllabus-category-trigger\"")
        self.assertNotContains(form_page, "Grade 3</option>")
        self.assertNotContains(form_page, "Grade 4</option>")

        response = self.client.post(
            reverse("cms-syllabus-create"),
            {
                "division": division.pk,
                "title": "Grade 3 mathematics",
                "description": "Ideas for grade three.",
                "topics-TOTAL_FORMS": "1",
                "topics-INITIAL_FORMS": "0",
                "topics-MIN_NUM_FORMS": "0",
                "topics-MAX_NUM_FORMS": "1000",
                "topics-0-id": "",
                "topics-0-topic": "Patterns",
                "topics-0-description": "Explore repeating patterns.",
                "topics-0-display_order": "1",
                "action": "publish",
            },
        )
        self.assertRedirects(response, reverse("cms-dashboard"))
        syllabus = Syllabus.objects.get(division=division)
        self.assertEqual(syllabus.status, Syllabus.Status.PUBLISHED)
        self.assertEqual(syllabus.topics.get().topic, "Patterns")
        for category_level in CompetitionLevel.objects.all():
            category_divisions = CompetitionDivision.objects.filter(
                level=category_level,
                grade=category_level.min_grade,
            ).select_related("season")
            for category_division in category_divisions:
                if not Syllabus.objects.filter(
                    division__season=category_division.season,
                    division__level=category_level,
                ).exists():
                    Syllabus.objects.create(
                        division=category_division,
                        title=f"{category_level.name} existing syllabus",
                    )
        empty_form_page = self.client.get(reverse("cms-syllabus-create"))
        self.assertContains(empty_form_page, "CMS Test Ecolier — Grades 3–4")
        self.assertContains(empty_form_page, "Already added")
        self.assertContains(
            empty_form_page,
            reverse("cms-syllabus-edit", args=[syllabus.pk]),
        )
        self.assertNotContains(empty_form_page, "data-category-option")
        self.assertContains(
            self.client.get(reverse("cms-syllabus-edit", args=[syllabus.pk])),
            "CMS Test Ecolier — Grades 3–4",
        )
        public_page = self.client.get(reverse("syllabus"))
        self.assertContains(public_page, "Grade 3 mathematics")
        self.assertContains(public_page, "Topics to explore")
        self.assertContains(public_page, "Patterns")
        self.assertContains(public_page, "Explore repeating patterns.")

    def test_syllabus_and_question_paper_rows_can_be_archived_and_deleted(self):
        # The uploaded PDF is kept in a throwaway root so the real one is untouched.
        private_directory = TemporaryDirectory()
        self.addCleanup(private_directory.cleanup)
        storage_settings = override_settings(PRIVATE_MEDIA_ROOT=private_directory.name)
        storage_settings.enable()
        self.addCleanup(storage_settings.disable)
        season = CompetitionSeason.objects.create(name="2026 Olympiad", year=2026, slug="2026")
        level = CompetitionLevel.objects.create(
            name="CMS Test Benjamin", code="benjamin-test", min_grade=5, max_grade=6
        )
        division = CompetitionDivision.objects.create(season=season, level=level, grade=5)
        syllabus = Syllabus.objects.create(division=division, title="Grade 5 mathematics")
        SyllabusTopic.objects.create(syllabus=syllabus, topic="Fractions")
        paper = QuestionPaper.objects.create(
            title="2026 Benjamin Questions",
            year=2026,
            category="Benjamin",
            pdf_file=SimpleUploadedFile("benjamin-2026.pdf", b"%PDF-1.4\nbenjamin"),
        )
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label__in=("cms", "competitions"),
                codename__in=("delete_syllabus", "delete_questionpaper"),
            )
        )
        self.client.force_login(User.objects.get(pk=self.user.pk))

        page = self.client.get(reverse("cms-dashboard")).content.decode()
        for url in (
            reverse("cms-syllabus-archive", args=[syllabus.pk]),
            reverse("cms-syllabus-delete", args=[syllabus.pk]),
            reverse("cms-question-paper-archive", args=[paper.pk]),
            reverse("cms-question-paper-delete", args=[paper.pk]),
        ):
            self.assertIn(url, page)

        self.assertRedirects(
            self.client.post(reverse("cms-syllabus-archive", args=[syllabus.pk])),
            reverse("cms-dashboard"),
        )
        syllabus.refresh_from_db()
        self.assertEqual(syllabus.status, Syllabus.Status.ARCHIVED)

        topic_count = SyllabusTopic.objects.filter(syllabus=syllabus).count()
        self.assertEqual(topic_count, 1)
        self.client.post(reverse("cms-syllabus-delete", args=[syllabus.pk]))
        self.assertFalse(Syllabus.objects.filter(pk=syllabus.pk).exists())
        self.assertEqual(SyllabusTopic.objects.filter(syllabus_id=syllabus.pk).count(), 0)
        # Deleting a syllabus must not take its competition division with it.
        self.assertTrue(CompetitionDivision.objects.filter(pk=division.pk).exists())

        stored = Path(paper.pdf_file.path)
        self.assertTrue(stored.exists())
        self.client.post(reverse("cms-question-paper-delete", args=[paper.pk]))
        self.assertFalse(QuestionPaper.objects.filter(pk=paper.pk).exists())
        self.assertFalse(stored.exists())

    def test_content_editor_group_includes_the_new_frontend_management_permissions(self):
        editor = Group.objects.get(name="Content Editor")
        editor_permissions = set(editor.permissions.values_list("codename", flat=True))
        self.assertIn("manage_aboutpage", editor_permissions)
        self.assertIn("add_questionpaper", editor_permissions)
        self.assertIn("add_syllabus", editor_permissions)


class QuestionPaperPrivateStorageTests(TestCase):
    """Question PDFs must only be reachable through the publication-checked download view."""

    def setUp(self):
        media_directory = TemporaryDirectory()
        private_directory = TemporaryDirectory()
        storage_settings = override_settings(
            MEDIA_ROOT=media_directory.name,
            PRIVATE_MEDIA_ROOT=private_directory.name,
        )
        storage_settings.enable()
        self.addCleanup(media_directory.cleanup)
        self.addCleanup(private_directory.cleanup)
        self.addCleanup(storage_settings.disable)
        self.media_root = Path(media_directory.name)
        self.private_root = Path(private_directory.name)

    def create_paper(self, status=PublicationStatus.PUBLISHED):
        return QuestionPaper.objects.create(
            title="2026 Cadet Questions",
            year=2026,
            category="Cadet",
            pdf_file=SimpleUploadedFile("cadet-2026.pdf", b"%PDF-1.4\ncadet"),
            status=status,
        )

    def test_pdf_is_stored_outside_the_public_media_root(self):
        paper = self.create_paper()
        stored = Path(paper.pdf_file.path)
        self.assertTrue(stored.is_file())
        self.assertIn(self.private_root.resolve(), stored.resolve().parents)
        self.assertFalse(any(self.media_root.rglob("*.pdf")))
        with self.assertRaises(ValueError):
            paper.pdf_file.url

    def test_pdf_is_not_served_from_the_media_url(self):
        draft = self.create_paper(status=PublicationStatus.DRAFT)
        self.assertEqual(self.client.get(f"/media/{draft.pdf_file.name}").status_code, 404)
        self.assertEqual(
            self.client.get(reverse("question-paper-download", args=[draft.pk])).status_code,
            404,
        )

    def test_media_url_refuses_question_papers_left_in_the_public_media_root(self):
        legacy = self.media_root / "question-papers" / "legacy.pdf"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"%PDF-1.4\nlegacy")
        public_image = self.media_root / "hero-slides" / "hero.jpg"
        public_image.parent.mkdir(parents=True)
        public_image.write_bytes(b"jpeg")

        self.assertEqual(self.client.get("/media/question-papers/legacy.pdf").status_code, 404)
        self.assertEqual(self.client.get("/media//question-papers/legacy.pdf").status_code, 404)
        self.assertEqual(self.client.get("/media/./question-papers/legacy.pdf").status_code, 404)
        self.assertEqual(
            self.client.get("/media/hero-slides/../question-papers/legacy.pdf").status_code,
            404,
        )
        self.assertEqual(self.client.get("/media/hero-slides/hero.jpg").status_code, 200)

    def test_media_url_refuses_hidden_files(self):
        (self.media_root / "hero-slides").mkdir(parents=True)
        (self.media_root / ".htaccess").write_text("Options -Indexes")
        (self.media_root / "hero-slides" / ".secret").write_text("hidden")
        self.assertEqual(self.client.get("/media/.htaccess").status_code, 404)
        self.assertEqual(self.client.get("/media/hero-slides/.secret").status_code, 404)

    def test_uploaded_names_keep_a_single_extension(self):
        # FileField.generate_filename is the path every form upload takes.
        for model, expected in (
            (HeroSlide, "hero-slides/shell_php.jpg"),
            (AnnouncementImage, "announcements/shell_php.jpg"),
            (AboutPageImage, "about-page/shell_php.jpg"),
        ):
            field = model._meta.get_field("image")
            self.assertEqual(field.generate_filename(None, "shell.php.jpg"), expected)
        paper = QuestionPaper.objects.create(
            title="Double extension",
            year=2026,
            category="Cadet",
            pdf_file=SimpleUploadedFile("paper.php.pdf", b"%PDF-1.4\nx"),
        )
        self.assertEqual(paper.pdf_file.name, "question-papers/paper_php.pdf")

    def test_content_desk_edit_page_renders_for_a_private_pdf(self):
        paper = self.create_paper()
        editor = User.objects.create_user(username="pdfeditor", password="test-pass-12345")
        editor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="cms",
                codename__in=("view_questionpaper", "change_questionpaper"),
            )
        )
        self.client.force_login(editor)
        response = self.client.get(reverse("cms-question-paper-edit", args=[paper.pk]))
        self.assertContains(response, paper.pdf_file.name)
        self.assertNotContains(response, "/media/question-papers/")


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
