"""Monitoring, metrics, and structured logging for the webhook engine."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


class LogFormat(Enum):
    """Log output formats."""
    
    JSON = "json"
    TEXT = "text"
    COMPACT = "compact"


@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    
    name: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)
    unit: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "unit": self.unit,
        }


class MetricType(Enum):
    """Types of metrics."""
    
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Counter:
    """A monotonically increasing counter."""
    
    name: str
    value: float = 0
    tags: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def inc(self, amount: float = 1) -> None:
        """Increment the counter."""
        with self._lock:
            self.value += amount
    
    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self.value
    
    def reset(self) -> float:
        """Reset and return previous value."""
        with self._lock:
            val = self.value
            self.value = 0
            return val


@dataclass
class Gauge:
    """A value that can go up or down."""
    
    name: str
    value: float = 0
    tags: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def set(self, value: float) -> None:
        """Set the gauge value."""
        with self._lock:
            self.value = value
    
    def inc(self, amount: float = 1) -> None:
        """Increment the gauge."""
        with self._lock:
            self.value += amount
    
    def dec(self, amount: float = 1) -> None:
        """Decrement the gauge."""
        with self._lock:
            self.value -= amount
    
    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self.value


@dataclass
class Histogram:
    """Tracks value distributions."""
    
    name: str
    buckets: list[float] = field(default_factory=lambda: [
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10
    ])
    tags: dict[str, str] = field(default_factory=dict)
    _counts: dict[float, int] = field(default_factory=dict, repr=False)
    _sum: float = 0
    _count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize bucket counts."""
        self._counts = {b: 0 for b in sorted(self.buckets)}
        self._counts[float("inf")] = 0
    
    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            self._sum += value
            self._count += 1
            
            for bucket in sorted(self._counts.keys()):
                if value <= bucket:
                    self._counts[bucket] += 1
    
    def get_stats(self) -> dict[str, Any]:
        """Get histogram statistics."""
        with self._lock:
            return {
                "count": self._count,
                "sum": self._sum,
                "mean": self._sum / self._count if self._count > 0 else 0,
                "buckets": dict(self._counts),
            }


