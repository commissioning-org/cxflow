"""Main webhook engine orchestrator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .client import WebhookClient, WebhookResponse
from .config import WebhookConfig, WebhookEndpoint, POWER_AUTOMATE_WEBHOOK
from .payload import PayloadBuilder, PayloadFormatter
from .retry import RetryPolicy, ExponentialBackoff
from .circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, get_registry
from .queue import WebhookQueue, DeadLetterQueue, RateLimiter
from .monitoring import (
    WebhookMetrics,
    EventEmitter,
    WebhookEvents,
    HealthChecker,
    HealthStatus,
    get_metrics,
    setup_logging,
    LogFormat,
)

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Result of a webhook delivery attempt."""
    
    success: bool
    response: Optional[WebhookResponse] = None
    error: Optional[str] = None
    retries: int = 0
    elapsed_ms: float = 0
    endpoint_name: str = ""
    message_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "response": self.response.to_dict() if self.response else None,
            "error": self.error,
            "retries": self.retries,
            "elapsed_ms": self.elapsed_ms,
            "endpoint_name": self.endpoint_name,
            "message_id": self.message_id,
        }


class WebhookEngine:
    """
    Main orchestrator for webhook delivery.
    
    Combines all components:
    - HTTP client with connection pooling
    - Retry logic with exponential backoff
    - Circuit breaker for fault tolerance
    - Queue for async processing
    - Rate limiting
    - Metrics and monitoring
    
    Example:
        engine = WebhookEngine()
        engine.add_endpoint(WebhookEndpoint(
            name="myapi",
            url="https://api.example.com/webhook",
        ))
        
        result = await engine.send("myapi", {"event": "test"})
    """
    
    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        enable_queue: bool = True,
        enable_metrics: bool = True,
        enable_logging: bool = True,
        log_level: str = "INFO",
        log_format: LogFormat = LogFormat.JSON,
    ):
        self.config = config or WebhookConfig()
        
        # Core components
        self._client: Optional[WebhookClient] = None
        self._queue: Optional[WebhookQueue] = None
        self._rate_limiters: dict[str, RateLimiter] = {}
        self._circuit_breakers = CircuitBreakerRegistry()
        
        # Monitoring
        self._events = EventEmitter()
        self._health = HealthChecker()
        self._metrics: Optional[WebhookMetrics] = None
        
        # Initialize components
        if enable_queue:
            self._queue = WebhookQueue(self.config)
        
        if enable_metrics:
            self._metrics = WebhookMetrics()
        
        if enable_logging:
            setup_logging(level=log_level, format=log_format)
        
        # Set up health checks
        self._setup_health_checks()
        
        # Add default Power Automate endpoint
        self.config.add_endpoint(POWER_AUTOMATE_WEBHOOK)
    
    def _setup_health_checks(self) -> None:
        """Set up default health checks."""
        
        def check_client() -> bool:
            return True  # Client is lazily initialized
        
        def check_queue() -> bool:
            if self._queue:
                return self._queue.size() < self.config.queue.max_size
            return True
        
        self._health.register("client", check_client)
        self._health.register("queue", check_queue)
    
    def _get_client(self) -> WebhookClient:
        """Get or create the webhook client."""
        if self._client is None:
            self._client = WebhookClient(
                timeout=self.config.default_timeout,
                verify_ssl=self.config.verify_ssl,
                connection_pool_size=self.config.connection_pool_size,
                default_headers=self.config.default_headers,
            )
        return self._client
    
    def _get_rate_limiter(self, endpoint_name: str) -> RateLimiter:
        """Get or create rate limiter for endpoint."""
        if self.config.rate_limit.per_endpoint:
            key = endpoint_name
        else:
            key = "_global_"
        
        if key not in self._rate_limiters:
            self._rate_limiters[key] = RateLimiter(
                requests_per_second=self.config.rate_limit.requests_per_second,
                burst_size=self.config.rate_limit.burst_size,
            )
        
        return self._rate_limiters[key]
    
    def _get_circuit_breaker(self, endpoint_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for endpoint."""
        from .circuit_breaker import CircuitBreakerConfig
        
        return self._circuit_breakers.get(
            endpoint_name,
            CircuitBreakerConfig(
                failure_threshold=self.config.circuit_breaker.failure_threshold,
                success_threshold=self.config.circuit_breaker.success_threshold,
                timeout=self.config.circuit_breaker.timeout,
                half_open_max_calls=self.config.circuit_breaker.half_open_max_calls,
            ),
        )
    
    # Endpoint management
    
    def add_endpoint(self, endpoint: WebhookEndpoint) -> None:
        """Add a webhook endpoint."""
        self.config.add_endpoint(endpoint)
        logger.info(f"Added endpoint: {endpoint.name}")
    
    def remove_endpoint(self, name: str) -> bool:
        """Remove a webhook endpoint."""
        result = self.config.remove_endpoint(name)
        if result:
            logger.info(f"Removed endpoint: {name}")
        return result
    
    def get_endpoint(self, name: str) -> Optional[WebhookEndpoint]:
        """Get an endpoint by name."""
        return self.config.get_endpoint(name)
    
    def list_endpoints(self) -> list[str]:
        """List all endpoint names."""
        return list(self.config.endpoints.keys())
    
    # Sending webhooks
    
    async def send(
        self,
        endpoint_name: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        retry: bool = True,
        use_circuit_breaker: bool = True,
        use_rate_limit: bool = True,
    ) -> DeliveryResult:
        """
        Send a webhook to an endpoint.
        
        Args:
            endpoint_name: Name of the registered endpoint
            payload: JSON payload to send
            headers: Additional headers (optional)
            timeout: Override endpoint timeout
            retry: Whether to retry on failure
            use_circuit_breaker: Whether to use circuit breaker
            use_rate_limit: Whether to apply rate limiting
        
        Returns:
            DeliveryResult with success status and response
        """
        endpoint = self.config.get_endpoint(endpoint_name)
        if not endpoint:
            return DeliveryResult(
                success=False,
                error=f"Endpoint '{endpoint_name}' not found",
                endpoint_name=endpoint_name,
            )
        
        # Emit start event
        await self._events.emit_async(
            WebhookEvents.REQUEST_START,
            endpoint_name=endpoint_name,
            payload=payload,
        )
        
        # Record metrics
        if self._metrics:
            self._metrics.requests_total.inc()
            self._metrics.request_by_endpoint(endpoint_name).inc()
        
        # Apply rate limiting
        if use_rate_limit:
            limiter = self._get_rate_limiter(endpoint_name)
            await limiter.acquire_async()
        
        # Check circuit breaker
        cb = None
        if use_circuit_breaker and endpoint.circuit_breaker_enabled:
            cb = self._get_circuit_breaker(endpoint_name)
            if not cb.allow_request():
                if self._metrics:
                    self._metrics.requests_failed.inc()
                return DeliveryResult(
                    success=False,
                    error="Circuit breaker is open",
                    endpoint_name=endpoint_name,
                )
        
        # Override timeout if specified
        if timeout:
            endpoint = WebhookEndpoint(
                name=endpoint.name,
                url=endpoint.url,
                method=endpoint.method,
                headers=endpoint.headers,
                timeout=timeout,
                auth_type=endpoint.auth_type,
                auth_config=endpoint.auth_config,
            )
        
        client = self._get_client()
        retries = 0
        
        async def do_send() -> WebhookResponse:
            return await client.send_async(endpoint, payload, headers)
        
        # Execute with optional retry
        if retry and endpoint.retry_enabled:
            strategy = ExponentialBackoff(
                max_attempts=self.config.retry.max_attempts,
                initial_delay=self.config.retry.initial_delay,
                max_delay=self.config.retry.max_delay,
                exponential_base=self.config.retry.exponential_base,
                jitter=self.config.retry.jitter,
                retry_on_status=tuple(self.config.retry.retry_on_status),
                retry_on_exception=self.config.retry.retry_on_exception,
            )
            
            def on_retry(attempt: int, delay: float, exc: Optional[Exception]) -> None:
                nonlocal retries
                retries = attempt
                if self._metrics:
                    self._metrics.requests_retried.inc()
                self._events.emit(
                    WebhookEvents.REQUEST_RETRY,
                    endpoint_name=endpoint_name,
                    attempt=attempt,
                    delay=delay,
                    error=str(exc) if exc else None,
                )
            
            policy = RetryPolicy(strategy, on_retry=on_retry)
            
            try:
                async with self._metrics.request_duration.time() if self._metrics else _null_context():
                    response = await policy.execute_async(do_send, is_async=True)
            except Exception as e:
                if cb:
                    cb.record_failure()
                if self._metrics:
                    self._metrics.requests_failed.inc()
                return DeliveryResult(
                    success=False,
                    error=str(e),
                    retries=retries,
                    endpoint_name=endpoint_name,
                )
        else:
            try:
                async with self._metrics.request_duration.time() if self._metrics else _null_context():
                    response = await do_send()
            except Exception as e:
                if cb:
                    cb.record_failure()
                if self._metrics:
                    self._metrics.requests_failed.inc()
                return DeliveryResult(
                    success=False,
                    error=str(e),
                    endpoint_name=endpoint_name,
                )
        
        # Record result with circuit breaker
        if cb:
            cb.record_response(response)
        
        # Emit events and record metrics
        if response.success:
            if self._metrics:
                self._metrics.requests_success.inc()
            await self._events.emit_async(
                WebhookEvents.REQUEST_SUCCESS,
                endpoint_name=endpoint_name,
                response=response,
            )
        else:
            if self._metrics:
                self._metrics.requests_failed.inc()
                self._metrics.errors_by_status(response.status_code).inc()
            await self._events.emit_async(
                WebhookEvents.REQUEST_FAILURE,
                endpoint_name=endpoint_name,
                response=response,
            )
        
        return DeliveryResult(
            success=response.success,
            response=response,
            retries=retries,
            elapsed_ms=response.elapsed_ms,
            endpoint_name=endpoint_name,
        )
    
    def send_sync(
        self,
        endpoint_name: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> DeliveryResult:
        """Send a webhook synchronously (blocking)."""
        endpoint = self.config.get_endpoint(endpoint_name)
        if not endpoint:
            return DeliveryResult(
                success=False,
                error=f"Endpoint '{endpoint_name}' not found",
                endpoint_name=endpoint_name,
            )
        
        client = self._get_client()
        
        try:
            response = client.send_sync(endpoint, payload, headers)
            return DeliveryResult(
                success=response.success,
                response=response,
                elapsed_ms=response.elapsed_ms,
                endpoint_name=endpoint_name,
            )
        except Exception as e:
            return DeliveryResult(
                success=False,
                error=str(e),
                endpoint_name=endpoint_name,
            )
    
    async def send_batch(
        self,
        endpoint_name: str,
        payloads: list[dict[str, Any]],
        concurrency: int = 10,
    ) -> list[DeliveryResult]:
        """Send multiple webhooks concurrently."""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def send_with_semaphore(payload: dict[str, Any]) -> DeliveryResult:
            async with semaphore:
                return await self.send(endpoint_name, payload)
        
        tasks = [send_with_semaphore(p) for p in payloads]
        return await asyncio.gather(*tasks)
    
    # Queue operations
    
    def enqueue(
        self,
        endpoint_name: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
        priority: int = 0,
        **kwargs: Any,
    ) -> Optional[str]:
        """Enqueue a webhook for async delivery."""
        if not self._queue:
            logger.warning("Queue not enabled, sending synchronously")
            self.send_sync(endpoint_name, payload, headers)
            return None
        
        message_id = self._queue.enqueue(
            endpoint_name,
            payload,
            headers,
            priority=priority,
            **kwargs,
        )
        
        if self._metrics:
            self._metrics.queue_size.set(self._queue.size())
        
        return message_id
    
    async def start_queue_processor(
        self,
        batch_size: Optional[int] = None,
        interval: Optional[float] = None,
        concurrency: int = 10,
    ) -> None:
        """Start the background queue processor."""
        if not self._queue:
            raise RuntimeError("Queue not enabled")
        
        await self._queue.start_processing(batch_size, interval, concurrency)
    
    def stop_queue_processor(self) -> None:
        """Stop the background queue processor."""
        if self._queue:
            self._queue.stop_processing()
    
    # Monitoring and events
    
    def on(self, event: str, callback: Callable) -> Callable:
        """Register an event listener."""
        return self._events.on(event, callback)
    
    def off(self, event: str, callback: Callable) -> bool:
        """Remove an event listener."""
        return self._events.off(event, callback)
    
    def health_check(self) -> HealthStatus:
        """Run health checks."""
        return self._health.check()
    
    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        if self._metrics:
            return self._metrics.registry.get_all()
        return {}
    
    def get_status(self) -> dict[str, Any]:
        """Get engine status."""
        status = {
            "endpoints": self.list_endpoints(),
            "health": self.health_check().to_dict(),
            "circuit_breakers": self._circuit_breakers.get_all_status(),
        }
        
        if self._queue:
            status["queue"] = self._queue.get_stats()
        
        if self._metrics:
            status["metrics"] = self.get_metrics()
        
        return status
    
    # Convenience methods for Power Automate
    
    async def send_to_power_automate(
        self,
        data: dict[str, Any],
        action: str = "trigger",
    ) -> DeliveryResult:
        """Send a webhook to Power Automate."""
        payload = PayloadFormatter.power_automate(data, action)
        return await self.send("power_automate", payload)
    
    def send_to_power_automate_sync(
        self,
        data: dict[str, Any],
        action: str = "trigger",
    ) -> DeliveryResult:
        """Send a webhook to Power Automate (synchronous)."""
        payload = PayloadFormatter.power_automate(data, action)
        return self.send_sync("power_automate", payload)
    
    # Lifecycle
    
    async def close(self) -> None:
        """Close the engine and release resources."""
        if self._client:
            await self._client.close()
        
        if self._queue:
            await self._queue.close()
        
        logger.info("Webhook engine closed")
    
    # Context manager
    
    async def __aenter__(self) -> WebhookEngine:
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Helper for optional context manager
class _NullContext:
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass


def _null_context():
    return _NullContext()


# Quick send functions
async def send_webhook(
    url: str,
    payload: dict[str, Any],
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> DeliveryResult:
    """Quick function to send a single webhook."""
    engine = WebhookEngine(enable_queue=False, enable_logging=False)
    engine.add_endpoint(WebhookEndpoint(
        name="adhoc",
        url=url,
        method=method,
        headers=headers or {},
        timeout=timeout,
    ))
    
    try:
        return await engine.send("adhoc", payload)
    finally:
        await engine.close()


def send_webhook_sync(
    url: str,
    payload: dict[str, Any],
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> DeliveryResult:
    """Quick function to send a single webhook synchronously."""
    engine = WebhookEngine(enable_queue=False, enable_logging=False)
    engine.add_endpoint(WebhookEndpoint(
        name="adhoc",
        url=url,
        method=method,
        headers=headers or {},
        timeout=timeout,
    ))
    
    try:
        return engine.send_sync("adhoc", payload)
    finally:
        asyncio.get_event_loop().run_until_complete(engine.close())


# Power Automate quick send
async def trigger_power_automate(
    data: dict[str, Any],
    action: str = "trigger",
) -> DeliveryResult:
    """Quick function to trigger Power Automate workflow."""
    engine = WebhookEngine(enable_queue=False)
    try:
        return await engine.send_to_power_automate(data, action)
    finally:
        await engine.close()


def trigger_power_automate_sync(
    data: dict[str, Any],
    action: str = "trigger",
) -> DeliveryResult:
    """Quick function to trigger Power Automate workflow (sync)."""
    engine = WebhookEngine(enable_queue=False, enable_logging=False)
    try:
        return engine.send_to_power_automate_sync(data, action)
    finally:
        asyncio.get_event_loop().run_until_complete(engine.close())
