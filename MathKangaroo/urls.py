"""
URL configuration for MathKangaroo project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import posixpath

from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path
from django.views.static import serve

# Upload folders whose files must only be served by permission-checking views.
# Question papers now live in PRIVATE_MEDIA_ROOT; this also covers copies left
# in MEDIA_ROOT by installations that predate that move.
PRIVATE_MEDIA_PREFIXES = ("question-papers/",)


def serve_media(request, path):
    # Fallback for uploads the web server does not serve itself (on cPanel the
    # web server serves MEDIA_ROOT directly when it lives in public_html).
    # Normalize exactly as django.views.static.serve does, so dot segments
    # ("hero-slides/../question-papers/...") cannot slip past the check.
    if posixpath.normpath(path).lstrip("/").startswith(PRIVATE_MEDIA_PREFIXES):
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("apps.cms.urls")),
    path("", include("apps.accounts.urls")),
]

handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"

urlpatterns += [path("media/<path:path>", serve_media)]
