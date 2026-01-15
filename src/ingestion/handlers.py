"""
Error Handlers for Data Ingestion

Implements the FailureHandler pattern for resilient Celery Chord execution.
When individual tasks in a Chord fail, the handler captures the error and
allows the callback to proceed with partial data.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger("sentinel.ingestion.handlers")


class FailureType(str, Enum):
    """Types of ingestion failures."""
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    NOT_FOUND = "not_found"
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class FailureObject:
    """
    Represents a failed task result that doesn't break the Chord.
    
    Instead of raising an exception (which would fail the entire Chord),
    tasks return this object to indicate failure while allowing the
    aggregate callback to proceed with partial data.
    """
    ticker: str
    failure_type: FailureType
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3
    raw_error: str | None = None
    
    @property
    def is_retryable(self) -> bool:
        """Check if this failure can be retried."""
        retryable_types = {
            FailureType.RATE_LIMIT,
            FailureType.TIMEOUT,
            FailureType.NETWORK_ERROR,
        }
        return (
            self.failure_type in retryable_types and
            self.retry_count < self.max_retries
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ticker": self.ticker,
            "failure_type": self.failure_type.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "is_retryable": self.is_retryable,
        }


class FailureHandler:
    """
    Centralized handler for ingestion failures.
    
    Logs failures to Redis for monitoring and potential retry.
    Provides aggregation statistics for dashboard display.
    """
    
    REDIS_KEY_PREFIX = "sentinel:failures:"
    FAILURE_TTL = 86400  # 24 hours
    
    def __init__(self) -> None:
        """Initialize the failure handler with Redis connection."""
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        try:
            self._redis = redis.Redis.from_url(redis_url)
        except Exception as e:
            logger.warning(f"Redis not available for failure tracking: {e}")
            self._redis = None
    
    def log_failure(self, failure: FailureObject) -> None:
        """
        Log a failure to Redis for tracking.
        
        Args:
            failure: The failure object to log
        """
        if not self._redis:
            logger.warning(f"Failure not logged (no Redis): {failure.ticker} - {failure.message}")
            return
        
        try:
            import json
            key = f"{self.REDIS_KEY_PREFIX}{failure.ticker}:{failure.timestamp.timestamp()}"
            self._redis.setex(
                key,
                self.FAILURE_TTL,
                json.dumps(failure.to_dict())
            )
            
            # Increment failure counter
            counter_key = f"{self.REDIS_KEY_PREFIX}count:{failure.failure_type.value}"
            self._redis.incr(counter_key)
            self._redis.expire(counter_key, self.FAILURE_TTL)
            
            logger.info(f"Logged failure: {failure.ticker} ({failure.failure_type})")
            
        except Exception as e:
            logger.error(f"Failed to log failure to Redis: {e}")
    
    def get_failure_stats(self) -> dict[str, int]:
        """
        Get failure statistics by type.
        
        Returns:
            Dictionary mapping failure types to counts
        """
        if not self._redis:
            return {}
        
        stats = {}
        for failure_type in FailureType:
            key = f"{self.REDIS_KEY_PREFIX}count:{failure_type.value}"
            try:
                count = self._redis.get(key)
                if count:
                    stats[failure_type.value] = int(count)
            except Exception:
                pass
        
        return stats
    
    def get_recent_failures(
        self,
        limit: int = 100,
        ticker: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent failures from Redis.
        
        Args:
            limit: Maximum number of failures to return
            ticker: Optional ticker to filter by
            
        Returns:
            List of failure dictionaries
        """
        if not self._redis:
            return []
        
        try:
            import json
            pattern = f"{self.REDIS_KEY_PREFIX}{ticker or '*'}:*"
            keys = self._redis.keys(pattern)
            
            failures = []
            for key in sorted(keys, reverse=True)[:limit]:
                data = self._redis.get(key)
                if data:
                    failures.append(json.loads(data))
            
            return failures
            
        except Exception as e:
            logger.error(f"Failed to get failures: {e}")
            return []
    
    def clear_failures(self, ticker: str | None = None) -> int:
        """
        Clear logged failures.
        
        Args:
            ticker: Optional ticker to clear (all if None)
            
        Returns:
            Number of failures cleared
        """
        if not self._redis:
            return 0
        
        try:
            pattern = f"{self.REDIS_KEY_PREFIX}{ticker or '*'}:*"
            keys = self._redis.keys(pattern)
            
            if keys:
                return self._redis.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Failed to clear failures: {e}")
            return 0


# Global handler instance
_failure_handler: FailureHandler | None = None


def get_failure_handler() -> FailureHandler:
    """Get the global failure handler instance."""
    global _failure_handler
    if _failure_handler is None:
        _failure_handler = FailureHandler()
    return _failure_handler
