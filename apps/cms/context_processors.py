from django.utils import timezone

from apps.competitions.models import CompetitionSeason
from .models import SiteSettings


def site_settings(request):
    context = {"site_settings": SiteSettings.objects.filter(pk=1).first()}
    if request.user.is_authenticated and request.user.is_staff:
        season = CompetitionSeason.objects.filter(is_current=True).first()
        context.update(
            {
                "current_season": season,
                "season_is_open": season.is_registration_open(timezone.now()) if season else False,
            }
        )
    return context
