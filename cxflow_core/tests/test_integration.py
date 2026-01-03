"""Tests for CXFlow core integration."""

import asyncio
import pytest

from cxflow_core import (
    CXFlowConfig,
    ServiceRegistry,
    ServiceStatus,
    EventBus,
    Event,
    EventPriority,
    HealthMonitor,
)


def test_config():
    """Test configuration."""
    config = CXFlowConfig()
    assert config.ml_service.name == "ml"
    assert config.gateway_enabled is True


def test_service_registry():
    """Test service registry."""
    registry = ServiceRegistry()
    
    # Register service
    info = registry.register("test", "http://localhost:8000")
    assert info.name == "test"
    assert info.url == "http://localhost:8000"
    
    # Get service
    service = registry.get("test")
    assert service is not None
    assert service.name == "test"
    
    # Update status
    registry.update_status("test", ServiceStatus.HEALTHY)
    assert registry.get("test").status == ServiceStatus.HEALTHY
    
    # List services
    services = registry.list_services()
    assert len(services) == 1
    
    # Unregister
    assert registry.unregister("test") is True
    assert registry.get("test") is None


def test_event_bus():
    """Test event bus."""
    bus = EventBus()
    
    # Track received events
    received = []
    
    def handler(event: Event):
        received.append(event)
    
    # Subscribe
    bus.subscribe("test.event", handler)
    
    # Publish
    event = Event(type="test.event", payload={"data": "test"})
    count = bus.publish_sync(event)
    
    assert count == 1
    assert len(received) == 1
    assert received[0].type == "test.event"
    
    # Test history
    history = bus.get_history()
    assert len(history) == 1


@pytest.mark.asyncio
async def test_event_bus_async():
    """Test async event bus."""
    bus = EventBus()
    
    received = []
    
    async def async_handler(event: Event):
        received.append(event)
    
    bus.subscribe("async.event", async_handler)
    
    event = Event(type="async.event", payload={"data": "test"})
    count = await bus.publish(event)
    
    assert count == 1
    assert len(received) == 1


def test_event_wildcards():
    """Test event wildcard subscriptions."""
    bus = EventBus()
    
    received = []
    
    def handler(event: Event):
        received.append(event)
    
    # Subscribe to wildcard
    bus.subscribe("ml.*", handler)
    
    # Publish matching event
    bus.publish_sync(Event(type="ml.train", payload={}))
    assert len(received) == 1
    
    # Publish non-matching event
    bus.publish_sync(Event(type="webhook.send", payload={}))
    assert len(received) == 1


@pytest.mark.asyncio
async def test_health_monitor():
    """Test health monitor (mock)."""
    config = CXFlowConfig()
    registry = ServiceRegistry()
    
    # Register a mock service
    registry.register("test", "http://localhost:9999")
    
    monitor = HealthMonitor(config, registry, check_interval=1)
    
    # Check service (will fail since it doesn't exist)
    result = await monitor.check_service(config.ml_service)
    assert result.service == "ml"
    # Service won't be healthy since it's not actually running


def test_event_priority():
    """Test event priorities."""
    event1 = Event(type="test", payload={}, priority=EventPriority.LOW)
    event2 = Event(type="test", payload={}, priority=EventPriority.HIGH)
    event3 = Event(type="test", payload={}, priority=EventPriority.CRITICAL)
    
    assert event1.priority == EventPriority.LOW
    assert event2.priority == EventPriority.HIGH
    assert event3.priority == EventPriority.CRITICAL


def test_service_discovery():
    """Test service discovery."""
    registry = ServiceRegistry()
    
    # Register multiple services
    registry.register("ml", "http://ml:8000")
    registry.register("webhook", "http://webhook:8001")
    
    # Find service
    url = registry.find_service("ml")
    assert url is None  # Not healthy yet
    
    # Update status
    registry.update_status("ml", ServiceStatus.HEALTHY)
    
    # Now should find it
    url = registry.find_service("ml")
    assert url == "http://ml:8000"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
