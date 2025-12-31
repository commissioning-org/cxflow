"""Retry logic with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

from .client import WebhookResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(ABC):
    """Abstract base class for retry strategies."""
    
    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Get delay in seconds before the next retry attempt."""
        pass
    
    @abstractmethod
    def should_retry(
        self,
        attempt: int,
        response: Optional[WebhookResponse] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """Determine if a retry should be attempted."""
        pass


@dataclass
class ExponentialBackoff(RetryStrategy):
    """Exponential backoff with optional jitter."""
    
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_exception: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def should_retry(
        self,
        attempt: int,
        response: Optional[WebhookResponse] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """Check if retry is warranted."""
        if attempt >= self.max_attempts:
            return False
        
        if exception is not None:
            return self.retry_on_exception
        
        if response is not None:
            return response.status_code in self.retry_on_status
        
        return False


@dataclass
class LinearBackoff(RetryStrategy):
    """Linear backoff strategy."""
    
    max_attempts: int = 3
    delay: float = 1.0
    delay_increment: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_exception: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Calculate linear delay."""
        delay = self.delay + (self.delay_increment * (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            delay += random.uniform(0, delay * 0.1)
        
        return max(0, delay)
    
    def should_retry(
        self,
        attempt: int,
        response: Optional[WebhookResponse] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """Check if retry is warranted."""
        if attempt >= self.max_attempts:
            return False
        
        if exception is not None:
            return self.retry_on_exception
        
        if response is not None:
            return response.status_code in self.retry_on_status
        
        return False


@dataclass
class ConstantBackoff(RetryStrategy):
    """Constant delay between retries."""
    
    max_attempts: int = 3
    delay: float = 1.0
    jitter: bool = False
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_exception: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Return constant delay."""
        delay = self.delay
        if self.jitter:
            delay += random.uniform(0, delay * 0.1)
        return delay
    
    def should_retry(
        self,
        attempt: int,
        response: Optional[WebhookResponse] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """Check if retry is warranted."""
        if attempt >= self.max_attempts:
            return False
        
        if exception is not None:
            return self.retry_on_exception
        
        if response is not None:
            return response.status_code in self.retry_on_status
        
        return False


@dataclass
class DecorrelatedJitter(RetryStrategy):
    """AWS-style decorrelated jitter backoff."""
    
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_exception: bool = True
    
    _prev_delay: float = 0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate decorrelated jitter delay."""
        if attempt == 1:
            self._prev_delay = self.base_delay
        else:
            self._prev_delay = random.uniform(
                self.base_delay,
                self._prev_delay * 3
            )
        return min(self._prev_delay, self.max_delay)
    
    def should_retry(
        self,
        attempt: int,
        response: Optional[WebhookResponse] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """Check if retry is warranted."""
        if attempt >= self.max_attempts:
            return False
        
        if exception is not None:
            return self.retry_on_exception
        
        if response is not None:
            return response.status_code in self.retry_on_status
        
        return False


class RetryPolicy:
    """Policy wrapper that manages retry execution."""
    
    def __init__(
        self,
        strategy: Optional[RetryStrategy] = None,
        on_retry: Optional[Callable[[int, float, Optional[Exception]], None]] = None,
    ):
        self.strategy = strategy or ExponentialBackoff()
        self.on_retry = on_retry
    
    async def execute_async(
        self,
        func: Callable[[], T],
        is_async: bool = True,
    ) -> T:
        """Execute a function with retry logic."""
        attempt = 0
        last_exception: Optional[Exception] = None
        last_response: Optional[WebhookResponse] = None
        
        while True:
            attempt += 1
            try:
                if is_async:
                    result = await func()  # type: ignore
                else:
                    result = func()
                
                # Check if result is a WebhookResponse
                if isinstance(result, WebhookResponse):
                    if result.success:
                        result.retry_count = attempt - 1
                        return result  # type: ignore
                    
                    last_response = result
                    if not self.strategy.should_retry(attempt, response=result):
                        result.retry_count = attempt - 1
                        return result  # type: ignore
                else:
                    return result
                
            except Exception as e:
                last_exception = e
                if not self.strategy.should_retry(attempt, exception=e):
                    raise
            
            # Calculate delay and wait
            delay = self.strategy.get_delay(attempt)
            
            logger.info(
                f"Retry attempt {attempt}/{self.strategy.max_attempts}, "
                f"waiting {delay:.2f}s",
                extra={
                    "attempt": attempt,
                    "delay": delay,
                    "exception": str(last_exception) if last_exception else None,
                    "status_code": last_response.status_code if last_response else None,
                }
            )
            
            if self.on_retry:
                self.on_retry(attempt, delay, last_exception)
            
            if is_async:
                await asyncio.sleep(delay)
            else:
                time.sleep(delay)
        
        # Should never reach here, but for type safety
        raise RuntimeError("Retry loop exited unexpectedly")
    
    def execute_sync(self, func: Callable[[], T]) -> T:
        """Execute a function with retry logic (synchronous)."""
        attempt = 0
        last_exception: Optional[Exception] = None
        last_response: Optional[WebhookResponse] = None
        
        while True:
            attempt += 1
            try:
                result = func()
                
                if isinstance(result, WebhookResponse):
                    if result.success:
                        result.retry_count = attempt - 1
                        return result  # type: ignore
                    
                    last_response = result
                    if not self.strategy.should_retry(attempt, response=result):
                        result.retry_count = attempt - 1
                        return result  # type: ignore
                else:
                    return result
                
            except Exception as e:
                last_exception = e
                if not self.strategy.should_retry(attempt, exception=e):
                    raise
            
            delay = self.strategy.get_delay(attempt)
            
            logger.info(
                f"Retry attempt {attempt}/{self.strategy.max_attempts}, "
                f"waiting {delay:.2f}s"
            )
            
            if self.on_retry:
                self.on_retry(attempt, delay, last_exception)
            
            time.sleep(delay)


def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> Callable:
    """Decorator to add retry logic to async functions."""
    
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            strategy = ExponentialBackoff(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
            )
            policy = RetryPolicy(strategy)
            return await policy.execute_async(
                lambda: func(*args, **kwargs),
                is_async=True,
            )
        return wrapper
    return decorator
