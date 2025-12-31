"""Circuit breaker pattern for fault tolerance."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from .client import WebhookResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit tripped, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    times_opened: int = 0
    
    def record_success(self) -> None:
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.now(timezone.utc)
    
    def record_failure(self) -> None:
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = datetime.now(timezone.utc)
    
    def record_rejection(self) -> None:
        """Record a rejected request (circuit open)."""
        self.rejected_requests += 1
    
    def record_state_change(self, opened: bool = False) -> None:
        """Record state change."""
        self.last_state_change = datetime.now(timezone.utc)
        if opened:
            self.times_opened += 1
    
    def reset(self) -> None:
        """Reset statistics."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rejected_requests": self.rejected_requests,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "failure_rate": self.failure_rate,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None,
            "times_opened": self.times_opened,
        }


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes in half-open before closing
    timeout: float = 60.0  # Seconds in open state before half-open
    half_open_max_calls: int = 3  # Max concurrent calls in half-open
    failure_rate_threshold: Optional[float] = None  # Alternative: open if rate exceeds
    min_throughput: int = 10  # Minimum requests before rate calculation
    
    # Status code handling
    success_codes: tuple[int, ...] = (200, 201, 202, 204)
    failure_codes: tuple[int, ...] = (500, 502, 503, 504)
    ignore_codes: tuple[int, ...] = (400, 401, 403, 404)  # Don't count as failure


class CircuitBreakerError(Exception):
    """Raised when circuit is open."""
    
    def __init__(self, message: str, circuit_name: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.retry_after = retry_after


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[str, CircuitState, CircuitState], None]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change
        
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
        self._async_lock: Optional[asyncio.Lock] = None
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_state_transition()
            return self._state
    
    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self.state == CircuitState.HALF_OPEN
    
    def _check_state_transition(self) -> None:
        """Check if state should transition."""
        if self._state == CircuitState.OPEN:
            if self._opened_at is not None:
                elapsed = time.time() - self._opened_at
                if elapsed >= self.config.timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        if old_state == new_state:
            return
        
        self._state = new_state
        self._stats.record_state_change(opened=(new_state == CircuitState.OPEN))
        
        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            self._half_open_calls = 0
            self._stats.reset()
        
        logger.info(
            f"Circuit '{self.name}' transitioned: {old_state.value} -> {new_state.value}",
            extra={
                "circuit": self.name,
                "old_state": old_state.value,
                "new_state": new_state.value,
            }
        )
        
        if self.on_state_change:
            self.on_state_change(self.name, old_state, new_state)
    
    def _should_allow_request(self) -> bool:
        """Check if request should be allowed."""
        state = self.state  # Triggers state check
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            return False
        
        # Half-open: allow limited requests
        if self._half_open_calls < self.config.half_open_max_calls:
            self._half_open_calls += 1
            return True
        
        return False
    
    def _record_result(self, success: bool, status_code: Optional[int] = None) -> None:
        """Record the result of a request."""
        with self._lock:
            # Check if status code should be ignored
            if status_code is not None and status_code in self.config.ignore_codes:
                return
            
            if success:
                self._stats.record_success()
                
                if self._state == CircuitState.HALF_OPEN:
                    if self._stats.consecutive_successes >= self.config.success_threshold:
                        self._transition_to(CircuitState.CLOSED)
            else:
                self._stats.record_failure()
                
                if self._state == CircuitState.HALF_OPEN:
                    self._transition_to(CircuitState.OPEN)
                elif self._state == CircuitState.CLOSED:
                    should_open = False
                    
                    # Check consecutive failures
                    if self._stats.consecutive_failures >= self.config.failure_threshold:
                        should_open = True
                    
                    # Check failure rate
                    if (self.config.failure_rate_threshold is not None and
                        self._stats.total_requests >= self.config.min_throughput):
                        if self._stats.failure_rate >= self.config.failure_rate_threshold:
                            should_open = True
                    
                    if should_open:
                        self._transition_to(CircuitState.OPEN)
    
    def record_success(self, status_code: Optional[int] = None) -> None:
        """Record a successful call."""
        self._record_result(True, status_code)
    
    def record_failure(self, status_code: Optional[int] = None) -> None:
        """Record a failed call."""
        self._record_result(False, status_code)
    
    def record_response(self, response: WebhookResponse) -> None:
        """Record result from a WebhookResponse."""
        if response.status_code in self.config.success_codes:
            self.record_success(response.status_code)
        elif response.status_code in self.config.failure_codes:
            self.record_failure(response.status_code)
        # Ignore other status codes
    
    def allow_request(self) -> bool:
        """Check if a request should be allowed (and track half-open calls)."""
        with self._lock:
            if self._should_allow_request():
                return True
            self._stats.record_rejection()
            return False
    
    def execute_sync(self, func: Callable[[], T]) -> T:
        """Execute a function with circuit breaker protection (sync)."""
        with self._lock:
            if not self._should_allow_request():
                self._stats.record_rejection()
                retry_after = None
                if self._opened_at:
                    retry_after = max(0, self.config.timeout - (time.time() - self._opened_at))
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is open",
                    self.name,
                    retry_after,
                )
        
        try:
            result = func()
            
            if isinstance(result, WebhookResponse):
                self.record_response(result)
            else:
                self.record_success()
            
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    async def execute_async(self, func: Callable[[], T]) -> T:
        """Execute a function with circuit breaker protection (async)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        
        async with self._async_lock:
            if not self._should_allow_request():
                self._stats.record_rejection()
                retry_after = None
                if self._opened_at:
                    retry_after = max(0, self.config.timeout - (time.time() - self._opened_at))
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is open",
                    self.name,
                    retry_after,
                )
        
        try:
            result = await func()  # type: ignore
            
            if isinstance(result, WebhookResponse):
                self.record_response(result)
            else:
                self.record_success()
            
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def reset(self) -> None:
        """Force reset the circuit breaker to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
    
    def trip(self) -> None:
        """Force the circuit breaker to open state."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
    
    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        with self._lock:
            retry_after = None
            if self._state == CircuitState.OPEN and self._opened_at:
                retry_after = max(0, self.config.timeout - (time.time() - self._opened_at))
            
            return {
                "name": self.name,
                "state": self.state.value,
                "stats": self._stats.to_dict(),
                "retry_after": retry_after,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout,
                    "half_open_max_calls": self.config.half_open_max_calls,
                },
            }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def get(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker by name."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    config=config or self.default_config,
                )
            return self._breakers[name]
    
    def get_all(self) -> dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        with self._lock:
            return dict(self._breakers)
    
    def get_all_status(self) -> list[dict[str, Any]]:
        """Get status of all circuit breakers."""
        with self._lock:
            return [cb.get_status() for cb in self._breakers.values()]
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()
    
    def remove(self, name: str) -> bool:
        """Remove a circuit breaker."""
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False


# Global registry
_registry: Optional[CircuitBreakerRegistry] = None


def get_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get a circuit breaker from the global registry."""
    return get_registry().get(name)
