from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.audit.models import record_event
from apps.competitions.models import CompetitionRegistration, CompetitionSeason
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
            else:
                login(request, user)
                messages.success(
                    request,
                    f"You're registered for {season.year}. Your participant username is {registration.registration_number}.",
                )
                return redirect("accounts:dashboard")
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
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("accounts:dashboard")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


def participant_logout(request):
    if request.method != "POST":
        raise PermissionDenied
    logout(request)
    return redirect("home")


@login_required
def dashboard(request):
    can_manage_users = request.user.is_staff and request.user.has_perm("accounts.view_user")
    if can_manage_users:
        return redirect("accounts:staff-users")
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
    return render(
        request,
        "accounts/staff_user_form.html",
        {"form": form, "account": account},
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
