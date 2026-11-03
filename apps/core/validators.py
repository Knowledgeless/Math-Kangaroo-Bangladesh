from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


def validate_safe_link(value):
    if not value:
        return
    if value.startswith("#") and not any(character in value for character in "\r\n\\"):
        return
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValidationError("Use a site-relative path or a secure HTTPS URL.")
