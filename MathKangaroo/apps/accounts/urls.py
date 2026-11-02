from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.participant_login, name="login"),
    path("logout/", views.participant_logout, name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html",
        email_template_name="accounts/password_reset_email.html",
        subject_template_name="accounts/password_reset_subject.txt",
        success_url="/password-reset/done/",
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url="/reset/done/",
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/users/", views.staff_users, name="staff-users"),
    path("dashboard/users/<int:pk>/edit/", views.staff_user_edit, name="staff-user-edit"),
    path("dashboard/users/<int:pk>/deactivate/", views.staff_user_deactivate, name="staff-user-deactivate"),
    path("dashboard/profile/", views.profile, name="profile"),
    path("dashboard/registrations/", views.registration_history, name="registration-history"),
    path("dashboard/register/", views.annual_registration, name="annual-registration"),
]
