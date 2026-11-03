from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CompetitionSeason(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REGISTRATION_OPEN = "registration_open", "Registration open"
        REGISTRATION_CLOSED = "registration_closed", "Registration closed"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=120)
    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(9999)]
    )
    slug = models.SlugField(unique=True)
    registration_open_at = models.DateTimeField(null=True, blank=True)
    registration_close_at = models.DateTimeField(null=True, blank=True)
    competition_date = models.DateTimeField(null=True, blank=True)
    result_date = models.DateTimeField(null=True, blank=True)
    profile_edit_open_at = models.DateTimeField(null=True, blank=True)
    profile_edit_close_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_current"],
                condition=Q(is_current=True),
                name="one_current_competition_season",
            )
        ]

    def __str__(self):
        return self.name

    def is_registration_open(self, at=None):
        at = at or timezone.now()
        return (
            self.status == self.Status.REGISTRATION_OPEN
            and (self.registration_open_at is None or self.registration_open_at <= at)
            and (self.registration_close_at is None or at <= self.registration_close_at)
        )

    def is_profile_edit_open(self, at=None):
        at = at or timezone.now()
        return (
            self.profile_edit_open_at is not None
            and self.profile_edit_close_at is not None
            and self.profile_edit_open_at <= at <= self.profile_edit_close_at
        )


class CompetitionLevel(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=32, unique=True)
    min_grade = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    max_grade = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["display_order", "min_grade"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    min_grade__gte=1,
                    min_grade__lte=12,
                    max_grade__gte=1,
                    max_grade__lte=12,
                ),
                name="competition_level_grade_bounds_valid",
            ),
            models.CheckConstraint(
                condition=Q(max_grade__gte=models.F("min_grade")),
                name="competition_level_grade_range_valid",
            )
        ]

    def __str__(self):
        return self.name


class CompetitionDivision(models.Model):
    season = models.ForeignKey(CompetitionSeason, on_delete=models.PROTECT, related_name="divisions")
    level = models.ForeignKey(CompetitionLevel, on_delete=models.PROTECT, related_name="divisions")
    grade = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    ranking_group = models.CharField(max_length=80, blank=True)
    question_count = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    max_score = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["level__display_order", "grade"]
        constraints = [
            models.UniqueConstraint(fields=["season", "grade"], name="unique_season_grade_division"),
            models.CheckConstraint(condition=Q(grade__gte=1, grade__lte=12), name="division_grade_valid"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.level_id and self.grade and not self.level.min_grade <= self.grade <= self.level.max_grade:
            raise ValidationError({"grade": "The grade must be within the selected competition level."})

    def __str__(self):
        return f"Grade {self.grade} — {self.level.name} ({self.season.year})"


class Syllabus(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    division = models.OneToOneField(CompetitionDivision, on_delete=models.PROTECT, related_name="syllabus")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["division__level__display_order", "division__grade"]

    def __str__(self):
        return self.title


class SyllabusTopic(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name="topics")
    topic = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.topic


class RegistrationSequence(models.Model):
    season = models.OneToOneField(
        CompetitionSeason,
        on_delete=models.CASCADE,
        related_name="registration_sequence",
    )
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.season.year}: next {self.next_number:05d}"


class CompetitionRegistration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    registration_number = models.CharField(max_length=7, unique=True, editable=False)
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="competition_registrations",
    )
    season = models.ForeignKey(
        CompetitionSeason,
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    division = models.ForeignKey(
        CompetitionDivision,
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    school_name = models.CharField(max_length=180)
    grade = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REGISTERED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-season__year", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "season"], name="one_registration_per_student_season"),
            models.CheckConstraint(condition=Q(grade__gte=1, grade__lte=12), name="registration_grade_valid"),
        ]
        indexes = [models.Index(fields=["season", "status"], name="registration_season_status_idx")]

    def __str__(self):
        return f"{self.registration_number} — {self.student}"
