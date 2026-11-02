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


class HeroSlideForm(StyledModelForm):
    class Meta:
        model = HeroSlide
        fields = (
            "title",
            "subtitle",
            "image_url",
            "mobile_image_url",
            "button_1_label",
            "button_1_url",
            "button_2_label",
            "button_2_url",
            "display_order",
        )
        widgets = {"subtitle": forms.Textarea(attrs={"rows": 3})}


class SiteSettingsForm(StyledModelForm):
    class Meta:
        model = SiteSettings
        fields = ("site_name", "tagline", "contact_email")
