from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cms"
    label = "cms"

    def ready(self):
        from .permissions import sync_staff_groups

        post_migrate.connect(
            sync_staff_groups,
            sender=self,
            dispatch_uid="cms.sync_staff_groups",
        )
