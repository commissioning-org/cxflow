"""Queue and batch processing for webhook delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pickle
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .client import WebhookClient, WebhookResponse
from .config import WebhookConfig, WebhookEndpoint
from .circuit_breaker import CircuitBreaker, CircuitBreakerError
from .retry import RetryPolicy, ExponentialBackoff

logger = logging.getLogger(__name__)


class DeliveryStatus(Enum):
    """Status of a webhook delivery."""
    
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    EXPIRED = "expired"


@dataclass
class WebhookMessage:
    """A message in the webhook queue."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    status: DeliveryStatus = DeliveryStatus.PENDING
    last_error: Optional[str] = None
    last_response: Optional[dict[str, Any]] = None
    priority: int = 0  # Higher = more important
    correlation_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    def is_scheduled(self) -> bool:
        """Check if message is scheduled for future delivery."""
        if self.scheduled_at is None:
            return False
        return datetime.now(timezone.utc) < self.scheduled_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.attempts < self.max_attempts
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "endpoint_name": self.endpoint_name,
            "payload": self.payload,
            "headers": self.headers,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "status": self.status.value,
            "last_error": self.last_error,
            "last_response": self.last_response,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebhookMessage:
        """Create from dictionary."""
        msg = cls(
            id=data["id"],
            endpoint_name=data["endpoint_name"],
            payload=data["payload"],
            headers=data.get("headers", {}),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            status=DeliveryStatus(data.get("status", "pending")),
            last_error=data.get("last_error"),
            last_response=data.get("last_response"),
            priority=data.get("priority", 0),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )
        
        if data.get("created_at"):
            msg.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("scheduled_at"):
            msg.scheduled_at = datetime.fromisoformat(data["scheduled_at"])
        if data.get("expires_at"):
            msg.expires_at = datetime.fromisoformat(data["expires_at"])
        
        return msg


class QueueBackend(ABC):
    """Abstract backend for queue storage."""
    
    @abstractmethod
    def push(self, message: WebhookMessage) -> None:
        """Add a message to the queue."""
        pass
    
    @abstractmethod
    def pop(self, count: int = 1) -> list[WebhookMessage]:
        """Get and remove messages from the queue."""
        pass
    
    @abstractmethod
    def peek(self, count: int = 1) -> list[WebhookMessage]:
        """Get messages without removing them."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get queue size."""
        pass
    
    @abstractmethod
    def clear(self) -> int:
        """Clear all messages. Returns count cleared."""
        pass


class MemoryQueueBackend(QueueBackend):
    """In-memory queue backend with priority support."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: deque[WebhookMessage] = deque()
        self._lock = threading.RLock()
    
    def push(self, message: WebhookMessage) -> None:
        """Add message to queue with priority ordering."""
        with self._lock:
            if len(self._queue) >= self.max_size:
                # Remove oldest low-priority message
                self._queue.popleft()
            
            # Insert maintaining priority order (higher priority first)
            inserted = False
            for i, existing in enumerate(self._queue):
                if message.priority > existing.priority:
                    self._queue.insert(i, message)
                    inserted = True
                    break
            
            if not inserted:
                self._queue.append(message)
    
    def pop(self, count: int = 1) -> list[WebhookMessage]:
        """Pop messages from queue."""
        with self._lock:
            messages = []
            for _ in range(min(count, len(self._queue))):
                msg = self._queue.popleft()
                if not msg.is_expired() and not msg.is_scheduled():
                    messages.append(msg)
                elif msg.is_scheduled():
                    # Re-queue scheduled messages
                    self._queue.append(msg)
            return messages
    
    def peek(self, count: int = 1) -> list[WebhookMessage]:
        """Peek at messages."""
        with self._lock:
            return list(self._queue)[:count]
    
    def size(self) -> int:
        """Get queue size."""
        with self._lock:
            return len(self._queue)
    
    def clear(self) -> int:
        """Clear queue."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count


