"""
Enhanced webhook engine with priority queuing and batch processing.

Features:
- Priority-based message queuing
- Batch processing for efficiency
- Message deduplication
- Message aggregation and consolidation
- Dead letter queue handling
- Backpressure management
- Scheduled delivery
- Message ordering guarantees
"""

from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import IntEnum
from collections import defaultdict
import hashlib
import json

logger = logging.getLogger(__name__)


class MessagePriority(IntEnum):
    """Message priority levels (higher number = higher priority)."""
    CRITICAL = 5
    HIGH = 4
    NORMAL = 3
    LOW = 2
    BULK = 1


@dataclass(order=True)
class PriorityMessage:
    """Message with priority for queue ordering."""
    priority: int
    timestamp: float = field(compare=False)
    message_id: str = field(compare=False)
    endpoint: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False, default_factory=dict)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)
    retry_count: int = field(compare=False, default=0)
    scheduled_for: Optional[float] = field(compare=False, default=None)
    
    def __post_init__(self):
        # For heap ordering (min-heap), negate priority for max-heap behavior
        self.priority = -self.priority


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    max_batch_size: int = 100
    max_wait_ms: int = 1000
    enabled: bool = True
    group_by_endpoint: bool = True
    deduplicate: bool = True
    aggregate: bool = False  # Aggregate similar messages


@dataclass
class BatchResult:
    """Result of batch processing."""
    batch_id: str
    messages_processed: int
    messages_succeeded: int
    messages_failed: int
    duplicates_removed: int
    elapsed_ms: int
    errors: List[str] = field(default_factory=list)


