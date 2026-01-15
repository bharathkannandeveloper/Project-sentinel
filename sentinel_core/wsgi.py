"""
WSGI config for Project Sentinel.

This exposes the WSGI callable as a module-level variable named ``application``.
For production deployments not using ASGI.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel_core.settings.development")

application = get_wsgi_application()
