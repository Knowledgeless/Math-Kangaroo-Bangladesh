from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(username__iexact=username.strip())

    def _create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError("A participant username is required.")
        user = self.model(username=username.strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(username, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        GUARDIAN = "guardian", "Guardian"
        STAFF = "staff", "Staff"

    email = models.EmailField("email address", blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def save(self, *args, **kwargs):
        self.username = self.username.strip()
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username


class GuardianProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="guardian_profile")
    preferred_language = models.CharField(max_length=12, default="en")

    def __str__(self):
        return f"Guardian profile for {self.user}"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=24, blank=True)
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_phone = models.CharField(max_length=24, blank=True)
    district = models.CharField(max_length=100, blank=True)
    grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grade__isnull=True) | models.Q(grade__gte=1, grade__lte=12),
                name="student_profile_grade_valid",
            )
        ]

    def __str__(self):
        return f"Student profile for {self.user}"
