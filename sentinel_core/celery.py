"""
Celery Configuration for Project Sentinel

This module initializes the Celery application with Redis as the broker
and result backend. It supports Canvas primitives (Chords, Groups) for
distributed task orchestration.
"""
import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sentinel_core.settings.development")

app = Celery("sentinel")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Canvas Configuration for robust Chord handling
app.conf.update(
    # Task routing
    task_routes={
        "src.ingestion.tasks.*": {"queue": "ingestion"},
        "src.analysis.tasks.*": {"queue": "analysis"},
        "src.knowledge.tasks.*": {"queue": "knowledge"},
    },
    
    # Chord error handling - allow callback even if some tasks fail
    chord_ignore_result=False,
    chord_join_timeout=300,
    
    # Result backend settings for reliable Chord synchronization
    result_extended=True,
    result_chord_retry_interval=1.0,
    result_chord_join_timeout=300,
    
    # Task prefetch optimization
    worker_prefetch_multiplier=4,
    
    # Retry policy for transient failures
    task_annotations={
        "*": {
            "rate_limit": "100/m",
            "max_retries": 3,
            "default_retry_delay": 60,
        }
    },
    
    # MessagePack serialization for efficiency
    accept_content=["json", "msgpack"],
    task_serializer="json",
    result_serializer="json",
)


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:
    """Debug task for testing Celery connectivity."""
    return f"Request: {self.request!r}"
