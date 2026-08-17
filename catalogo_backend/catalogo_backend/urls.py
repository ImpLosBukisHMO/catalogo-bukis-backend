"""
URL configuration for catalogo_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
import re

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


def serve_media(request, path, **kwargs):
    return static_serve(request, path, document_root=settings.MEDIA_ROOT, **kwargs)


@api_view(["GET"])
def view_root(request):
    return Response("API Root", status=status.HTTP_200_OK)


urlpatterns = [
    path("", view_root),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]

media_url = settings.MEDIA_URL.lstrip("/")

if media_url:
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"

    urlpatterns += [
        re_path(rf"^{re.escape(media_url)}(?P<path>.*)$", serve_media, name="media"),
    ]
