"""
Ponto de entrada ASGI: um único servidor atende Django e FastAPI.

  /api/*  -> FastAPI (docs em /api/docs)
  demais  -> Django (admin, páginas)
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# get_asgi_application() chama django.setup(); só depois podemos importar
# o FastAPI, que usa os models do Django.
django_app = get_asgi_application()

from api.main import app as fastapi_app  # noqa: E402


async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        await fastapi_app(scope, receive, send)
    elif scope["type"] in ("http", "websocket") and scope["path"].startswith("/api"):
        await fastapi_app(scope, receive, send)
    else:
        await django_app(scope, receive, send)
