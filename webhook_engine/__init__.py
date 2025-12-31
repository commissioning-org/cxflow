"""
Webhook Post Engine - A comprehensive, automated webhook delivery system.

Features:
- Async HTTP client with connection pooling
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Request signing and authentication (Bearer, Basic, HMAC, API Key, Query Params)
- Payload validation and transformation
- Batch processing with rate limiting
- Dead letter queue for failed deliveries
- Comprehensive logging and metrics (Prometheus-compatible)
- CLI interface for operations
- Pre-configured Power Automate integration

Quick Start:
    from webhook_engine import WebhookEngine, trigger_power_automate
    
    # Quick send to Power Automate
    result = trigger_power_automate({"message": "Hello!"})
    
    # Full engine with queue and retry
    async with WebhookEngine() as engine:
        result = await engine.send("power_automate", {"event": "test"})

CLI Usage:
    python -m webhook_engine send power_automate --data '{"event": "test"}'
    python -m webhook_engine --help
"""

__version__ = "1.0.0"
__author__ = "CXFlow"

from .client import WebhookClient, WebhookResponse, send_webhook_sync
from .payload import PayloadBuilder, PayloadFormatter
from .retry import RetryPolicy, ExponentialBackoff, LinearBackoff, ConstantBackoff
from .circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerError
from .queue import WebhookQueue, DeadLetterQueue, WebhookMessage, RateLimiter
from .engine import (
    WebhookEngine,
    DeliveryResult,
    send_webhook,
    trigger_power_automate,
    trigger_power_automate_sync,
)
from .config import WebhookConfig, WebhookEndpoint, POWER_AUTOMATE_WEBHOOK
from .monitoring import (
    WebhookMetrics,
    MetricsRegistry,
    get_metrics,
    setup_logging,
    LogFormat,
    HealthChecker,
    HealthStatus,
)
from .integrations import (
    PowerAutomateClient,
    SlackWebhook,
    DiscordWebhook,
    TeamsWebhook,
    GenericWebhook,
    EventBridge,
)

__all__ = [
    # Core
    "WebhookEngine",
    "WebhookClient",
    "WebhookResponse",
    "DeliveryResult",
    
    # Config
    "WebhookConfig",
    "WebhookEndpoint",
    "POWER_AUTOMATE_WEBHOOK",
    
    # Payload
    "PayloadBuilder",
    "PayloadFormatter",
    
    # Retry
    "RetryPolicy",
    "ExponentialBackoff",
    "LinearBackoff",
    "ConstantBackoff",
    
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerError",
    
    # Queue
    "WebhookQueue",
    "DeadLetterQueue",
    "WebhookMessage",
    "RateLimiter",
    
    # Monitoring
    "WebhookMetrics",
    "MetricsRegistry",
    "get_metrics",
    "setup_logging",
    "LogFormat",
    "HealthChecker",
    "HealthStatus",
    
    # Integrations
    "PowerAutomateClient",
    "SlackWebhook",
    "DiscordWebhook",
    "TeamsWebhook",
    "GenericWebhook",
    "EventBridge",
    
    # Quick functions
    "send_webhook",
    "send_webhook_sync",
    "trigger_power_automate",
    "trigger_power_automate_sync",
]