@dataclass
class Timer:
    """Times operations and tracks as histogram."""
    
    name: str
    histogram: Histogram = field(default=None)  # type: ignore
    tags: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Initialize histogram."""
        if self.histogram is None:
            self.histogram = Histogram(
                name=f"{self.name}_seconds",
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
                tags=self.tags,
            )
    
    def time(self) -> TimerContext:
        """Context manager for timing."""
        return TimerContext(self)
    
    def observe(self, seconds: float) -> None:
        """Record a duration."""
        self.histogram.observe(seconds)
    
    def get_stats(self) -> dict[str, Any]:
        """Get timer statistics."""
        return self.histogram.get_stats()


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, timer: Timer):
        self.timer = timer
        self.start_time: float = 0
    
    def __enter__(self) -> TimerContext:
        """Start timing."""
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Stop timing and record."""
        elapsed = time.perf_counter() - self.start_time
        self.timer.observe(elapsed)
    
    async def __aenter__(self) -> TimerContext:
        """Async start timing."""
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Async stop timing and record."""
        elapsed = time.perf_counter() - self.start_time
        self.timer.observe(elapsed)


class MetricsRegistry:
    """Registry for all metrics."""
    
    def __init__(self, prefix: str = "webhook"):
        self.prefix = prefix
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._timers: dict[str, Timer] = {}
        self._lock = threading.RLock()
    
    def _make_name(self, name: str) -> str:
        """Create full metric name."""
        return f"{self.prefix}_{name}" if self.prefix else name
    
    def counter(
        self,
        name: str,
        tags: Optional[dict[str, str]] = None,
    ) -> Counter:
        """Get or create a counter."""
        full_name = self._make_name(name)
        key = f"{full_name}:{json.dumps(tags or {}, sort_keys=True)}"
        
        with self._lock:
            if key not in self._counters:
                self._counters[key] = Counter(name=full_name, tags=tags or {})
            return self._counters[key]
    
    def gauge(
        self,
        name: str,
        tags: Optional[dict[str, str]] = None,
    ) -> Gauge:
        """Get or create a gauge."""
        full_name = self._make_name(name)
        key = f"{full_name}:{json.dumps(tags or {}, sort_keys=True)}"
        
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = Gauge(name=full_name, tags=tags or {})
            return self._gauges[key]
    
    def histogram(
        self,
        name: str,
        buckets: Optional[list[float]] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> Histogram:
        """Get or create a histogram."""
        full_name = self._make_name(name)
        key = f"{full_name}:{json.dumps(tags or {}, sort_keys=True)}"
        
        with self._lock:
            if key not in self._histograms:
                kwargs: dict[str, Any] = {"name": full_name, "tags": tags or {}}
                if buckets:
                    kwargs["buckets"] = buckets
                self._histograms[key] = Histogram(**kwargs)
            return self._histograms[key]
    
    def timer(
        self,
        name: str,
        tags: Optional[dict[str, str]] = None,
    ) -> Timer:
        """Get or create a timer."""
        full_name = self._make_name(name)
        key = f"{full_name}:{json.dumps(tags or {}, sort_keys=True)}"
        
        with self._lock:
            if key not in self._timers:
                self._timers[key] = Timer(name=full_name, tags=tags or {})
            return self._timers[key]
    
    def get_all(self) -> dict[str, Any]:
        """Get all metrics."""
        with self._lock:
            return {
                "counters": {k: v.get() for k, v in self._counters.items()},
                "gauges": {k: v.get() for k, v in self._gauges.items()},
                "histograms": {k: v.get_stats() for k, v in self._histograms.items()},
                "timers": {k: v.get_stats() for k, v in self._timers.items()},
            }
    
    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()


# Global metrics registry
_metrics: Optional[MetricsRegistry] = None


def get_metrics() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsRegistry()
    return _metrics


# Pre-defined metrics
class WebhookMetrics:
    """Pre-defined webhook metrics."""
    
    def __init__(self, registry: Optional[MetricsRegistry] = None):
        self.registry = registry or get_metrics()
    
    @property
    def requests_total(self) -> Counter:
        """Total webhook requests."""
        return self.registry.counter("requests_total")
    
    @property
    def requests_success(self) -> Counter:
        """Successful webhook requests."""
        return self.registry.counter("requests_success")
    
    @property
    def requests_failed(self) -> Counter:
        """Failed webhook requests."""
        return self.registry.counter("requests_failed")
    
    @property
    def requests_retried(self) -> Counter:
        """Retried webhook requests."""
        return self.registry.counter("requests_retried")
    
    @property
    def queue_size(self) -> Gauge:
        """Current queue size."""
        return self.registry.gauge("queue_size")
    
    @property
    def dlq_size(self) -> Gauge:
        """Dead letter queue size."""
        return self.registry.gauge("dlq_size")
    
    @property
    def request_duration(self) -> Timer:
        """Request duration timer."""
        return self.registry.timer("request_duration")
    
    def request_by_endpoint(self, endpoint: str) -> Counter:
        """Requests counter by endpoint."""
        return self.registry.counter("requests_by_endpoint", {"endpoint": endpoint})
    
    def errors_by_status(self, status_code: int) -> Counter:
        """Error counter by status code."""
        return self.registry.counter("errors_by_status", {"status": str(status_code)})
    
    def circuit_breaker_state(self, endpoint: str, state: str) -> Gauge:
        """Circuit breaker state gauge."""
        return self.registry.gauge("circuit_breaker", {"endpoint": endpoint, "state": state})


class JsonFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def __init__(
        self,
        include_timestamp: bool = True,
        include_level: bool = True,
        include_logger: bool = True,
        extra_fields: Optional[dict[str, Any]] = None,
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_level = include_level
        self.include_logger = include_logger
        self.extra_fields = extra_fields or {}
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        message: dict[str, Any] = {
            "message": record.getMessage(),
        }
        
        if self.include_timestamp:
            message["timestamp"] = datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat()
        
        if self.include_level:
            message["level"] = record.levelname
        
        if self.include_logger:
            message["logger"] = record.name
        
        # Add extra fields from record
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "asctime",
                ):
                    try:
                        json.dumps(value)  # Check if serializable
                        message[key] = value
                    except (TypeError, ValueError):
                        message[key] = str(value)
        
        # Add configured extra fields
        message.update(self.extra_fields)
        
        # Add exception info
        if record.exc_info:
            message["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(message)


class CompactFormatter(logging.Formatter):
    """Compact log formatter for development."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record compactly."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = record.levelname[0]  # First letter
        
        parts = [f"{timestamp} {level} {record.getMessage()}"]
        
        # Add key extras
        extras = []
        for key in ("endpoint", "message_id", "status_code", "elapsed_ms"):
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")
        
        if extras:
            parts.append(f"[{', '.join(extras)}]")
        
        return " ".join(parts)


