from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.forms import inlineformset_factory
from django.db.models import Q

from apps.competitions.models import CompetitionDivision, Syllabus, SyllabusTopic
from .content_sanitizer import sanitize_about_content
from .models import AboutPage, Announcement, FAQ, HeroSlide, QuestionPaper, SiteSettings


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class AnnouncementForm(StyledModelForm):
    class Meta:
        model = Announcement
        fields = (
            "title",
            "slug",
            "summary",
            "content",
            "category",
            "cover_image_url",
            "cover_image_alt_text",
            "pinned",
            "meta_title",
            "meta_description",
        )
        widgets = {
            "content": forms.Textarea(attrs={"rows": 8}),
            "summary": forms.Textarea(attrs={"rows": 3}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
        }


class FAQForm(StyledModelForm):
    class Meta:
        model = FAQ
        fields = ("category", "question", "answer", "display_order")
        widgets = {"answer": forms.Textarea(attrs={"rows": 6})}


class HeroSlideImageField(forms.ImageField):
    def to_python(self, value):
        if value and value.size >= HeroSlide.MAX_IMAGE_SIZE:
            raise forms.ValidationError("Choose an image smaller than 300 KB.")
        return super().to_python(value)


class HeroSlideForm(StyledModelForm):
    image = HeroSlideImageField(
        label="Slider image",
        help_text="Use a 1200 × 630 image smaller than 300 KB.",
    )
    display_order = forms.IntegerField(min_value=0, max_value=65535, initial=0)

    class Meta:
        model = HeroSlide
        fields = ("image", "display_order")

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.image.width * 630 != image.image.height * 1200:
            raise forms.ValidationError("Use an image with a 1200 × 630 (40:21) ratio.")
        return image


class HeroSlideOrderForm(forms.Form):
    display_order = forms.IntegerField(min_value=0, max_value=65535)


class SiteSettingsForm(StyledModelForm):
    class Meta:
        model = SiteSettings
        fields = ("site_name", "tagline", "contact_email")


class AboutPageForm(StyledModelForm):
    class Meta:
        model = AboutPage
        fields = ("title", "introduction", "content")
        widgets = {
            "introduction": forms.Textarea(attrs={"rows": 3}),
            "content": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk:
            self.initial["content"] = sanitize_about_content(self.instance.content)

    def clean_content(self):
        return sanitize_about_content(self.cleaned_data["content"])


class QuestionPaperForm(StyledModelForm):
    pdf_file = forms.FileField(
        label="Question PDF",
        required=False,
        help_text="Upload a PDF file no larger than 20 MB.",
    )

    class Meta:
        model = QuestionPaper
        fields = ("title", "description", "year", "category", "pdf_file")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "year": forms.NumberInput(attrs={"min": 2000, "max": 9999}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["pdf_file"].required = False
        else:
            self.fields["pdf_file"].required = True
        self.fields["category"].help_text = "For example: Pre-Ecolier, Ecolier, or Solutions."

    def clean_category(self):
        category = self.cleaned_data["category"].strip()
        if not category:
            raise forms.ValidationError("Enter a category for this question paper.")
        return category

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get("pdf_file")
        if isinstance(pdf_file, UploadedFile):
            if pdf_file.size > QuestionPaper.MAX_FILE_SIZE:
                raise forms.ValidationError("Choose a PDF smaller than 20 MB.")
            if not pdf_file.name.lower().endswith(".pdf"):
                raise forms.ValidationError("Upload a PDF file.")
            if pdf_file.read(5) != b"%PDF-":
                raise forms.ValidationError("The uploaded file is not a valid PDF.")
            pdf_file.seek(0)
        return pdf_file


class SyllabusForm(StyledModelForm):
    class Meta:
        model = Syllabus
        fields = ("division", "title", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        divisions = CompetitionDivision.objects.select_related("season", "level").order_by(
            "-season__year", "level__display_order", "grade"
        )
        if self.instance.pk:
            divisions = divisions.filter(Q(syllabus__isnull=True) | Q(pk=self.instance.division_id))
        else:
            divisions = divisions.filter(syllabus__isnull=True)
        self.fields["division"].queryset = divisions


class SyllabusTopicForm(StyledModelForm):
    class Meta:
        model = SyllabusTopic
        fields = ("topic", "description", "display_order")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "display_order": forms.NumberInput(attrs={"min": 0, "max": 65535}),
        }


SyllabusTopicFormSet = inlineformset_factory(
    Syllabus,
    SyllabusTopic,
    form=SyllabusTopicForm,
    extra=2,
    can_delete=True,
)
