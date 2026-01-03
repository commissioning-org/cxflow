# CxSpaceLLM Integration Guide

This document describes the CxSpaceLLM integration into all CXFlow dataflows.

## Overview

CxSpaceLLM is a GitHub Space model that has been integrated into the CXFlow system to provide AI-powered insights and enrichment for all dataflows. This integration allows every dataflow in the system to be automatically enhanced with intelligent analysis, recommendations, and insights.

## What Was Implemented

### 1. Configuration Layer
- **File**: `.env.example`, `cxflow_core/config.py`
- Added CxSpaceLLM configuration options:
  - `CXSPACELLM_ENABLED` - Enable/disable the integration
  - `CXSPACELLM_MODEL` - The model name (default: "CxSpaceLLM")
  - `CXSPACELLM_BASE_URL` - API endpoint URL
  - `CXSPACELLM_TOKEN` - Authentication token
  - `CXSPACELLM_TIMEOUT_SECONDS` - Request timeout

### 2. CxSpaceLLM Connector
- **File**: `cxflow_core/connectors.py`
- Created `CxSpaceLLMConnector` class with the following capabilities:
  - **Chat Completion**: Generate AI responses using chat interface
  - **Data Analysis**: Analyze arbitrary data with custom prompts
  - **Dataflow Enrichment**: Automatically enrich dataflows with AI insights
  - **Event Publishing**: Publishes events for all operations (start/complete)

### 3. Workflow Integration
- **File**: `cxflow_core/workflows.py`
- Updated `WorkflowOrchestrator` to integrate CxSpaceLLM:
  - Added `cxspacellm` connector to orchestrator
  - Enhanced `run_ml_workflow()` with optional AI enrichment
  - Enhanced `run_research_workflow()` with optional AI enrichment
  - Enhanced `run_analytics_workflow()` with optional AI enrichment
  - Added `enrich_dataflow()` method for generic dataflow enrichment
  - Added `analyze_dataflow_with_ai()` method for custom analysis

### 4. Event Bus Integration
- **File**: `cxflow_core/integrations/webhook.py`
- Added CxSpaceLLM event handlers to webhook integration:
  - Subscribes to `cxspacellm.chat.complete` events
  - Subscribes to `cxspacellm.enrich.complete` events
  - Forwards CxSpaceLLM events to configured webhooks

### 5. Documentation
- **Files**: `README.md`, `cxflow_core/README.md`
- Added comprehensive documentation:
  - Quick start guide for CxSpaceLLM
  - Configuration examples
  - Usage examples with code snippets
  - Integration patterns

### 6. Examples
- **File**: `examples/cxspacellm_integration.py`
- Created comprehensive example demonstrating:
  - Direct CxSpaceLLM usage (chat, analysis, enrichment)
  - Workflow integration
  - Event-driven integration
  - Configuration checking

### 7. Tests
- **File**: `cxflow_core/tests/test_cxspacellm.py`
- Created comprehensive test suite:
  - Configuration tests
  - Connector initialization tests
  - Chat completion tests (with mocks)
  - Dataflow enrichment tests (with mocks)
  - Workflow orchestrator integration tests
  - Event publishing tests
  - Disabled state tests

## How It Works

### Basic Flow

1. **Configuration**: CxSpaceLLM is configured via environment variables
2. **Initialization**: The `CxSpaceLLMConnector` is created with the config
3. **Workflow Execution**: When a workflow runs, it can optionally enrich data
4. **AI Analysis**: CxSpaceLLM analyzes the dataflow data
5. **Enrichment**: AI insights are added to the dataflow result
6. **Events**: Events are published for monitoring and webhooks

### Integration Points

CxSpaceLLM is integrated at multiple levels:

1. **Direct Usage**: Applications can directly use `CxSpaceLLMConnector`
2. **Workflow Level**: All workflow methods support `enrich_with_ai=True`
3. **Generic Enrichment**: Any dataflow can be enriched via `enrich_dataflow()`
4. **Event Driven**: CxSpaceLLM operations trigger events for webhooks

## Usage Examples

### Configuration