def setup_logging(
    level: str = "INFO",
    format: LogFormat = LogFormat.JSON,
    log_file: Optional[str] = None,
    include_payload: bool = False,
    extra_fields: Optional[dict[str, Any]] = None,
) -> logging.Logger:
    """Set up logging for the webhook engine."""
    logger = logging.getLogger("webhook_engine")
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()
    
    # Create formatter
    if format == LogFormat.JSON:
        formatter = JsonFormatter(extra_fields=extra_fields)
    elif format == LogFormat.COMPACT:
        formatter = CompactFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


class EventEmitter:
    """Simple event emitter for webhook events."""
    
    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def on(self, event: str, callback: Callable) -> Callable:
        """Register an event listener."""
        with self._lock:
            self._listeners[event].append(callback)
        return callback
    
    def off(self, event: str, callback: Callable) -> bool:
        """Remove an event listener."""
        with self._lock:
            if callback in self._listeners[event]:
                self._listeners[event].remove(callback)
                return True
            return False
    
    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all listeners."""
        with self._lock:
            listeners = list(self._listeners[event])
        
        for listener in listeners:
            try:
                listener(*args, **kwargs)
            except Exception as e:
                logging.error(f"Error in event listener for '{event}': {e}")
    
    async def emit_async(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all listeners (async)."""
        with self._lock:
            listeners = list(self._listeners[event])
        
        for listener in listeners:
            try:
                result = listener(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logging.error(f"Error in async event listener for '{event}': {e}")


# Webhook events
class WebhookEvents:
    """Standard webhook event names."""
    
    REQUEST_START = "request.start"
    REQUEST_SUCCESS = "request.success"
    REQUEST_FAILURE = "request.failure"
    REQUEST_RETRY = "request.retry"
    
    QUEUE_ENQUEUE = "queue.enqueue"
    QUEUE_DEQUEUE = "queue.dequeue"
    QUEUE_DLQ = "queue.dlq"
    
    CIRCUIT_OPEN = "circuit.open"
    CIRCUIT_CLOSE = "circuit.close"
    CIRCUIT_HALF_OPEN = "circuit.half_open"


# Health check
@dataclass
class HealthStatus:
    """Health check status."""
    
    healthy: bool
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "healthy": self.healthy,
            "checks": self.checks,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Health checker for the webhook engine."""
    
    def __init__(self):
        self._checks: dict[str, Callable[[], bool]] = {}
    
    def register(self, name: str, check: Callable[[], bool]) -> None:
        """Register a health check."""
        self._checks[name] = check
    
    def check(self) -> HealthStatus:
        """Run all health checks."""
        checks = {}
        details = {}
        
        for name, check_fn in self._checks.items():
            try:
                result = check_fn()
                checks[name] = result
            except Exception as e:
                checks[name] = False
                details[name] = {"error": str(e)}
        
        return HealthStatus(
            healthy=all(checks.values()),
            checks=checks,
            details=details,
        )


# Export collector for external systems
class MetricsExporter(ABC):
    """Abstract base class for metrics exporters."""
    
    @abstractmethod
    def export(self, registry: MetricsRegistry) -> str:
        """Export metrics in target format."""
        pass


class PrometheusExporter(MetricsExporter):
    """Export metrics in Prometheus format."""
    
    def export(self, registry: MetricsRegistry) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        metrics = registry.get_all()
        
        # Counters
        for key, value in metrics.get("counters", {}).items():
            name = key.split(":")[0]
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        # Gauges
        for key, value in metrics.get("gauges", {}).items():
            name = key.split(":")[0]
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        
        # Histograms
        for key, stats in metrics.get("histograms", {}).items():
            name = key.split(":")[0]
            lines.append(f"# TYPE {name} histogram")
            for bucket, count in stats.get("buckets", {}).items():
                le = "+Inf" if bucket == float("inf") else bucket
                lines.append(f'{name}_bucket{{le="{le}"}} {count}')
            lines.append(f"{name}_sum {stats.get('sum', 0)}")
            lines.append(f"{name}_count {stats.get('count', 0)}")
        
        return "\n".join(lines)


class JsonExporter(MetricsExporter):
    """Export metrics as JSON."""
    
    def export(self, registry: MetricsRegistry) -> str:
        """Export metrics as JSON."""
        return json.dumps(registry.get_all(), indent=2, default=str)
