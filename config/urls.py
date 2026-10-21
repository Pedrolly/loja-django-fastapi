from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def home(request):
    return JsonResponse(
        {
            "app": "Loja Django + FastAPI",
            "admin": "/admin/",
            "api_docs": "/api/docs",
        }
    )


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),
]