class FileQueueBackend(QueueBackend):
    """File-based persistent queue backend."""
    
    def __init__(self, path: str | Path, max_size: int = 10000):
        self.path = Path(path)
        self.max_size = max_size
        self._lock = threading.RLock()
        
        # Ensure directory exists
        self.path.mkdir(parents=True, exist_ok=True)
        self._queue_file = self.path / "queue.pkl"
        self._load()
    
    def _load(self) -> None:
        """Load queue from disk."""
        if self._queue_file.exists():
            try:
                with open(self._queue_file, "rb") as f:
                    self._messages: list[WebhookMessage] = pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load queue from disk: {e}")
                self._messages = []
        else:
            self._messages = []
    
    def _save(self) -> None:
        """Save queue to disk."""
        try:
            with open(self._queue_file, "wb") as f:
                pickle.dump(self._messages, f)
        except Exception as e:
            logger.error(f"Failed to save queue to disk: {e}")
    
    def push(self, message: WebhookMessage) -> None:
        """Add message to queue."""
        with self._lock:
            if len(self._messages) >= self.max_size:
                self._messages.pop(0)
            self._messages.append(message)
            self._save()
    
    def pop(self, count: int = 1) -> list[WebhookMessage]:
        """Pop messages from queue."""
        with self._lock:
            messages = []
            remaining = []
            
            for msg in self._messages:
                if len(messages) < count and not msg.is_expired() and not msg.is_scheduled():
                    messages.append(msg)
                else:
                    remaining.append(msg)
            
            self._messages = remaining
            self._save()
            return messages
    
    def peek(self, count: int = 1) -> list[WebhookMessage]:
        """Peek at messages."""
        with self._lock:
            return self._messages[:count]
    
    def size(self) -> int:
        """Get queue size."""
        with self._lock:
            return len(self._messages)
    
    def clear(self) -> int:
        """Clear queue."""
        with self._lock:
            count = len(self._messages)
            self._messages = []
            self._save()
            return count


class DeadLetterQueue:
    """Queue for failed messages that exceeded retry limits."""
    
    def __init__(
        self,
        max_size: int = 1000,
        persistence_path: Optional[str] = None,
    ):
        self.max_size = max_size
        self._messages: deque[WebhookMessage] = deque(maxlen=max_size)
        self._lock = threading.RLock()
        self._persistence_path = Path(persistence_path) if persistence_path else None
        
        if self._persistence_path:
            self._load()
    
    def _load(self) -> None:
        """Load from disk."""
        if self._persistence_path and self._persistence_path.exists():
            try:
                with open(self._persistence_path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        self._messages.append(WebhookMessage.from_dict(item))
            except Exception as e:
                logger.warning(f"Failed to load DLQ from disk: {e}")
    
    def _save(self) -> None:
        """Save to disk."""
        if self._persistence_path:
            try:
                self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._persistence_path, "w") as f:
                    json.dump([m.to_dict() for m in self._messages], f)
            except Exception as e:
                logger.error(f"Failed to save DLQ to disk: {e}")
    
    def add(self, message: WebhookMessage) -> None:
        """Add a message to the dead letter queue."""
        with self._lock:
            message.status = DeliveryStatus.DEAD_LETTERED
            self._messages.append(message)
            self._save()
            
            logger.warning(
                f"Message {message.id} moved to dead letter queue",
                extra={
                    "message_id": message.id,
                    "endpoint": message.endpoint_name,
                    "attempts": message.attempts,
                    "last_error": message.last_error,
                }
            )
    
    def get_all(self) -> list[WebhookMessage]:
        """Get all messages in the DLQ."""
        with self._lock:
            return list(self._messages)
    
    def retry(self, message_id: str) -> Optional[WebhookMessage]:
        """Remove a message from DLQ for retry."""
        with self._lock:
            for i, msg in enumerate(self._messages):
                if msg.id == message_id:
                    msg.status = DeliveryStatus.PENDING
                    msg.attempts = 0
                    del self._messages[i]
                    self._save()
                    return msg
            return None
    
    def retry_all(self) -> list[WebhookMessage]:
        """Remove all messages from DLQ for retry."""
        with self._lock:
            messages = list(self._messages)
            for msg in messages:
                msg.status = DeliveryStatus.PENDING
                msg.attempts = 0
            self._messages.clear()
            self._save()
            return messages
    
    def purge(self, older_than_days: Optional[int] = None) -> int:
        """Purge messages from DLQ."""
        with self._lock:
            if older_than_days is None:
                count = len(self._messages)
                self._messages.clear()
            else:
                cutoff = datetime.now(timezone.utc).timestamp() - (older_than_days * 86400)
                original = len(self._messages)
                self._messages = deque(
                    (m for m in self._messages if m.created_at.timestamp() > cutoff),
                    maxlen=self.max_size,
                )
                count = original - len(self._messages)
            
            self._save()
            return count
    
    def size(self) -> int:
        """Get DLQ size."""
        with self._lock:
            return len(self._messages)


