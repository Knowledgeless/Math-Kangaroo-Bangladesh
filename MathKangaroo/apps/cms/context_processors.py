from .models import SiteSettings


def site_settings(_request):
    return {"site_settings": SiteSettings.objects.filter(pk=1).first()}
