"""Configuration management for the webhook engine."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


@dataclass
class WebhookEndpoint:
    """Represents a webhook endpoint configuration."""
    
    name: str
    url: str
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    auth_type: Optional[str] = None  # "bearer", "basic", "hmac", "api_key"
    auth_config: dict[str, Any] = field(default_factory=dict)
    retry_enabled: bool = True
    circuit_breaker_enabled: bool = True
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate endpoint configuration."""
        parsed = urlparse(self.url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {self.url}")
        if self.method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise ValueError(f"Invalid HTTP method: {self.method}")
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebhookEndpoint:
        """Create endpoint from dictionary."""
        return cls(
            name=data["name"],
            url=data["url"],
            method=data.get("method", "POST"),
            headers=data.get("headers", {}),
            timeout=data.get("timeout", 30.0),
            auth_type=data.get("auth_type"),
            auth_config=data.get("auth_config", {}),
            retry_enabled=data.get("retry_enabled", True),
            circuit_breaker_enabled=data.get("circuit_breaker_enabled", True),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "timeout": self.timeout,
            "auth_type": self.auth_type,
            "auth_config": self.auth_config,
            "retry_enabled": self.retry_enabled,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class RetryConfig:
    """Retry configuration."""
    
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_exception: bool = True


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # Time in open state before half-open
    half_open_max_calls: int = 3


@dataclass
class QueueConfig:
    """Queue configuration."""
    
    max_size: int = 10000
    batch_size: int = 100
    flush_interval: float = 5.0
    persistence_path: Optional[str] = None
    dead_letter_enabled: bool = True
    dead_letter_max_size: int = 1000


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    
    requests_per_second: float = 100.0
    burst_size: int = 200
    per_endpoint: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    
    level: str = "INFO"
    format: str = "json"  # "json" or "text"
    include_payload: bool = False
    include_response: bool = False
    log_file: Optional[str] = None


@dataclass
class WebhookConfig:
    """Main webhook engine configuration."""
    
    endpoints: dict[str, WebhookEndpoint] = field(default_factory=dict)
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Global settings
    default_timeout: float = 30.0
    default_headers: dict[str, str] = field(default_factory=lambda: {
        "Content-Type": "application/json",
        "User-Agent": "WebhookEngine/1.0",
    })
    verify_ssl: bool = True
    connection_pool_size: int = 100
    
    def add_endpoint(self, endpoint: WebhookEndpoint) -> None:
        """Add an endpoint to the configuration."""
        self.endpoints[endpoint.name] = endpoint
    
    def get_endpoint(self, name: str) -> Optional[WebhookEndpoint]:
        """Get an endpoint by name."""
        return self.endpoints.get(name)
    
    def remove_endpoint(self, name: str) -> bool:
        """Remove an endpoint by name."""
        if name in self.endpoints:
            del self.endpoints[name]
            return True
        return False
    
    @classmethod
    def from_file(cls, path: str | Path) -> WebhookConfig:
        """Load configuration from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path) as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebhookConfig:
        """Create configuration from dictionary."""
        config = cls()
        
        # Parse endpoints
        for ep_data in data.get("endpoints", []):
            endpoint = WebhookEndpoint.from_dict(ep_data)
            config.add_endpoint(endpoint)
        
        # Parse retry config
        if "retry" in data:
            rc = data["retry"]
            config.retry = RetryConfig(
                max_attempts=rc.get("max_attempts", 3),
                initial_delay=rc.get("initial_delay", 1.0),
                max_delay=rc.get("max_delay", 60.0),
                exponential_base=rc.get("exponential_base", 2.0),
                jitter=rc.get("jitter", True),
                retry_on_status=rc.get("retry_on_status", [429, 500, 502, 503, 504]),
                retry_on_exception=rc.get("retry_on_exception", True),
            )
        
        # Parse circuit breaker config
        if "circuit_breaker" in data:
            cb = data["circuit_breaker"]
            config.circuit_breaker = CircuitBreakerConfig(
                failure_threshold=cb.get("failure_threshold", 5),
                success_threshold=cb.get("success_threshold", 2),
                timeout=cb.get("timeout", 60.0),
                half_open_max_calls=cb.get("half_open_max_calls", 3),
            )
        
        # Parse queue config
        if "queue" in data:
            qc = data["queue"]
            config.queue = QueueConfig(
                max_size=qc.get("max_size", 10000),
                batch_size=qc.get("batch_size", 100),
                flush_interval=qc.get("flush_interval", 5.0),
                persistence_path=qc.get("persistence_path"),
                dead_letter_enabled=qc.get("dead_letter_enabled", True),
                dead_letter_max_size=qc.get("dead_letter_max_size", 1000),
            )
        
        # Parse rate limit config
        if "rate_limit" in data:
            rl = data["rate_limit"]
            config.rate_limit = RateLimitConfig(
                requests_per_second=rl.get("requests_per_second", 100.0),
                burst_size=rl.get("burst_size", 200),
                per_endpoint=rl.get("per_endpoint", True),
            )
        
        # Parse logging config
        if "logging" in data:
            lc = data["logging"]
            config.logging = LoggingConfig(
                level=lc.get("level", "INFO"),
                format=lc.get("format", "json"),
                include_payload=lc.get("include_payload", False),
                include_response=lc.get("include_response", False),
                log_file=lc.get("log_file"),
            )
        
        # Global settings
        config.default_timeout = data.get("default_timeout", 30.0)
        config.default_headers.update(data.get("default_headers", {}))
        config.verify_ssl = data.get("verify_ssl", True)
        config.connection_pool_size = data.get("connection_pool_size", 100)
        
        return config
    
    @classmethod
    def from_env(cls) -> WebhookConfig:
        """Create configuration from environment variables."""
        config = cls()
        
        # Default endpoint from environment
        if url := os.getenv("WEBHOOK_URL"):
            config.add_endpoint(WebhookEndpoint(
                name="default",
                url=url,
                method=os.getenv("WEBHOOK_METHOD", "POST"),
                timeout=float(os.getenv("WEBHOOK_TIMEOUT", "30")),
            ))
        
        # Retry settings
        config.retry.max_attempts = int(os.getenv("WEBHOOK_RETRY_MAX", "3"))
        config.retry.initial_delay = float(os.getenv("WEBHOOK_RETRY_DELAY", "1.0"))
        
        # Rate limit
        config.rate_limit.requests_per_second = float(
            os.getenv("WEBHOOK_RATE_LIMIT", "100")
        )
        
        # SSL verification
        config.verify_ssl = os.getenv("WEBHOOK_VERIFY_SSL", "true").lower() == "true"
        
        return config
    
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "endpoints": [ep.to_dict() for ep in self.endpoints.values()],
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "initial_delay": self.retry.initial_delay,
                "max_delay": self.retry.max_delay,
                "exponential_base": self.retry.exponential_base,
                "jitter": self.retry.jitter,
                "retry_on_status": self.retry.retry_on_status,
                "retry_on_exception": self.retry.retry_on_exception,
            },
            "circuit_breaker": {
                "failure_threshold": self.circuit_breaker.failure_threshold,
                "success_threshold": self.circuit_breaker.success_threshold,
                "timeout": self.circuit_breaker.timeout,
                "half_open_max_calls": self.circuit_breaker.half_open_max_calls,
            },
            "queue": {
                "max_size": self.queue.max_size,
                "batch_size": self.queue.batch_size,
                "flush_interval": self.queue.flush_interval,
                "persistence_path": self.queue.persistence_path,
                "dead_letter_enabled": self.queue.dead_letter_enabled,
                "dead_letter_max_size": self.queue.dead_letter_max_size,
            },
            "rate_limit": {
                "requests_per_second": self.rate_limit.requests_per_second,
                "burst_size": self.rate_limit.burst_size,
                "per_endpoint": self.rate_limit.per_endpoint,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "include_payload": self.logging.include_payload,
                "include_response": self.logging.include_response,
                "log_file": self.logging.log_file,
            },
            "default_timeout": self.default_timeout,
            "default_headers": self.default_headers,
            "verify_ssl": self.verify_ssl,
            "connection_pool_size": self.connection_pool_size,
        }
    
    def save(self, path: str | Path) -> None:
        """Save configuration to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# Pre-configured Power Automate endpoint
POWER_AUTOMATE_WEBHOOK = WebhookEndpoint(
    name="power_automate",
    url="https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/3d2dbeba15b5425b8551f67e61084464/triggers/manual/paths/invoke",
    method="POST",
    headers={
        "Content-Type": "application/json",
    },
    auth_type="query_params",
    auth_config={
        "api-version": "1",
        "sp": "/triggers/manual/run",
        "sv": "1.0",
        "sig": "zcOVZS6oRhfwU-R6rTxxk8EW32faD-S-bcar0DiFfno",
    },
    timeout=30.0,
    retry_enabled=True,
    circuit_breaker_enabled=True,
    tags=["power_automate", "microsoft", "automation"],
    metadata={
        "description": "Power Automate workflow trigger",
        "workflow_id": "3d2dbeba15b5425b8551f67e61084464",
    },
)
