"""Tests for CxSpaceLLM integration."""

import asyncio
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch

from cxflow_core import (
    CXFlowConfig,
    ServiceRegistry,
    EventBus,
    CxSpaceLLMConnector,
)
from cxflow_core.workflows import create_orchestrator


def test_cxspacellm_config():
    """Test CxSpaceLLM configuration."""
    config = CXFlowConfig()
    
    # Check default config values
    assert hasattr(config, 'cxspacellm_enabled')
    assert hasattr(config, 'cxspacellm_model')
    assert hasattr(config, 'cxspacellm_base_url')
    assert hasattr(config, 'cxspacellm_timeout')
    
    # Default model should be CxSpaceLLM
    assert config.cxspacellm_model == "CxSpaceLLM"


def test_cxspacellm_connector_init():
    """Test CxSpaceLLM connector initialization."""
    config = CXFlowConfig()
    registry = ServiceRegistry()
    bus = EventBus()
    
    connector = CxSpaceLLMConnector(registry, bus, config)
    
    assert connector.service_name == "cxspacellm"
    assert connector.model == config.cxspacellm_model
    assert connector.timeout == config.cxspacellm_timeout
    assert connector.base_url == config.cxspacellm_base_url


def test_cxspacellm_connector_disabled():
    """Test CxSpaceLLM connector when disabled."""
    config = CXFlowConfig()
    config.cxspacellm_enabled = False
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    connector = CxSpaceLLMConnector(registry, bus, config)
    
    assert connector.enabled is False


@pytest.mark.asyncio
async def test_cxspacellm_connector_no_token():
    """Test CxSpaceLLM connector raises error without token."""
    config = CXFlowConfig()
    config.cxspacellm_token = ""
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    connector = CxSpaceLLMConnector(registry, bus, config)
    
    with pytest.raises(RuntimeError, match="token not configured"):
        await connector.call("test")


@pytest.mark.asyncio
async def test_cxspacellm_chat_completion_mock():
    """Test CxSpaceLLM chat completion with mock."""
    config = CXFlowConfig()
    config.cxspacellm_token = "test_token"
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    connector = CxSpaceLLMConnector(registry, bus, config)
    
    # Mock the call method
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a test response"
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5}
    }
    
    connector.call = AsyncMock(return_value=mock_response)
    
    # Test chat completion
    result = await connector.chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.7
    )
    
    assert result == mock_response
    assert "choices" in result
    assert result["choices"][0]["message"]["content"] == "This is a test response"


@pytest.mark.asyncio
async def test_cxspacellm_enrich_dataflow_mock():
    """Test CxSpaceLLM dataflow enrichment with mock."""
    config = CXFlowConfig()
    config.cxspacellm_token = "test_token"
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    connector = CxSpaceLLMConnector(registry, bus, config)
    
    # Mock the chat_completion method
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "Analysis: This dataflow shows good performance."
                }
            }
        ],
        "created": 1234567890
    }
    
    connector.chat_completion = AsyncMock(return_value=mock_response)
    
    # Test dataflow enrichment
    dataflow = {
        "id": "test_flow",
        "type": "ml_training",
        "status": "complete",
        "data": {"accuracy": 0.95}
    }
    
    enriched = await connector.enrich_dataflow(dataflow)
    
    assert enriched["id"] == "test_flow"
    assert "ai_insights" in enriched
    assert enriched["enriched_by"] == "CxSpaceLLM"
    assert enriched["ai_insights"] == "Analysis: This dataflow shows good performance."


@pytest.mark.asyncio
async def test_workflow_orchestrator_with_cxspacellm():
    """Test workflow orchestrator with CxSpaceLLM integration."""
    config = CXFlowConfig()
    config.cxspacellm_enabled = True
    config.cxspacellm_token = "test_token"
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    orchestrator = create_orchestrator(registry, bus, config)
    
    # Verify CxSpaceLLM connector is initialized
    assert orchestrator.cxspacellm is not None
    assert orchestrator.cxspacellm.enabled is True


@pytest.mark.asyncio
async def test_enrich_dataflow_via_orchestrator():
    """Test enriching dataflow via orchestrator."""
    config = CXFlowConfig()
    config.cxspacellm_enabled = True
    config.cxspacellm_token = "test_token"
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    orchestrator = create_orchestrator(registry, bus, config)
    
    # Mock the enrich_dataflow method
    mock_enriched = {
        "id": "test",
        "type": "test",
        "data": {},
        "ai_insights": "Mock insights",
        "enriched_by": "CxSpaceLLM"
    }
    
    orchestrator.cxspacellm.enrich_dataflow = AsyncMock(return_value=mock_enriched)
    
    # Test enrichment
    dataflow = {"id": "test", "type": "test", "data": {}}
    result = await orchestrator.enrich_dataflow(dataflow)
    
    assert result["ai_insights"] == "Mock insights"
    assert result["enriched_by"] == "CxSpaceLLM"


@pytest.mark.asyncio
async def test_cxspacellm_events():
    """Test that CxSpaceLLM operations publish events."""
    config = CXFlowConfig()
    config.cxspacellm_token = "test_token"
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    # Track events
    events_received = []
    
    async def event_handler(event):
        events_received.append(event)
    
    bus.subscribe("cxspacellm.*", event_handler)
    
    connector = CxSpaceLLMConnector(registry, bus, config)
    
    # Mock the call method
    mock_response = {
        "choices": [{"message": {"content": "test"}}],
        "usage": {}
    }
    connector.call = AsyncMock(return_value=mock_response)
    
    # Trigger operations
    await connector.chat_completion(messages=[{"role": "user", "content": "test"}])
    
    # Give time for async event handling
    await asyncio.sleep(0.1)
    
    # Check events were published
    assert len(events_received) >= 2  # start and complete events
    event_types = [e.type for e in events_received]
    assert "cxspacellm.chat.start" in event_types
    assert "cxspacellm.chat.complete" in event_types


def test_cxspacellm_disabled_workflow():
    """Test workflow behavior when CxSpaceLLM is disabled."""
    config = CXFlowConfig()
    config.cxspacellm_enabled = False
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    orchestrator = create_orchestrator(registry, bus, config)
    
    # CxSpaceLLM should be initialized but disabled
    assert orchestrator.cxspacellm is not None
    assert orchestrator.cxspacellm.enabled is False


@pytest.mark.asyncio
async def test_enrich_dataflow_disabled():
    """Test that enrichment returns original data when disabled."""
    config = CXFlowConfig()
    config.cxspacellm_enabled = False
    
    registry = ServiceRegistry()
    bus = EventBus()
    
    orchestrator = create_orchestrator(registry, bus, config)
    
    dataflow = {"id": "test", "type": "test", "data": {"value": 123}}
    result = await orchestrator.enrich_dataflow(dataflow)
    
    # Should return original dataflow unchanged
    assert result == dataflow
    assert "ai_insights" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