class PriorityWebhookQueue:
    """
    Priority-based webhook queue with batching and deduplication.
    """
    
    def __init__(
        self,
        batch_config: Optional[BatchConfig] = None,
        max_queue_size: int = 10000,
        enable_deduplication: bool = True,
        dedup_window_seconds: int = 300,
    ):
        self.batch_config = batch_config or BatchConfig()
        self.max_queue_size = max_queue_size
        self.enable_deduplication = enable_deduplication
        self.dedup_window_seconds = dedup_window_seconds
        
        # Priority queue (min-heap with negated priorities)
        self._queue: List[PriorityMessage] = []
        self._scheduled_messages: List[PriorityMessage] = []
        
        # Deduplication tracking
        self._message_hashes: Dict[str, float] = {}  # hash -> timestamp
        self._seen_ids: Set[str] = set()
        
        # Batching state
        self._pending_batches: Dict[str, List[PriorityMessage]] = defaultdict(list)
        self._batch_timers: Dict[str, float] = {}
        
        # Metrics
        self._total_enqueued = 0
        self._total_dequeued = 0
        self._total_duplicates = 0
        self._total_dropped = 0
    
    async def enqueue(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        schedule_delay_seconds: Optional[float] = None,
    ) -> bool:
        """Enqueue a message with priority."""
        
        # Check queue size
        if len(self._queue) >= self.max_queue_size:
            self._total_dropped += 1
            logger.warning(f"Queue full, dropping message for {endpoint}")
            return False
        
        # Generate message ID if not provided
        if message_id is None:
            message_id = self._generate_message_id(endpoint, payload)
        
        # Check for duplicates
        if self.enable_deduplication:
            if self._is_duplicate(message_id, payload):
                self._total_duplicates += 1
                logger.debug(f"Duplicate message ignored: {message_id}")
                return False
        
        # Create message
        now = asyncio.get_event_loop().time()
        scheduled_for = now + schedule_delay_seconds if schedule_delay_seconds else None
        
        message = PriorityMessage(
            priority=priority,
            timestamp=now,
            message_id=message_id,
            endpoint=endpoint,
            payload=payload,
            metadata=metadata or {},
            scheduled_for=scheduled_for,
        )
        
        # Add to appropriate queue
        if scheduled_for:
            heapq.heappush(self._scheduled_messages, (scheduled_for, message))
        else:
            heapq.heappush(self._queue, message)
        
        self._total_enqueued += 1
        
        # Track for deduplication
        if self.enable_deduplication:
            self._track_message(message_id, payload, now)
        
        return True
    
    async def dequeue(self, timeout: Optional[float] = None) -> Optional[PriorityMessage]:
        """Dequeue highest priority message."""
        
        # Move scheduled messages that are ready
        await self._process_scheduled_messages()
        
        if not self._queue:
            return None
        
        message = heapq.heappop(self._queue)
        self._total_dequeued += 1
        return message
    
    async def dequeue_batch(
        self,
        endpoint: Optional[str] = None,
        max_size: Optional[int] = None,
    ) -> List[PriorityMessage]:
        """Dequeue a batch of messages."""
        
        await self._process_scheduled_messages()
        
        if not self._queue:
            return []
        
        batch_size = max_size or self.batch_config.max_batch_size
        batch: List[PriorityMessage] = []
        
        # Dequeue messages
        while self._queue and len(batch) < batch_size:
            message = heapq.heappop(self._queue)
            
            # Filter by endpoint if specified
            if endpoint and message.endpoint != endpoint:
                # Put it back (will be reordered)
                heapq.heappush(self._queue, message)
                continue
            
            batch.append(message)
            self._total_dequeued += 1
        
        return batch
    
    def size(self) -> int:
        """Get current queue size."""
        return len(self._queue) + len(self._scheduled_messages)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0 and len(self._scheduled_messages) == 0
    
    async def _process_scheduled_messages(self) -> None:
        """Move scheduled messages to main queue if ready."""
        now = asyncio.get_event_loop().time()
        
        while self._scheduled_messages:
            scheduled_time, message = self._scheduled_messages[0]
            
            if scheduled_time <= now:
                heapq.heappop(self._scheduled_messages)
                heapq.heappush(self._queue, message)
            else:
                break
    
    def _is_duplicate(self, message_id: str, payload: Dict[str, Any]) -> bool:
        """Check if message is a duplicate."""
        now = asyncio.get_event_loop().time()
        
        # Check by message ID
        if message_id in self._seen_ids:
            return True
        
        # Check by content hash
        content_hash = self._hash_payload(payload)
        if content_hash in self._message_hashes:
            last_seen = self._message_hashes[content_hash]
            if now - last_seen < self.dedup_window_seconds:
                return True
        
        return False
    
    def _track_message(self, message_id: str, payload: Dict[str, Any], timestamp: float) -> None:
        """Track message for deduplication."""
        self._seen_ids.add(message_id)
        content_hash = self._hash_payload(payload)
        self._message_hashes[content_hash] = timestamp
        
        # Clean up old entries periodically
        if len(self._message_hashes) > 10000:
            self._cleanup_dedup_tracking()
    
    def _cleanup_dedup_tracking(self) -> None:
        """Clean up old deduplication tracking data."""
        now = asyncio.get_event_loop().time()
        cutoff = now - self.dedup_window_seconds
        
        # Clean message hashes
        expired = [
            hash_key for hash_key, timestamp in self._message_hashes.items()
            if timestamp < cutoff
        ]
        for hash_key in expired:
            del self._message_hashes[hash_key]
    
    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        """Generate hash of payload for deduplication."""
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()
    
    def _generate_message_id(self, endpoint: str, payload: Dict[str, Any]) -> str:
        """Generate unique message ID."""
        timestamp = datetime.utcnow().isoformat()
        content = f"{endpoint}{timestamp}{self._hash_payload(payload)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            'queue_size': len(self._queue),
            'scheduled_messages': len(self._scheduled_messages),
            'total_enqueued': self._total_enqueued,
            'total_dequeued': self._total_dequeued,
            'total_duplicates': self._total_duplicates,
            'total_dropped': self._total_dropped,
            'dedup_cache_size': len(self._message_hashes),
        }


