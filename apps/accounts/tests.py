from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.cms.views import home
from apps.competitions.models import CompetitionRegistration, CompetitionSeason
from .models import StudentProfile

User = get_user_model()
STRONG_PASSWORD = "Sensible-student-pass-849!"


class AccountFlowTests(TestCase):
    def test_all_message_levels_render_with_their_toast_types(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.session = self.client.session
        request.resolver_match = resolve("/")
        request._messages = FallbackStorage(request)
        messages.success(request, "Saved successfully.")
        messages.error(request, "Something went wrong.")
        messages.warning(request, "Please review this.")
        messages.info(request, "Here is an update.")

        response = home(request)

        self.assertContains(response, "toast-success")
        self.assertContains(response, "toast-error")
        self.assertContains(response, "toast-warning")
        self.assertContains(response, "toast-info")
        self.assertContains(response, 'role="alert"')
        self.assertEqual(response.content.count(b'data-toast'), 4)

    def test_signup_creates_student_profile_annual_registration_and_participant_login(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Amina",
                "last_name": "Rahman",
                "email": "amina@example.org",
                "date_of_birth": "2015-03-10",
                "phone": "",
                "guardian_name": "Nadia Rahman",
                "guardian_phone": "01700000000",
                "district": "Dhaka",
                "school_name": "Dhaka Model School",
                "grade": "5",
                "password1": STRONG_PASSWORD,
                "password2": STRONG_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))
        user = User.objects.get(email="amina@example.org")
        self.assertEqual(user.username, "2700001")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertEqual(user.student_profile.date_of_birth.isoformat(), "2015-03-10")
        registration = CompetitionRegistration.objects.get(student=user)
        self.assertEqual(registration.registration_number, "2700001")
        self.assertEqual(registration.season.year, 2027)
        self.assertEqual(registration.school_name, "Dhaka Model School")
        self.assertEqual(registration.grade, 5)
        self.assertIn("_auth_user_id", self.client.session)

    def test_participant_id_is_the_case_insensitive_login_identifier(self):
        user = User.objects.create_user(username="2700001", email="student@example.org", password=STRONG_PASSWORD)
        self.assertEqual(User.objects.get_by_natural_key("2700001"), user)
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "2700001", "password": STRONG_PASSWORD},
            follow=True,
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertContains(response, "toast-success")
        self.assertContains(response, "You are now logged in.")

        response = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertRedirects(response, reverse("home"))
        self.assertContains(response, "toast-success")
        self.assertContains(response, "You have been logged out.")

    def test_invalid_login_shows_error_toast(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "2700001", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "toast-error")
        self.assertContains(response, "The participant username or password was not recognized.")

    def test_a_student_can_register_with_an_email_shared_by_a_sibling(self):
        User.objects.create_user(username="2600001", email="family@example.org", password=STRONG_PASSWORD)
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Another",
                "last_name": "Student",
                "email": "FAMILY@EXAMPLE.ORG",
                "date_of_birth": "2016-03-10",
                "guardian_name": "Nadia Rahman",
                "guardian_phone": "01700000000",
                "school_name": "Dhaka Model School",
                "grade": "4",
                "password1": STRONG_PASSWORD,
                "password2": STRONG_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(User.objects.filter(email__iexact="family@example.org").count(), 2)

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}",
        )

    def test_navigation_shows_only_authenticated_actions(self):
        self.client.force_login(
            User.objects.create_user(username="2700001", email="student@example.org", password=STRONG_PASSWORD)
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Log out")
        self.assertNotContains(response, "Join the fun")

    def test_custom_user_admin_add_form_supports_participant_username(self):
        superuser = User.objects.create_superuser(
            username="admin0001",
            email="admin@example.org",
            password=STRONG_PASSWORD,
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("admin:accounts_user_add"))
        self.assertEqual(response.status_code, 200)

    def test_existing_student_without_current_registration_sees_reminder_and_prefilled_renewal(self):
        user = User.objects.create_user(username="2600001", email="student@example.org", password=STRONG_PASSWORD)
        profile = StudentProfile.objects.create(
            user=user,
            date_of_birth="2013-04-20",
            guardian_name="Parent Name",
            guardian_phone="01711111111",
        )
        season = CompetitionSeason.objects.get(is_current=True)
        old_season = CompetitionSeason.objects.create(name="2026 season", year=2026, slug="2026-test")
        old_division = old_season.divisions.create(
            level=season.divisions.first().level,
            grade=6,
        )
        CompetitionRegistration.objects.create(
            registration_number="2600001",
            student=user,
            season=old_season,
            division=old_division,
            school_name="Old school",
            grade=6,
        )

        self.client.force_login(user)
        dashboard_response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(dashboard_response, "Complete your 2027 registration")
        self.assertContains(dashboard_response, user.username)
        renewal_response = self.client.get(reverse("accounts:annual-registration"))
        self.assertContains(renewal_response, profile.guardian_name)
        self.assertContains(renewal_response, user.email)
        self.assertNotContains(renewal_response, 'value="Old school"')
        self.assertNotContains(renewal_response, '<option value="6" selected')

    def test_existing_student_can_register_for_new_year_without_changing_login_id(self):
        user = User.objects.create_user(username="2600001", email="student@example.org", password=STRONG_PASSWORD)
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:annual-registration"),
            {"school_name": "New School", "grade": "7"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        registration = CompetitionRegistration.objects.get(student=user)
        self.assertEqual(registration.registration_number, "2700001")
        user.refresh_from_db()
        self.assertEqual(user.username, "2600001")
        self.assertEqual(registration.grade, 7)
        self.assertEqual(registration.school_name, "New School")

    def test_profile_is_read_only_outside_admin_configured_edit_window(self):
        user = User.objects.create_user(username="2700001", email="student@example.org", password=STRONG_PASSWORD)
        StudentProfile.objects.create(user=user)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("accounts:profile")), "Profile editing is closed")
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Changed",
                "last_name": "Name",
                "email": "student@example.org",
                "date_of_birth": "2014-01-01",
                "guardian_name": "Guardian",
                "guardian_phone": "01700000000",
            },
        )
        self.assertEqual(response.status_code, 403)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "")

    def test_profile_can_be_edited_inside_the_admin_configured_window(self):
        user = User.objects.create_user(username="2700001", email="student@example.org", password=STRONG_PASSWORD)
        StudentProfile.objects.create(user=user)
        season = CompetitionSeason.objects.get(is_current=True)
        season.profile_edit_open_at = timezone.now() - timezone.timedelta(days=1)
        season.profile_edit_close_at = timezone.now() + timezone.timedelta(days=1)
        season.save(update_fields=["profile_edit_open_at", "profile_edit_close_at"])
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Amina",
                "last_name": "Rahman",
                "email": "student@example.org",
                "date_of_birth": "2014-01-01",
                "guardian_name": "Parent Name",
                "guardian_phone": "01722222222",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Amina")
        self.assertEqual(user.student_profile.guardian_phone, "01722222222")

    def test_registration_is_rejected_after_admin_closes_season(self):
        season = CompetitionSeason.objects.get(is_current=True)
        season.status = CompetitionSeason.Status.REGISTRATION_CLOSED
        season.save(update_fields=["status"])
        response = self.client.post(
            reverse("accounts:signup"),
            {"first_name": "Amina", "password1": STRONG_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="manager0001",
            email="manager@example.org",
            password=STRONG_PASSWORD,
        )
        self.season = CompetitionSeason.objects.get(is_current=True)
        self.division = self.season.divisions.first()

    def test_staff_landing_dashboard_uses_live_data_and_permission_gated_panels(self):
        student = User.objects.create_user(
            username="2707654",
            email="dashboard@example.org",
            first_name="Dashboard",
            last_name="Student",
            password=STRONG_PASSWORD,
        )
        CompetitionRegistration.objects.create(
            registration_number="2776540",
            student=student,
            season=self.season,
            division=self.division,
            school_name="Kangaroo Academy",
            grade=self.division.grade,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registration overview")
        self.assertContains(response, "Level breakdown")
        self.assertContains(response, "Manage users")
        self.assertEqual(response.context["current_season_participants"], 1)
        self.assertEqual(len(response.context["monthly_values"]), 12)
        self.assertEqual(
            sum(month["registrations"] for month in response.context["monthly_values"]),
            1,
        )

    def test_registration_statistics_use_live_data_and_staff_shell(self):
        student = User.objects.create_user(
            username="2707655",
            email="stats@example.org",
            first_name="Stats",
            last_name="Student",
            password=STRONG_PASSWORD,
        )
        StudentProfile.objects.create(user=student, district="Dhaka")
        CompetitionRegistration.objects.create(
            registration_number="2776550",
            student=student,
            season=self.season,
            division=self.division,
            school_name="Kangaroo Academy",
            grade=self.division.grade,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("accounts:staff-stats"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "staff_base.html")
        self.assertContains(response, "Daily registrations")
        self.assertContains(response, "Gender and upazila figures are not shown")
        self.assertEqual(response.context["total_registrations"], 1)
        self.assertEqual(response.context["total_students"], 1)
        self.assertEqual(response.context["total_institutes"], 1)
        self.assertEqual(response.context["season_total"], 1)
        self.assertEqual(response.context["new_students"], 1)
        self.assertEqual(response.context["district_rows"][0]["label"], "Dhaka")

    def test_registration_statistics_require_staff_registration_permission(self):
        staff = User.objects.create_user(
            username="statswithoutpermission",
            password=STRONG_PASSWORD,
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("accounts:staff-stats"))

        self.assertEqual(response.status_code, 403)

    def test_invalid_staff_user_update_shows_warning_toast(self):
        student = User.objects.create_user(
            username="2707656",
            email="invalid-update@example.org",
            password=STRONG_PASSWORD,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("accounts:staff-user-edit", args=[student.pk]),
            {},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "toast-warning")
        self.assertContains(response, "Please review the highlighted fields")

    def test_unprivileged_staff_sees_no_user_or_registration_statistics(self):
        staff = User.objects.create_user(
            username="staffwithouttools",
            password=STRONG_PASSWORD,
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No staff tools are assigned")
        self.assertNotContains(response, "Student accounts")
        self.assertNotContains(response, "Competition registrations")

    def test_staff_user_dashboard_searches_all_requested_fields_and_shows_stats(self):
        student = User.objects.create_user(
            username="2709876",
            email="mina@example.org",
            first_name="Mina",
            last_name="Chowdhury",
            password=STRONG_PASSWORD,
        )
        StudentProfile.objects.create(user=student, phone="01855550123")
        CompetitionRegistration.objects.create(
            registration_number="2798765",
            student=student,
            season=self.season,
            division=self.division,
            school_name="Bright Future Academy",
            grade=self.division.grade,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("accounts:staff-users"))
        self.assertContains(response, "All accounts")
        self.assertContains(response, "Competition registrations")
        self.assertContains(response, "Bright Future Academy")
        self.assertEqual(response.context["student_users"], 1)

        for search in (
            "Mina Chowdhury",
            "2709876",
            "mina@example.org",
            "01855550123",
            "Bright Future Academy",
        ):
            with self.subTest(search=search):
                response = self.client.get(reverse("accounts:staff-users"), {"q": search})
                self.assertContains(response, "Mina Chowdhury")

    def test_staff_with_user_permission_can_update_account_and_student_phone(self):
        staff = User.objects.create_user(
            username="accountstaff",
            email="staff@example.org",
            password=STRONG_PASSWORD,
            is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type=ContentType.objects.get(app_label="accounts", model="user"),
            codename__in=("view_user", "change_user"),
        )
        staff.user_permissions.add(*permissions)
        student = User.objects.create_user(
            username="2701234",
            email="student@example.org",
            first_name="Old",
            last_name="Name",
            password=STRONG_PASSWORD,
        )
        profile = StudentProfile.objects.create(user=student, phone="01711111111")
        self.client.force_login(staff)

        response = self.client.post(
            reverse("accounts:staff-user-edit", args=[student.pk]),
            {
                "first_name": "New",
                "last_name": "Name",
                "email": "NEW@example.org",
                "role": User.Role.STUDENT,
                "phone": "01999990000",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("accounts:staff-users"))
        student.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(student.first_name, "New")
        self.assertEqual(student.email, "new@example.org")
        self.assertEqual(profile.phone, "01999990000")
        self.assertTrue(
            AuditLog.objects.filter(actor=staff, action="user.updated", object_id=str(student.pk)).exists()
        )

    def test_non_staff_and_unprivileged_staff_cannot_view_user_dashboard(self):
        for username, is_staff in (("regularuser", False), ("unprivileged", True)):
            with self.subTest(username=username):
                user = User.objects.create_user(
                    username=username,
                    password=STRONG_PASSWORD,
                    is_staff=is_staff,
                )
                self.client.force_login(user)
                response = self.client.get(reverse("accounts:staff-users"))
                self.assertEqual(response.status_code, 403)

    def test_deactivation_preserves_registration_and_self_deactivation_is_blocked(self):
        student = User.objects.create_user(
            username="2702468",
            email="participant@example.org",
            password=STRONG_PASSWORD,
        )
        registration = CompetitionRegistration.objects.create(
            registration_number="2724680",
            student=student,
            season=self.season,
            division=self.division,
            school_name="History Academy",
            grade=self.division.grade,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("accounts:staff-user-deactivate", args=[student.pk]),
            follow=True,
        )

        self.assertEqual(response.redirect_chain[-1][0], reverse("accounts:staff-users"))
        student.refresh_from_db()
        self.assertFalse(student.is_active)
        self.assertTrue(CompetitionRegistration.objects.filter(pk=registration.pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(actor=self.admin, action="user.deactivated", object_id=str(student.pk)).exists()
        )
        self.assertContains(response, "toast-success")

        response = self.client.post(
            reverse("accounts:staff-user-deactivate", args=[self.admin.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