class WebhookQueue:
    """Main webhook queue with processing capabilities."""
    
    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        backend: Optional[QueueBackend] = None,
        dead_letter_queue: Optional[DeadLetterQueue] = None,
    ):
        self.config = config or WebhookConfig()
        
        # Set up backend
        if backend:
            self._backend = backend
        elif self.config.queue.persistence_path:
            self._backend = FileQueueBackend(
                self.config.queue.persistence_path,
                self.config.queue.max_size,
            )
        else:
            self._backend = MemoryQueueBackend(self.config.queue.max_size)
        
        # Set up DLQ
        if dead_letter_queue:
            self._dlq = dead_letter_queue
        elif self.config.queue.dead_letter_enabled:
            dlq_path = None
            if self.config.queue.persistence_path:
                dlq_path = str(Path(self.config.queue.persistence_path) / "dlq.json")
            self._dlq = DeadLetterQueue(
                max_size=self.config.queue.dead_letter_max_size,
                persistence_path=dlq_path,
            )
        else:
            self._dlq = None
        
        self._client: Optional[WebhookClient] = None
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._processing = False
        self._stop_event = threading.Event()
    
    @property
    def dlq(self) -> Optional[DeadLetterQueue]:
        """Get the dead letter queue."""
        return self._dlq
    
    def _get_client(self) -> WebhookClient:
        """Get or create webhook client."""
        if self._client is None:
            self._client = WebhookClient(
                timeout=self.config.default_timeout,
                verify_ssl=self.config.verify_ssl,
                connection_pool_size=self.config.connection_pool_size,
                default_headers=self.config.default_headers,
            )
        return self._client
    
    def _get_circuit_breaker(self, endpoint_name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker for endpoint."""
        endpoint = self.config.get_endpoint(endpoint_name)
        if not endpoint or not endpoint.circuit_breaker_enabled:
            return None
        
        if endpoint_name not in self._circuit_breakers:
            from .circuit_breaker import CircuitBreakerConfig as CBConfig
            self._circuit_breakers[endpoint_name] = CircuitBreaker(
                name=endpoint_name,
                config=CBConfig(
                    failure_threshold=self.config.circuit_breaker.failure_threshold,
                    success_threshold=self.config.circuit_breaker.success_threshold,
                    timeout=self.config.circuit_breaker.timeout,
                    half_open_max_calls=self.config.circuit_breaker.half_open_max_calls,
                ),
            )
        
        return self._circuit_breakers[endpoint_name]
    
    def enqueue(
        self,
        endpoint_name: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        max_attempts: Optional[int] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Enqueue a webhook message for delivery."""
        message = WebhookMessage(
            endpoint_name=endpoint_name,
            payload=payload,
            headers=headers or {},
            priority=priority,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            max_attempts=max_attempts or self.config.retry.max_attempts,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )
        
        self._backend.push(message)
        
        logger.debug(
            f"Enqueued message {message.id} for {endpoint_name}",
            extra={
                "message_id": message.id,
                "endpoint": endpoint_name,
                "priority": priority,
            }
        )
        
        return message.id
    
    async def process_one(self) -> Optional[WebhookResponse]:
        """Process a single message from the queue."""
        messages = self._backend.pop(1)
        if not messages:
            return None
        
        message = messages[0]
        endpoint = self.config.get_endpoint(message.endpoint_name)
        
        if not endpoint:
            logger.error(f"Endpoint '{message.endpoint_name}' not found")
            message.status = DeliveryStatus.FAILED
            message.last_error = f"Endpoint '{message.endpoint_name}' not found"
            if self._dlq:
                self._dlq.add(message)
            return None
        
        # Check circuit breaker
        cb = self._get_circuit_breaker(message.endpoint_name)
        if cb and not cb.allow_request():
            # Re-queue the message
            self._backend.push(message)
            logger.debug(f"Circuit open for {message.endpoint_name}, re-queued message")
            return None
        
        # Attempt delivery
        message.status = DeliveryStatus.IN_FLIGHT
        message.attempts += 1
        
        client = self._get_client()
        
        try:
            response = await client.send_async(
                endpoint,
                message.payload,
                message.headers or None,
            )
            
            # Record with circuit breaker
            if cb:
                cb.record_response(response)
            
            if response.success:
                message.status = DeliveryStatus.DELIVERED
                message.last_response = response.to_dict()
                
                logger.info(
                    f"Delivered message {message.id} to {endpoint.name}",
                    extra={
                        "message_id": message.id,
                        "endpoint": endpoint.name,
                        "status_code": response.status_code,
                        "elapsed_ms": response.elapsed_ms,
                    }
                )
                
                return response
            else:
                # Delivery failed
                message.last_error = f"HTTP {response.status_code}: {response.body[:200]}"
                message.last_response = response.to_dict()
                
                if message.can_retry() and response.is_retryable:
                    message.status = DeliveryStatus.PENDING
                    self._backend.push(message)
                    logger.warning(
                        f"Message {message.id} failed, will retry ({message.attempts}/{message.max_attempts})"
                    )
                else:
                    message.status = DeliveryStatus.FAILED
                    if self._dlq:
                        self._dlq.add(message)
                
                return response
                
        except CircuitBreakerError:
            # Re-queue
            message.status = DeliveryStatus.PENDING
            self._backend.push(message)
            return None
            
        except Exception as e:
            message.last_error = str(e)
            
            if cb:
                cb.record_failure()
            
            if message.can_retry():
                message.status = DeliveryStatus.PENDING
                self._backend.push(message)
                logger.warning(
                    f"Message {message.id} failed with exception, will retry: {e}"
                )
            else:
                message.status = DeliveryStatus.FAILED
                if self._dlq:
                    self._dlq.add(message)
            
            return None
    
    async def process_batch(
        self,
        batch_size: Optional[int] = None,
        concurrency: int = 10,
    ) -> list[WebhookResponse]:
        """Process a batch of messages concurrently."""
        batch_size = batch_size or self.config.queue.batch_size
        messages = self._backend.pop(batch_size)
        
        if not messages:
            return []
        
        # Re-queue messages first, then process
        # This ensures messages aren't lost if processing crashes
        for msg in messages:
            self._backend.push(msg)
        
        # Process with concurrency limit
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_with_semaphore() -> Optional[WebhookResponse]:
            async with semaphore:
                return await self.process_one()
        
        tasks = [process_with_semaphore() for _ in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [r for r in results if isinstance(r, WebhookResponse)]
    
    async def start_processing(
        self,
        batch_size: Optional[int] = None,
        interval: Optional[float] = None,
        concurrency: int = 10,
    ) -> None:
        """Start continuous queue processing."""
        batch_size = batch_size or self.config.queue.batch_size
        interval = interval or self.config.queue.flush_interval
        
        self._processing = True
        self._stop_event.clear()
        
        logger.info("Started webhook queue processing")
        
        while self._processing:
            try:
                if self._backend.size() > 0:
                    await self.process_batch(batch_size, concurrency)
                else:
                    await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
                await asyncio.sleep(1)
            
            if self._stop_event.is_set():
                break
    
    def stop_processing(self) -> None:
        """Stop queue processing."""
        self._processing = False
        self._stop_event.set()
        logger.info("Stopped webhook queue processing")
    
    def size(self) -> int:
        """Get queue size."""
        return self._backend.size()
    
    def clear(self) -> int:
        """Clear the queue."""
        return self._backend.clear()
    
    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            "queue_size": self._backend.size(),
            "dlq_size": self._dlq.size() if self._dlq else 0,
            "processing": self._processing,
            "circuit_breakers": {
                name: cb.get_status()
                for name, cb in self._circuit_breakers.items()
            },
        }
    
    async def close(self) -> None:
        """Close the queue and release resources."""
        self.stop_processing()
        if self._client:
            await self._client.close()


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(
        self,
        requests_per_second: float = 100.0,
        burst_size: int = 200,
    ):
        self.rate = requests_per_second
        self.burst_size = burst_size
        self._tokens = float(burst_size)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.burst_size, self._tokens + elapsed * self.rate)
        self._last_update = now
    
    def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, returning wait time if needed."""
        with self._lock:
            self._refill()
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            
            # Calculate wait time
            needed = tokens - self._tokens
            wait_time = needed / self.rate
            return wait_time
    
    async def acquire_async(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary."""
        wait_time = self.acquire(tokens)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        with self._lock:
            self._refill()
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
