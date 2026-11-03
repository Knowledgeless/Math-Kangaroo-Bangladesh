from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Value
from django.db.models.functions import Concat, TruncDate, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.audit.models import AuditLog, record_event
from apps.competitions.models import CompetitionLevel, CompetitionRegistration, CompetitionSeason
from apps.competitions.services import register_student

from .forms import (
    AnnualRegistrationForm,
    ParticipantLoginForm,
    StaffUserForm,
    StudentProfileForm,
    StudentSignupForm,
)
from .models import StudentProfile, User


def _current_season():
    return CompetitionSeason.objects.filter(is_current=True).first()


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    season = _current_season()
    can_register = bool(season and season.is_registration_open())
    form = StudentSignupForm(request.POST or None)
    if request.method == "POST":
        if not can_register:
            messages.error(request, "Registration is not open right now. Please check back for the next update.")
        elif form.is_valid():
            try:
                with transaction.atomic():
                    user = User(
                        username=None,
                        first_name=form.cleaned_data["first_name"],
                        last_name=form.cleaned_data["last_name"],
                        email=form.cleaned_data["email"].strip().lower(),
                        role=User.Role.STUDENT,
                    )
                    user.set_password(form.cleaned_data["password1"])
                    registration = register_student(
                        student=user,
                        season_id=season.pk,
                        school_name=form.cleaned_data["school_name"],
                        grade=form.cleaned_data["grade"],
                        request=request,
                    )
                    StudentProfile.objects.filter(user=user).update(
                        date_of_birth=form.cleaned_data["date_of_birth"],
                        phone=form.cleaned_data["phone"],
                        guardian_name=form.cleaned_data["guardian_name"],
                        guardian_phone=form.cleaned_data["guardian_phone"],
                        district=form.cleaned_data["district"],
                    )
            except ValidationError as error:
                form.add_error(None, error)
                messages.warning(request, "Please review the highlighted fields and try again.")
            else:
                login(request, user)
                messages.success(
                    request,
                    f"You're registered for {season.year}. Your participant username is {registration.registration_number}.",
                )
                return redirect("accounts:dashboard")
        elif can_register:
            messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "accounts/signup.html",
        {"form": form, "season": season, "can_register": can_register},
    )


def participant_login(request):
    form = ParticipantLoginForm(request.POST or None, request=request)
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "You are now logged in.")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("accounts:dashboard")
    if request.method == "POST":
        messages.error(request, "The participant username or password was not recognized.")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


def participant_logout(request):
    if request.method != "POST":
        raise PermissionDenied
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")


@login_required
def dashboard(request):
    can_manage_users = request.user.is_staff and request.user.has_perm("accounts.view_user")
    if request.user.is_staff:
        return render(request, "accounts/staff_dashboard.html", _staff_dashboard_context(request))
    registrations = request.user.competition_registrations.select_related(
        "season", "division__level"
    )
    current_season = _current_season()
    current_registration = (
        registrations.filter(season=current_season).first() if current_season else None
    )
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        "accounts/dashboard.html",
        {
            "profile": profile,
            "registrations": registrations,
            "current_season": current_season,
            "current_registration": current_registration,
            "needs_current_registration": bool(
                current_season
                and current_season.is_registration_open()
                and current_registration is None
                and request.user.role == User.Role.STUDENT
            ),
            "can_manage_content": any(
                request.user.has_perm(permission)
                for permission in (
                    "cms.view_announcement",
                    "cms.add_announcement",
                    "cms.change_announcement",
                    "cms.view_faq",
                    "cms.add_faq",
                    "cms.view_heroslide",
                )
            ),
            "can_manage_users": can_manage_users,
        },
    )


