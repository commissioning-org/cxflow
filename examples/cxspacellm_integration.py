#!/usr/bin/env python3
"""
CxSpaceLLM Integration Example

Demonstrates how to use CxSpaceLLM to enrich dataflows with AI insights.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cxflow_core import (
    CXFlowConfig,
    ServiceRegistry,
    EventBus,
    ServiceStatus,
    CxSpaceLLMConnector,
)
from cxflow_core.workflows import create_orchestrator


async def example_direct_llm_usage():
    """Example: Direct usage of CxSpaceLLM connector."""
    print("\n=== Example 1: Direct CxSpaceLLM Usage ===\n")
    
    config = CXFlowConfig()
    registry = ServiceRegistry()
    bus = EventBus()
    
    # Create CxSpaceLLM connector
    llm = CxSpaceLLMConnector(registry, bus, config)
    
    if not llm.enabled:
        print("⚠️  CxSpaceLLM is not enabled. Set CXSPACELLM_ENABLED=true and CXSPACELLM_TOKEN")
        return
    
    # Example 1: Chat completion
    print("1. Chat Completion:")
    try:
        response = await llm.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful data analyst."},
                {"role": "user", "content": "What are the key metrics to track for an ML model?"}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Response: {content[:200]}...")
        print(f"Usage: {response.get('usage', {})}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Analyze data
    print("\n2. Data Analysis:")
    try:
        data = {
            "model_accuracy": 0.95,
            "training_time": 120,
            "features": ["age", "income", "location"],
            "samples": 10000
        }
        
        analysis = await llm.analyze_data(
            data=data,
            prompt="Analyze this ML model performance and suggest improvements"
        )
        
        content = analysis.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Analysis: {content[:200]}...")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Enrich dataflow
    print("\n3. Dataflow Enrichment:")
    try:
        dataflow = {
            "id": "flow_001",
            "type": "ml_training",
            "status": "complete",
            "data": {
                "model_id": "model_123",
                "accuracy": 0.92,
                "precision": 0.89,
                "recall": 0.94,
                "training_samples": 5000
            }
        }
        
        enriched = await llm.enrich_dataflow(dataflow)
        
        print(f"Dataflow ID: {enriched.get('id')}")
        print(f"Enriched by: {enriched.get('enriched_by')}")
        print(f"AI Insights: {enriched.get('ai_insights', '')[:200]}...")
    except Exception as e:
        print(f"Error: {e}")


async def example_workflow_integration():
    """Example: Using CxSpaceLLM through workflow orchestrator."""
    print("\n=== Example 2: Workflow Integration ===\n")
    
    config = CXFlowConfig()
    registry = ServiceRegistry()
    bus = EventBus()
    
    # Register mock services (in real usage, these would be actual services)
    registry.register("ml", "http://ml:8000", version="2.0.0")
    registry.update_status("ml", ServiceStatus.HEALTHY)
    
    registry.register("webhook_engine", "http://localhost:8001", version="2.0.0")
    registry.update_status("webhook_engine", ServiceStatus.HEALTHY)
    
    # Create orchestrator with CxSpaceLLM support
    orchestrator = create_orchestrator(registry, bus, config)
    
    if not orchestrator.cxspacellm.enabled:
        print("⚠️  CxSpaceLLM is not enabled")
        return
    
    # Example 1: Enrich any dataflow
    print("1. Generic Dataflow Enrichment:")
    try:
        dataflow = {
            "id": "ingestion_001",
            "type": "data_ingestion",
            "status": "complete",
            "data": {
                "source": "database",
                "records_processed": 10000,
                "duration_seconds": 45,
                "errors": 0
            }
        }
        
        enriched = await orchestrator.enrich_dataflow(dataflow)
        print(f"Original type: {dataflow.get('type')}")
        print(f"Enriched: {enriched.get('enriched_by')}")
        print(f"Insights: {enriched.get('ai_insights', '')[:150]}...")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Custom analysis
    print("\n2. Custom Dataflow Analysis:")
    try:
        metrics = {
            "throughput": [100, 150, 200, 180, 220],
            "latency_ms": [50, 55, 48, 52, 49],
            "error_rate": [0.01, 0.02, 0.01, 0.03, 0.01]
        }
        
        analysis = await orchestrator.analyze_dataflow_with_ai(
            dataflow_data=metrics,
            custom_prompt="Analyze these performance metrics over time and identify trends"
        )
        
        content = analysis.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Analysis: {content[:200]}...")
    except Exception as e:
        print(f"Error: {e}")


async def example_event_driven():
    """Example: Event-driven CxSpaceLLM integration."""
    print("\n=== Example 3: Event-Driven Integration ===\n")
    
    config = CXFlowConfig()
    registry = ServiceRegistry()
    bus = EventBus()
    
    # Track events
    events_received = []
    
    async def on_cxspacellm_event(event):
        """Handler for CxSpaceLLM events."""
        events_received.append(event)
        print(f"📨 Event: {event.type}")
        print(f"   Source: {event.source}")
        print(f"   Payload: {json.dumps(event.payload, indent=2)}")
    
    # Subscribe to CxSpaceLLM events
    bus.subscribe("cxspacellm.*", on_cxspacellm_event)
    
    # Create LLM connector
    llm = CxSpaceLLMConnector(registry, bus, config)
    
    if not llm.enabled:
        print("⚠️  CxSpaceLLM is not enabled")
        return
    
    print("Triggering CxSpaceLLM operations...\n")
    
    try:
        # This will trigger cxspacellm.chat.start and cxspacellm.chat.complete events
        await llm.chat_completion(
            messages=[
                {"role": "user", "content": "Hello!"}
            ],
            temperature=0.7
        )
        
        # This will trigger cxspacellm.enrich.start and cxspacellm.enrich.complete events
        await llm.enrich_dataflow({
            "id": "test",
            "type": "test",
            "data": {}
        })
        
        # Give event handlers time to process
        await asyncio.sleep(0.1)
        
        print(f"\n✅ Total events received: {len(events_received)}")
        
    except Exception as e:
        print(f"Error: {e}")


async def main():
    """Run all examples."""
    print("=" * 70)
    print("CxSpaceLLM Integration Examples")
    print("=" * 70)
    
    # Check configuration
    print("\nConfiguration:")
    print(f"  CXSPACELLM_ENABLED: {os.getenv('CXSPACELLM_ENABLED', 'true')}")
    print(f"  CXSPACELLM_MODEL: {os.getenv('CXSPACELLM_MODEL', 'CxSpaceLLM')}")
    print(f"  CXSPACELLM_TOKEN: {'***' if os.getenv('CXSPACELLM_TOKEN') else 'NOT SET'}")
    print(f"  CXSPACELLM_BASE_URL: {os.getenv('CXSPACELLM_BASE_URL', 'https://models.inference.ai.azure.com')}")
    
    if not os.getenv('CXSPACELLM_TOKEN'):
        print("\n⚠️  Warning: CXSPACELLM_TOKEN not set. Examples will fail.")
        print("   Set it in your .env file or environment")
    
    # Run examples
    await example_direct_llm_usage()
    await example_workflow_integration()
    await example_event_driven()
    
    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
