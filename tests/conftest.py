"""
Pytest configuration for Project Sentinel tests.
"""
import os
import sys

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel_core.settings.development")


@pytest.fixture(scope="session")
def django_setup():
    """Set up Django for tests."""
    import django
    django.setup()


@pytest.fixture
def mock_redis():
    """Mock Redis for tests that don't need real Redis."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.keys.return_value = []
    return mock
