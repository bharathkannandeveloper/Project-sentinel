"""
Development Settings for Project Sentinel
"""
from .base import *  # noqa: F401, F403

# Development specific settings
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Use in-memory channel layer for development if Redis not available
try:
    import redis
    r = redis.Redis.from_url(REDIS_URL)  # noqa: F405
    r.ping()
except Exception:
    # Fall back to in-memory channel layer
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# More verbose logging in development
LOGGING["loggers"]["sentinel"]["level"] = "DEBUG"  # noqa: F405
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405

# Disable CSRF for API development (remove in production)
# CSRF_TRUSTED_ORIGINS = ["http://localhost:*", "http://127.0.0.1:*"]
