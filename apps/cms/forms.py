from django import forms

from .models import Announcement, FAQ, HeroSlide, SiteSettings


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
