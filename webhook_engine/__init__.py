"""
Webhook Post Engine - A comprehensive, automated webhook delivery system.

Features:
- Async HTTP client with connection pooling
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Request signing and authentication
- Payload validation and transformation
- Batch processing with rate limiting
- Dead letter queue for failed deliveries
- Comprehensive logging and metrics
- CLI interface for operations
"""

__version__ = "1.0.0"
__author__ = "CXFlow"

from .client import WebhookClient, WebhookResponse
from .payload import PayloadBuilder, PayloadFormatter
from .retry import RetryPolicy, ExponentialBackoff
from .circuit_breaker import CircuitBreaker, CircuitState
from .queue import WebhookQueue, DeadLetterQueue
from .engine import WebhookEngine
from .config import WebhookConfig

__all__ = [
    "WebhookClient",
    "WebhookResponse",
    "PayloadBuilder",
    "PayloadFormatter",
    "RetryPolicy",
    "ExponentialBackoff",
    "CircuitBreaker",
    "CircuitState",
    "WebhookQueue",
    "DeadLetterQueue",
    "WebhookEngine",
    "WebhookConfig",
]
