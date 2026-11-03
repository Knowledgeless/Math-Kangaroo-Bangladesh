from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import StudentProfile, User


GRADE_CHOICES = [(grade, f"Grade {grade}") for grade in range(1, 13)]


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class StudentSignupForm(StyledForm):
    first_name = forms.CharField(max_length=150, label="Student's first name")
    last_name = forms.CharField(max_length=150, label="Student's last name")
    email = forms.EmailField(label="Email address for updates and password recovery")
    date_of_birth = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )
    phone = forms.CharField(max_length=24, required=False, label="Student phone (optional)")
    guardian_name = forms.CharField(max_length=150, label="Parent or guardian name")
    guardian_phone = forms.CharField(max_length=24, label="Parent or guardian phone")
    district = forms.CharField(max_length=100, required=False, label="District (optional)")
    school_name = forms.CharField(max_length=180, label="School name")
    grade = forms.TypedChoiceField(choices=GRADE_CHOICES, coerce=int, label="Current grade")
    password1 = forms.CharField(
        label="Create a password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data["date_of_birth"]
        if date_of_birth > timezone.localdate():
            raise ValidationError("Date of birth cannot be in the future.")
        return date_of_birth

    def clean_school_name(self):
        school_name = self.cleaned_data["school_name"].strip()
        if not school_name:
            raise ValidationError("Enter the student's school.")
        return school_name

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        confirmation = cleaned_data.get("password2")
        if password and confirmation and password != confirmation:
            self.add_error("password2", "The passwords do not match.")
        if password and cleaned_data.get("first_name") and cleaned_data.get("last_name"):
            candidate = User(
                first_name=cleaned_data["first_name"],
                last_name=cleaned_data["last_name"],
                email=cleaned_data.get("email", ""),
            )
            try:
                password_validation.validate_password(password, candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data


class AnnualRegistrationForm(StyledForm):
    school_name = forms.CharField(max_length=180, label="School for this competition year")
    grade = forms.TypedChoiceField(choices=GRADE_CHOICES, coerce=int, label="Grade for this competition year")

    def clean_school_name(self):
        school_name = self.cleaned_data["school_name"].strip()
        if not school_name:
            raise ValidationError("Enter the student's school.")
        return school_name


class StudentProfileForm(StyledForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(label="Email address")
    date_of_birth = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )
    phone = forms.CharField(max_length=24, required=False, label="Student phone (optional)")
    guardian_name = forms.CharField(max_length=150, label="Parent or guardian name")
    guardian_phone = forms.CharField(max_length=24, label="Parent or guardian phone")
    district = forms.CharField(max_length=100, required=False, label="District (optional)")

    def __init__(self, *args, user, profile, **kwargs):
        initial = kwargs.pop("initial", {})
        initial.update(
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "date_of_birth": profile.date_of_birth,
                "phone": profile.phone,
                "guardian_name": profile.guardian_name,
                "guardian_phone": profile.guardian_phone,
                "district": profile.district,
            }
        )
        super().__init__(*args, initial=initial, **kwargs)
        self.user = user
        self.profile = profile

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data["date_of_birth"]
        if date_of_birth > timezone.localdate():
            raise ValidationError("Date of birth cannot be in the future.")
        return date_of_birth

    def save(self):
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"].strip().lower()
        self.user.save(update_fields=["first_name", "last_name", "email"])
        for field in ("date_of_birth", "phone", "guardian_name", "guardian_phone", "district"):
            setattr(self.profile, field, self.cleaned_data[field])
        self.profile.save(
            update_fields=["date_of_birth", "phone", "guardian_name", "guardian_phone", "district"]
        )
        return self.profile


class StaffUserForm(StyledForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(label="Email address", required=False)
    role = forms.ChoiceField(choices=User.Role.choices, label="Account type")
    phone = forms.CharField(max_length=24, required=False, label="Student phone")
    is_active = forms.BooleanField(required=False, label="Account is active")

    def __init__(self, *args, user, profile=None, actor, **kwargs):
        initial = kwargs.pop("initial", {})
        initial.update(
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": user.role,
                "phone": profile.phone if profile else "",
                "is_active": user.is_active,
            }
        )
        super().__init__(*args, initial=initial, **kwargs)
        self.user = user
        self.profile = profile
        self.actor = actor

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        if (
            not cleaned_data.get("is_active", False)
            and (self.user.is_superuser or self.user.pk == self.actor.pk)
        ):
            self.add_error("is_active", "You cannot deactivate this protected account.")
        return cleaned_data

    def save(self):
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"]
        self.user.role = self.cleaned_data["role"]
        self.user.is_active = self.cleaned_data["is_active"]
        self.user.save(update_fields=["first_name", "last_name", "email", "role", "is_active"])

        profile = self.profile
        if profile is None and self.user.role == User.Role.STUDENT:
            profile = StudentProfile.objects.create(user=self.user)
        if profile is not None:
            profile.phone = self.cleaned_data["phone"]
            profile.save(update_fields=["phone"])
            self.profile = profile
        return self.user


class ParticipantLoginForm(forms.Form):
    username = forms.CharField(
        label="Participant username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "inputmode": "numeric"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(
                self.request,
                username=username.strip(),
                password=password,
            )
            if self.user_cache is None:
                raise ValidationError("The participant username or password is incorrect.")
        return cleaned_data

    def get_user(self):
        return self.user_cache
