"""ASGI entry point (gunicorn + uvicorn workers). DJANGO_SETTINGS_MODULE comes
from the environment."""

import os

from django.core.asgi import get_asgi_application

os.environ["DJANGO_SETTINGS_MODULE"]

application = get_asgi_application()