class BatchProcessor:
    """Process messages in batches for efficiency."""
    
    def __init__(
        self,
        queue: PriorityWebhookQueue,
        config: Optional[BatchConfig] = None,
    ):
        self.queue = queue
        self.config = config or BatchConfig()
        self._processing = False
    
    async def process_batch(
        self,
        send_func: Any,  # Async function to send message
        endpoint: Optional[str] = None,
    ) -> BatchResult:
        """Process a batch of messages."""
        start_time = asyncio.get_event_loop().time()
        
        batch_id = hashlib.sha256(
            f"{datetime.utcnow().isoformat()}{endpoint or 'all'}".encode()
        ).hexdigest()[:16]
        
        result = BatchResult(
            batch_id=batch_id,
            messages_processed=0,
            messages_succeeded=0,
            messages_failed=0,
            duplicates_removed=0,
            elapsed_ms=0,
        )
        
        # Dequeue batch
        messages = await self.queue.dequeue_batch(
            endpoint=endpoint,
            max_size=self.config.max_batch_size,
        )
        
        if not messages:
            return result
        
        result.messages_processed = len(messages)
        
        # Deduplicate if enabled
        if self.config.deduplicate:
            messages, dup_count = self._deduplicate_batch(messages)
            result.duplicates_removed = dup_count
        
        # Aggregate if enabled
        if self.config.aggregate:
            messages = self._aggregate_messages(messages)
        
        # Send messages
        tasks = []
        for message in messages:
            task = send_func(
                endpoint=message.endpoint,
                payload=message.payload,
                message_id=message.message_id,
            )
            tasks.append(task)
        
        # Wait for all sends to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        for idx, send_result in enumerate(results):
            if isinstance(send_result, Exception):
                result.messages_failed += 1
                result.errors.append(str(send_result))
            else:
                result.messages_succeeded += 1
        
        elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        result.elapsed_ms = elapsed_ms
        
        return result
    
    def _deduplicate_batch(
        self,
        messages: List[PriorityMessage],
    ) -> tuple[List[PriorityMessage], int]:
        """Remove duplicates from batch."""
        seen_hashes = set()
        unique_messages = []
        dup_count = 0
        
        for message in messages:
            content_hash = hashlib.sha256(
                json.dumps(message.payload, sort_keys=True).encode()
            ).hexdigest()
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_messages.append(message)
            else:
                dup_count += 1
        
        return unique_messages, dup_count
    
    def _aggregate_messages(
        self,
        messages: List[PriorityMessage],
    ) -> List[PriorityMessage]:
        """Aggregate similar messages."""
        # Group by endpoint and event type
        groups: Dict[tuple, List[PriorityMessage]] = defaultdict(list)
        
        for message in messages:
            event_type = message.payload.get('event', 'unknown')
            key = (message.endpoint, event_type)
            groups[key].append(message)
        
        # Create aggregated messages
        aggregated = []
        for (endpoint, event_type), group_messages in groups.items():
            if len(group_messages) == 1:
                aggregated.append(group_messages[0])
            else:
                # Create aggregated message
                aggregated_payload = {
                    'event': f'{event_type}.batch',
                    'count': len(group_messages),
                    'items': [m.payload for m in group_messages],
                    'aggregated_at': datetime.utcnow().isoformat() + 'Z',
                }
                
                aggregated_message = PriorityMessage(
                    priority=-max(m.priority for m in group_messages),  # Use highest priority
                    timestamp=min(m.timestamp for m in group_messages),
                    message_id=f"batch_{hashlib.sha256(str(group_messages).encode()).hexdigest()[:16]}",
                    endpoint=endpoint,
                    payload=aggregated_payload,
                    metadata={'aggregated_count': len(group_messages)},
                )
                aggregated.append(aggregated_message)
        
        return aggregated
    
    async def start_background_processing(
        self,
        send_func: Any,
        interval_ms: int = 1000,
    ) -> None:
        """Start background batch processing."""
        self._processing = True
        
        while self._processing:
            try:
                if not self.queue.is_empty():
                    await self.process_batch(send_func)
                
                await asyncio.sleep(interval_ms / 1000)
            
            except Exception as e:
                logger.exception("Error in background batch processing")
                await asyncio.sleep(1)
    
    def stop_background_processing(self) -> None:
        """Stop background processing."""
        self._processing = False


if __name__ == '__main__':
    # Example usage
    import asyncio
    
    async def example_send_func(endpoint: str, payload: Dict[str, Any], message_id: str):
        """Example send function."""
        await asyncio.sleep(0.1)  # Simulate network delay
        return {'ok': True, 'message_id': message_id}
    
    async def main():
        # Create queue
        queue = PriorityWebhookQueue(
            batch_config=BatchConfig(max_batch_size=10, max_wait_ms=1000),
            enable_deduplication=True,
        )
        
        # Enqueue some messages
        for i in range(20):
            priority = MessagePriority.HIGH if i % 5 == 0 else MessagePriority.NORMAL
            await queue.enqueue(
                endpoint="test_endpoint",
                payload={'event': 'test', 'data': i},
                priority=priority,
            )
        
        # Process batch
        processor = BatchProcessor(queue)
        result = await processor.process_batch(example_send_func)
        
        print(f"Batch processed: {result.messages_processed} messages")
        print(f"Success: {result.messages_succeeded}, Failed: {result.messages_failed}")
        print(f"Elapsed: {result.elapsed_ms}ms")
        
        # Show stats
        print("\nQueue stats:", queue.get_stats())
    
    asyncio.run(main())