def _staff_dashboard_context(request):
    user = request.user
    can_manage_users = user.has_perm("accounts.view_user")
    can_view_registrations = user.has_perm("competitions.view_competitionregistration")
    current_season = _current_season()
    now = timezone.now()
    stats = []

    if can_manage_users:
        stats.extend(
            [
                {
                    "label": "Student accounts",
                    "value": User.objects.filter(
                        role=User.Role.STUDENT,
                        is_active=True,
                        is_staff=False,
                        is_superuser=False,
                    ).count(),
                    "detail": "Active participant accounts",
                    "tone": "lime",
                    "icon": "people-fill",
                },
                {
                    "label": "New accounts",
                    "value": User.objects.filter(date_joined__gte=now - timedelta(days=30)).count(),
                    "detail": "Joined in the last 30 days",
                    "tone": "yellow",
                    "icon": "person-plus-fill",
                },
            ]
        )
    if can_view_registrations:
        registrations = CompetitionRegistration.objects.all()
        stats.append(
            {
                "label": "Competition registrations",
                "value": registrations.count(),
                "detail": "All seasons",
                "tone": "coral",
                "icon": "journal-check",
            }
        )
        if current_season:
            stats.append(
                {
                    "label": f"{current_season.year} participants",
                    "value": registrations.filter(season=current_season).count(),
                    "detail": current_season.get_status_display(),
                    "tone": "lilac",
                    "icon": "person-check-fill",
                }
            )

    monthly_registration_counts = {}
    if can_view_registrations:
        monthly_registration_counts = {
            entry["month"].strftime("%Y-%m"): entry["total"]
            for entry in CompetitionRegistration.objects.filter(
                created_at__gte=now - timedelta(days=365)
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Count("pk"))
        }

    monthly_account_counts = {}
    if can_manage_users:
        monthly_account_counts = {
            entry["month"].strftime("%Y-%m"): entry["total"]
            for entry in User.objects.filter(date_joined__gte=now - timedelta(days=365))
            .annotate(month=TruncMonth("date_joined"))
            .values("month")
            .annotate(total=Count("pk"))
        }

    month_cursor = timezone.localdate().replace(day=1)
    months = []
    for _ in range(12):
        months.append(month_cursor)
        month_cursor = (month_cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    monthly_values = [
        {
            "label": month.strftime("%b"),
            "registrations": monthly_registration_counts.get(month.strftime("%Y-%m"), 0),
            "accounts": monthly_account_counts.get(month.strftime("%Y-%m"), 0),
        }
        for month in months
    ]
    max_monthly_value = max(
        (max(month["registrations"], month["accounts"]) for month in monthly_values),
        default=0,
    )
    for month in monthly_values:
        month["registration_height"] = max(
            4, round(month["registrations"] / max_monthly_value * 100)
        ) if max_monthly_value else 4
        month["account_height"] = max(
            4, round(month["accounts"] / max_monthly_value * 100)
        ) if max_monthly_value else 4

    level_rows = []
    if can_view_registrations:
        level_counts = dict(
            CompetitionRegistration.objects.filter(season=current_season)
            .values("division__level_id")
            .annotate(total=Count("pk"))
            .values_list("division__level_id", "total")
        ) if current_season else {}
        max_level_count = max(level_counts.values(), default=0)
        level_rows = [
            {
                "name": level.name,
                "count": level_counts.get(level.pk, 0),
                "percentage": round(level_counts.get(level.pk, 0) / max_level_count * 100)
                if max_level_count
                else 0,
            }
            for level in CompetitionLevel.objects.all()
        ]

    can_view_activity = user.has_perm("audit.view_auditlog")
    recent_activity = (
        AuditLog.objects.select_related("actor").all()[:6] if can_view_activity else []
    )
    current_season_participants = (
        CompetitionRegistration.objects.filter(season=current_season).count()
        if current_season and can_view_registrations
        else None
    )
    can_manage_content = any(
        user.has_perm(permission)
        for permission in (
            "cms.view_announcement",
            "cms.add_announcement",
            "cms.change_announcement",
            "cms.view_faq",
            "cms.view_heroslide",
        )
    )
    return {
        "current_season": current_season,
        "current_season_participants": current_season_participants,
        "season_is_open": current_season.is_registration_open(now) if current_season else False,
        "stats": stats,
        "monthly_values": monthly_values,
        "level_rows": level_rows,
        "recent_activity": recent_activity,
        "can_manage_users": can_manage_users,
        "can_view_registrations": can_view_registrations,
        "can_view_activity": can_view_activity,
        "can_manage_content": can_manage_content,
    }


@login_required
def staff_registration_stats(request):
    if not request.user.is_staff or not request.user.has_perm(
        "competitions.view_competitionregistration"
    ):
        raise PermissionDenied

    current_season = _current_season()
    registrations = CompetitionRegistration.objects.select_related(
        "student", "division__level", "season"
    )
    current_registrations = (
        registrations.filter(season=current_season) if current_season else registrations.none()
    )
    total_registrations = registrations.count()
    total_students = registrations.values("student_id").distinct().count()
    total_institutes = (
        registrations.exclude(school_name="")
        .values("school_name")
        .distinct()
        .count()
    )

    prior_student_ids = (
        CompetitionRegistration.objects.filter(
            season__year__lt=current_season.year
        ).values_list("student_id", flat=True)
        if current_season
        else []
    )
    returning_student_ids = current_registrations.filter(
        student_id__in=prior_student_ids
    ).values_list("student_id", flat=True).distinct()
    returning_students = current_registrations.filter(
        student_id__in=returning_student_ids
    ).values("student_id").distinct().count()
    new_students = current_registrations.exclude(
        student_id__in=returning_student_ids
    ).values("student_id").distinct().count()
    season_total = returning_students + new_students

    palette = ("#567b45", "#d5b54e", "#8d7bb5", "#db8064", "#70a9a0", "#aa8a6c")

    def breakdown(queryset, label_key):
        counts = list(
            queryset.values(label_key)
            .annotate(total=Count("pk"))
            .order_by("-total", label_key)
        )
        max_count = max((item["total"] for item in counts), default=0)
        total = sum(item["total"] for item in counts)
        start = 0
        for index, item in enumerate(counts):
            item["label"] = item[label_key] or "Not provided"
            item["percentage"] = round(item["total"] * 100 / total) if total else 0
            item["bar_width"] = round(item["total"] * 100 / max_count) if max_count else 0
            item["color"] = palette[index % len(palette)]
            item["start"] = start
            start += item["total"] * 360 / total if total else 0
            item["end"] = start
        return counts, (
            ", ".join(
                f"{entry['color']} {entry['start']:.2f}deg {entry['end']:.2f}deg"
                for entry in counts
            )
            or "#e8eadf 0deg 360deg"
        )

    category_rows, category_donut = breakdown(
        current_registrations, "division__level__name"
    )
    grade_rows, _ = breakdown(current_registrations, "grade")
    institute_rows, _ = breakdown(
        current_registrations.exclude(school_name=""), "school_name"
    )
    district_rows, district_donut = breakdown(
        current_registrations.exclude(student__student_profile__district=""),
        "student__student_profile__district",
    )
    institute_rows = institute_rows[:15]
    district_rows = district_rows[:15]

    today = timezone.localdate()
    trend_start = today - timedelta(days=29)
    trend_counts = {
        row["day"]: row["total"]
        for row in current_registrations.filter(
            created_at__date__gte=trend_start,
            created_at__date__lte=today,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("pk"))
    }
    trend_rows = [
        {
            "date": trend_start + timedelta(days=day_index),
            "total": trend_counts.get(trend_start + timedelta(days=day_index), 0),
        }
        for day_index in range(30)
    ]
    max_daily = max((item["total"] for item in trend_rows), default=0)
    for item in trend_rows:
        item["height"] = max(3, round(item["total"] * 100 / max_daily)) if max_daily else 3

    return render(
        request,
        "accounts/staff_stats.html",
        {
            "current_season": current_season,
            "season_is_open": current_season.is_registration_open() if current_season else False,
            "total_registrations": total_registrations,
            "total_students": total_students,
            "total_institutes": total_institutes,
            "season_total": season_total,
            "new_students": new_students,
            "returning_students": returning_students,
            "new_percentage": round(new_students * 100 / season_total) if season_total else 0,
            "returning_percentage": round(returning_students * 100 / season_total) if season_total else 0,
            "category_rows": category_rows,
            "category_donut": category_donut,
            "returning_donut": (
                f"#d5b54e 0deg {returning_students * 360 / season_total:.2f}deg, "
                f"#567b45 {returning_students * 360 / season_total:.2f}deg 360deg"
                if season_total
                else "#e8eadf 0deg 360deg"
            ),
            "grade_rows": grade_rows,
            "institute_rows": institute_rows,
            "district_rows": district_rows,
            "district_donut": district_donut,
            "trend_rows": trend_rows,
            "max_daily": max_daily,
            "staff_page_label": "Registration stats",
        },
    )


@login_required
def staff_users(request):
    if not request.user.is_staff or not request.user.has_perm("accounts.view_user"):
        raise PermissionDenied

    search = request.GET.get("q", "").strip()[:100]
    users = User.objects.select_related("student_profile").prefetch_related(
        "competition_registrations__season",
        "competition_registrations__division__level",
    )
    if search:
        users = users.annotate(
            full_name=Concat("first_name", Value(" "), "last_name"),
        ).filter(
            Q(full_name__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(student_profile__phone__icontains=search)
            | Q(student_profile__guardian_phone__icontains=search)
            | Q(competition_registrations__school_name__icontains=search)
        )
    users = users.annotate(
        registration_count=Count("competition_registrations", distinct=True),
    ).order_by("-date_joined", "username").distinct()

    current_season = _current_season()
    now = timezone.now()
    page_obj = Paginator(users, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/staff_users.html",
        {
            "page_obj": page_obj,
            "search": search,
            "total_users": User.objects.count(),
            "student_users": User.objects.filter(
                role=User.Role.STUDENT,
                is_staff=False,
                is_superuser=False,
            ).count(),
            "guardian_users": User.objects.filter(role=User.Role.GUARDIAN).count(),
            "staff_users_count": User.objects.filter(is_staff=True).count(),
            "recent_users": User.objects.filter(
                date_joined__gte=now - timedelta(days=30)
            ).count(),
            "competition_registrations": CompetitionRegistration.objects.count(),
            "current_season": current_season,
            "current_season_registrations": (
                CompetitionRegistration.objects.filter(season=current_season).count()
                if current_season
                else 0
            ),
            "can_manage_users": True,
            "season_is_open": current_season.is_registration_open() if current_season else False,
            "can_manage_content": request.user.has_perm("cms.view_announcement"),
            "can_view_activity": request.user.has_perm("audit.view_auditlog"),
            "staff_page_label": "Participants & users",
        },
    )


@login_required
def staff_user_edit(request, pk):
    if not request.user.is_staff or not request.user.has_perm("accounts.change_user"):
        raise PermissionDenied
    account = get_object_or_404(User, pk=pk)
    if account.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    profile = StudentProfile.objects.filter(user=account).first()
    form = StaffUserForm(
        request.POST or None,
        user=account,
        profile=profile,
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            account = form.save()
            record_event(request, action="user.updated", instance=account)
        messages.success(request, "The user account was updated.")
        return redirect("accounts:staff-users")
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "accounts/staff_user_form.html",
        {
            "form": form,
            "account": account,
            "current_season": _current_season(),
            "can_manage_users": True,
            "can_manage_content": request.user.has_perm("cms.view_announcement"),
            "can_view_activity": request.user.has_perm("audit.view_auditlog"),
            "staff_page_label": "Edit user",
        },
    )


@login_required
def staff_user_deactivate(request, pk):
    if not request.user.is_staff or not request.user.has_perm("accounts.delete_user"):
        raise PermissionDenied
    if request.method != "POST":
        raise PermissionDenied
    account = get_object_or_404(User, pk=pk)
    if account.is_superuser or account.pk == request.user.pk:
        raise PermissionDenied
    if account.is_active:
        with transaction.atomic():
            account.is_active = False
            account.save(update_fields=["is_active"])
            record_event(request, action="user.deactivated", instance=account)
        messages.success(
            request,
            "Account access was removed. Registration history has been retained.",
        )
    else:
        messages.info(request, "This account is already inactive.")
    return redirect("accounts:staff-users")


@login_required
def annual_registration(request):
    season = get_object_or_404(CompetitionSeason, is_current=True)
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    if not season.is_registration_open():
        messages.info(request, f"Registration for {season.year} is not open.")
        return redirect("accounts:dashboard")
    if CompetitionRegistration.objects.filter(student=request.user, season=season).exists():
        messages.info(request, f"You are already registered for {season.year}.")
        return redirect("accounts:dashboard")

    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    form = AnnualRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            registration = register_student(
                student=request.user,
                season_id=season.pk,
                school_name=form.cleaned_data["school_name"],
                grade=form.cleaned_data["grade"],
                request=request,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request,
                f"You're registered for {season.year}. Your participant number is {registration.registration_number}.",
            )
            return redirect("accounts:dashboard")
    if request.method == "POST":
        messages.warning(request, "Please review the highlighted fields and try again.")
    return render(
        request,
        "accounts/annual_registration.html",
        {
            "form": form,
            "season": season,
            "profile": profile,
            "previous_registration": request.user.competition_registrations.select_related(
                "season", "division__level"
            ).first(),
        },
    )


@login_required
def profile(request):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    student_profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    season = _current_season()
    can_edit = bool(season and season.is_profile_edit_open())
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = StudentProfileForm(request.POST, user=request.user, profile=student_profile)
        if form.is_valid():
            form.save()
            record_event(request, action="student_profile.updated", instance=student_profile)
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        messages.warning(request, "Please review the highlighted fields and try again.")
    else:
        form = StudentProfileForm(user=request.user, profile=student_profile) if can_edit else None
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "profile": student_profile,
            "can_edit": can_edit,
            "season": season,
            "current_registration": (
                request.user.competition_registrations.filter(season=season).first()
                if season
                else None
            ),
            "registrations": request.user.competition_registrations.select_related(
                "season", "division__level"
            ),
        },
    )


@login_required
def registration_history(request):
    registrations = request.user.competition_registrations.select_related(
        "season", "division__level"
    )
    return render(
        request,
        "accounts/registration_history.html",
        {"registrations": registrations, "current_season": _current_season()},
    )
