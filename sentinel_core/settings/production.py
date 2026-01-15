"""
Production Settings for Project Sentinel
"""
from .base import *  # noqa: F401, F403

# Production specific settings
DEBUG = False

# IMPORTANT: Change 'YOUR_USERNAME' to your actual PythonAnywhere username
# Add your Vercel domain when you deploy
ALLOWED_HOSTS = [
    'YOUR_USERNAME.pythonanywhere.com',
    '.vercel.app',  # Allows all Vercel subdomains
    'localhost',
    '127.0.0.1'
]

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# HTTPS settings (enable when using HTTPS)
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# Logging
LOGGING["loggers"]["sentinel"]["level"] = "INFO"  # noqa: F405
