from django.http import HttpResponse
from django.template.loader import render_to_string


def permission_denied(request, exception):
    return HttpResponse(render_to_string("errors/403.html"), status=403)


def page_not_found(request, exception):
    return HttpResponse(render_to_string("errors/404.html"), status=404)


def server_error(request):
    return HttpResponse(render_to_string("errors/500.html"), status=500)
