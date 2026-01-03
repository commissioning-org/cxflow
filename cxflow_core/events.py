"""Event bus for cross-service communication."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventPriority(str, Enum):
    """Event priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Event:
    """Event message."""
    
    type: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    source: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: EventPriority = EventPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """
    Event bus for pub/sub communication between services.
    
    Supports:
    - Topic-based subscription
    - Event filtering
    - Async event handlers
    - Priority handling
    - Event history
    """
    
    def __init__(self, max_history: int = 1000):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[Event] = []
        self._max_history = max_history
        self._running = False
    
    def subscribe(self, topic: str, handler: Callable) -> None:
        """
        Subscribe to a topic.
        
        Args:
            topic: Topic name (supports wildcards with *)
            handler: Callback function (can be sync or async)
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        logger.info(f"Subscribed to topic: {topic}")
    
    def unsubscribe(self, topic: str, handler: Callable) -> bool:
        """
        Unsubscribe from a topic.
        
        Args:
            topic: Topic name
            handler: Handler to remove
            
        Returns:
            True if unsubscribed, False if not found
        """
        if topic in self._subscribers:
            try:
                self._subscribers[topic].remove(handler)
                logger.info(f"Unsubscribed from topic: {topic}")
                return True
            except ValueError:
                pass
        return False
    
    async def publish(self, event: Event) -> int:
        """
        Publish an event.
        
        Args:
            event: Event to publish
            
        Returns:
            Number of handlers notified
        """
        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Find matching subscribers
        handlers = self._find_handlers(event.type)
        
        if not handlers:
            logger.debug(f"No subscribers for event: {event.type}")
            return 0
        
        # Notify handlers
        notified = 0
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
                notified += 1
            except Exception as e:
                logger.error(f"Event handler error for {event.type}: {e}")
        
        logger.debug(f"Published event {event.type} to {notified} handlers")
        return notified
    
    def publish_sync(self, event: Event) -> int:
        """
        Publish an event synchronously.
        
        Args:
            event: Event to publish
            
        Returns:
            Number of handlers notified
        """
        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Find matching subscribers
        handlers = self._find_handlers(event.type)
        
        if not handlers:
            logger.debug(f"No subscribers for event: {event.type}")
            return 0
        
        # Notify handlers (sync only)
        notified = 0
        for handler in handlers:
            if not asyncio.iscoroutinefunction(handler):
                try:
                    handler(event)
                    notified += 1
                except Exception as e:
                    logger.error(f"Event handler error for {event.type}: {e}")
        
        return notified
    
    def _find_handlers(self, event_type: str) -> list[Callable]:
        """Find handlers matching an event type."""
        handlers = []
        
        for topic, topic_handlers in self._subscribers.items():
            if self._match_topic(topic, event_type):
                handlers.extend(topic_handlers)
        
        return handlers
    
    def _match_topic(self, pattern: str, topic: str) -> bool:
        """
        Match a topic pattern against a topic.
        
        Supports wildcards:
        - * matches any single segment
        - ** matches any number of segments
        """
        if pattern == topic:
            return True
        
        if "*" not in pattern:
            return False
        
        # Simple wildcard matching
        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")
        
        if "**" in pattern:
            # Multi-segment wildcard
            return True
        
        if len(pattern_parts) != len(topic_parts):
            return False
        
        for p, t in zip(pattern_parts, topic_parts):
            if p != "*" and p != t:
                return False
        
        return True
    
    def get_history(self, topic: str | None = None, limit: int = 100) -> list[Event]:
        """
        Get event history.
        
        Args:
            topic: Optional topic filter
            limit: Maximum number of events to return
            
        Returns:
            List of events (newest first)
        """
        events = self._history[::-1]
        
        if topic:
            events = [e for e in events if self._match_topic(topic, e.type)]
        
        return events[:limit]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
    
    def get_topics(self) -> list[str]:
        """Get all subscribed topics."""
        return list(self._subscribers.keys())
    
    def get_subscriber_count(self, topic: str) -> int:
        """Get number of subscribers for a topic."""
        return len(self._subscribers.get(topic, []))
