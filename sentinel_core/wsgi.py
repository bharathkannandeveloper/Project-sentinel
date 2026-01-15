"""
WSGI config for Project Sentinel.

This exposes the WSGI callable as a module-level variable named ``application``.
For production deployments (Vercel, etc.).
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel_core.settings.production")

application = get_wsgi_application()
app = application  # Vercel looks for 'app'
