from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property


class SingleExtensionNameMixin:
    """Keep only the final extension of an uploaded file's name.

    "shell.php.jpg" becomes "shell_php.jpg". Web servers that map handlers by
    any extension in a name (Apache's AddHandler, used by cPanel MultiPHP)
    would otherwise run such an upload as a script. Hidden names are refused.
    """

    def get_valid_name(self, name):
        name = super().get_valid_name(name)
        stem, dot, extension = name.rpartition(".")
        if not dot:
            return name
        stem = stem.replace(".", "_").strip("_") or "upload"
        return f"{stem}.{extension}"


@deconstructible(path="apps.core.storage.PublicMediaStorage")
class PublicMediaStorage(SingleExtensionNameMixin, FileSystemStorage):
    """Default storage for public uploads under MEDIA_ROOT."""


@deconstructible(path="apps.core.storage.PrivateMediaStorage")
class PrivateMediaStorage(SingleExtensionNameMixin, FileSystemStorage):
    """Uploads that must never be reachable by URL.

    Files live under PRIVATE_MEDIA_ROOT, outside every web-served directory,
    and are read only by views that check permissions and publication state
    (for example the question-paper download view).
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("file_permissions_mode", 0o640)
        kwargs.setdefault("directory_permissions_mode", 0o750)
        super().__init__(**kwargs)

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def _clear_cached_properties(self, setting, **kwargs):
        super()._clear_cached_properties(setting, **kwargs)
        if setting == "PRIVATE_MEDIA_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)

    def url(self, name):
        raise ValueError(
            "Private files have no public URL; serve them through a permission-checked view."
        )
