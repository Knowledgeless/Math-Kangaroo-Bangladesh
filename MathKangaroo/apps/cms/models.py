from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.validators import validate_safe_link


class PublicationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=120, default="Math Kangaroo Bangladesh")
    tagline = models.CharField(max_length=180, blank=True)
    contact_email = models.EmailField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.site_name


class HeroSlide(models.Model):
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=280, blank=True)
    image_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])
    mobile_image_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])
    button_1_label = models.CharField(max_length=40, blank=True)
    button_1_url = models.CharField(max_length=240, blank=True, validators=[validate_safe_link])
    button_2_label = models.CharField(max_length=40, blank=True)
    button_2_url = models.CharField(max_length=240, blank=True, validators=[validate_safe_link])
    status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT)
    display_order = models.PositiveSmallIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="hero_slides"
    )

    class Meta:
        ordering = ["display_order", "id"]
        permissions = [("publish_heroslide", "Can publish hero slides")]

    def is_public(self):
        return self.status == PublicationStatus.PUBLISHED and (
            self.published_at is None or self.published_at <= timezone.now()
        )

    def __str__(self):
        return self.title


class Announcement(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "General"
        REGISTRATION = "registration", "Registration"
        COMPETITION = "competition", "Competition"
        RESULTS = "results", "Results"
        SCHOOLS = "schools", "Schools"

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.CharField(max_length=320)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    cover_image_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])
    cover_image_alt_text = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    pinned = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="announcements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-published_at", "-created_at"]
        permissions = [("publish_announcement", "Can publish announcements")]
        indexes = [models.Index(fields=["status", "published_at"], name="announcement_publication_idx")]

    def is_public(self):
        return self.status == PublicationStatus.PUBLISHED and (
            self.published_at is None or self.published_at <= timezone.now()
        )

    def clean(self):
        if self.cover_image_url and not self.cover_image_alt_text.strip():
            raise ValidationError({"cover_image_alt_text": "Describe the image for visitors who cannot see it."})

    def get_absolute_url(self):
        return reverse("announcement-detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title


class FAQCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "FAQ categories"

    def __str__(self):
        return self.name


class FAQ(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.PROTECT, related_name="questions")
    question = models.CharField(max_length=240)
    answer = models.TextField()
    status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT)
    display_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__display_order", "display_order", "id"]
        permissions = [("publish_faq", "Can publish FAQs")]

    def __str__(self):
        return self.question


class PublicResource(models.Model):
    class Kind(models.TextChoices):
        PRACTICE = "practice", "Practice question"
        PAST_PAPER = "past_paper", "Past paper"
        SOLUTION = "solution", "Solution"

    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=320, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    grade_min = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    grade_max = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    resource_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])
    status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "title"]
        permissions = [("publish_publicresource", "Can publish public resources")]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(grade_min__isnull=True)
                    | models.Q(grade_min__gte=1, grade_min__lte=12)
                ),
                name="public_resource_grade_min_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(grade_max__isnull=True)
                    | models.Q(grade_max__gte=1, grade_max__lte=12)
                ),
                name="public_resource_grade_max_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(grade_min__isnull=True)
                    | models.Q(grade_max__isnull=True)
                    | models.Q(grade_max__gte=models.F("grade_min"))
                ),
                name="public_resource_grade_range_valid",
            ),
        ]

    def clean(self):
        if self.grade_min is not None and self.grade_max is not None and self.grade_max < self.grade_min:
            raise ValidationError({"grade_max": "The maximum grade must be at least the minimum grade."})

    def is_public(self):
        return self.status == PublicationStatus.PUBLISHED and (
            self.published_at is None or self.published_at <= timezone.now()
        )

    def __str__(self):
        return self.title
