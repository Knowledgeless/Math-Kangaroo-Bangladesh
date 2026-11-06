from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property


@deconstructible(path="apps.core.storage.PrivateMediaStorage")
class PrivateMediaStorage(FileSystemStorage):
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