```bash
# In .env file
CXSPACELLM_ENABLED=true
CXSPACELLM_TOKEN=your_github_models_token
CXSPACELLM_MODEL=CxSpaceLLM
CXSPACELLM_BASE_URL=https://models.inference.ai.azure.com
CXSPACELLM_TIMEOUT_SECONDS=60
```

### Direct Usage

```python
from cxflow_core import CXFlowConfig, ServiceRegistry, EventBus, CxSpaceLLMConnector

config = CXFlowConfig()
registry = ServiceRegistry()
bus = EventBus()

llm = CxSpaceLLMConnector(registry, bus, config)

# Chat completion
response = await llm.chat_completion(
    messages=[
        {"role": "system", "content": "You are a data analyst."},
        {"role": "user", "content": "Analyze this data..."}
    ]
)

# Analyze data
analysis = await llm.analyze_data(
    data={"metrics": [...]},
    prompt="Identify trends"
)

# Enrich dataflow
enriched = await llm.enrich_dataflow({
    "id": "flow1",
    "type": "ml_training",
    "data": {...}
})
```

### Workflow Integration

```python
from cxflow_core.workflows import create_orchestrator

orchestrator = create_orchestrator(registry, bus, config)

# ML workflow with AI enrichment
result = await orchestrator.run_ml_workflow(
    data=training_data,
    enrich_with_ai=True
)
print(result["ai_insights"])

# Generic dataflow enrichment
enriched = await orchestrator.enrich_dataflow(dataflow_data)
```

## Key Benefits

1. **Automated Insights**: Every dataflow can automatically get AI-generated insights
2. **Smart Recommendations**: AI suggests improvements and identifies potential issues
3. **Consistent Integration**: Same pattern works across all workflow types
4. **Event-Driven**: Integrates seamlessly with webhook notifications
5. **Optional**: Can be enabled/disabled per workflow or globally
6. **Flexible**: Works with custom prompts for specific analysis needs

## Files Modified

1. `.env.example` - Added CxSpaceLLM configuration
2. `cxflow_core/config.py` - Added CxSpaceLLM config fields
3. `cxflow_core/connectors.py` - Added `CxSpaceLLMConnector` class
4. `cxflow_core/workflows.py` - Enhanced workflows with CxSpaceLLM
5. `cxflow_core/__init__.py` - Exported CxSpaceLLM connector
6. `cxflow_core/integrations/webhook.py` - Added CxSpaceLLM event handlers
7. `cxflow_core/README.md` - Added documentation
8. `README.md` - Added overview and quick start

## Files Created

1. `examples/cxspacellm_integration.py` - Comprehensive examples
2. `cxflow_core/tests/test_cxspacellm.py` - Test suite

## Testing

Run the example:
```bash
# Set your token
export CXSPACELLM_TOKEN=your_token_here

# Run the example
python examples/cxspacellm_integration.py
```

Run tests:
```bash
cd cxflow_core
pytest tests/test_cxspacellm.py -v
```

Check syntax:
```bash
python -m py_compile cxflow_core/connectors.py
python -m py_compile cxflow_core/workflows.py
python -m py_compile examples/cxspacellm_integration.py
```

## Security Considerations

1. **Token Security**: Never commit `CXSPACELLM_TOKEN` to git
2. **API Calls**: All API calls include timeout protection
3. **Error Handling**: Failures gracefully fallback to non-enriched data
4. **Event Privacy**: Ensure webhook endpoints are secured

## Future Enhancements

Potential future improvements:
1. Streaming responses for large analyses
2. Caching of AI responses to reduce API calls
3. Batch enrichment of multiple dataflows
4. Custom system prompts per workflow type
5. Token usage tracking and rate limiting
6. A/B testing different prompts for enrichment

## Conclusion

CxSpaceLLM is now fully integrated into all CXFlow dataflows, providing AI-powered insights throughout the system. The integration is:
- ✅ Configured via environment variables
- ✅ Integrated into all workflow types
- ✅ Event-driven with webhook support
- ✅ Well-documented with examples
- ✅ Tested with comprehensive test suite
- ✅ Optional and can be disabled
- ✅ Backward compatible
