# Python FastAPI Endpoint Template

## Purpose
Create a new FastAPI endpoint following CXFlow project patterns.

## Prompt Template

```
Create a FastAPI endpoint for [DESCRIPTION]:

Endpoint Details:
- Path: [PATH] (e.g., /api/data/process)
- Method: [METHOD] (GET, POST, PUT, DELETE)
- Request Body: [DESCRIPTION OF REQUEST]
- Response: [DESCRIPTION OF RESPONSE]

Requirements:
- Use Pydantic models for request/response validation
- Include proper type hints (Python 3.10+ style)
- Use async/await pattern
- Add comprehensive error handling
- Return appropriate HTTP status codes
- Include docstring with description
- Follow project's FastAPI patterns

Optional:
- Add authentication if needed
- Include rate limiting if applicable
- Add caching if appropriate
```

## Variables to Fill In

- `[DESCRIPTION]`: Brief description of what the endpoint does
- `[PATH]`: The URL path for the endpoint
- `[METHOD]`: HTTP method (GET, POST, etc.)
- `[DESCRIPTION OF REQUEST]`: Request body structure and fields
- `[DESCRIPTION OF RESPONSE]`: Response format and fields

## Example

```
Create a FastAPI endpoint for processing data analytics:

Endpoint Details:
- Path: /api/analytics/process
- Method: POST
- Request Body: JSON with fields: data (list of dicts), metric (string), threshold (float)
- Response: JSON with fields: status, results (list), summary (dict)

Requirements:
- Use Pydantic models for request/response validation
- Include proper type hints (Python 3.10+ style)
- Use async/await pattern
- Add comprehensive error handling
- Return appropriate HTTP status codes
- Include docstring with description
- Follow project's FastAPI patterns

Optional:
- Add authentication if needed
- Include rate limiting if applicable
- Add caching if appropriate
```

## Expected Result

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any

app = FastAPI()

class AnalyticsRequest(BaseModel):
    """Request model for analytics processing."""
    data: list[dict]
    metric: str = Field(..., description="Metric to analyze")
    threshold: float = Field(ge=0.0, description="Threshold value")

class AnalyticsResponse(BaseModel):
    """Response model for analytics results."""
    status: str
    results: list[dict]
    summary: dict[str, Any]

@app.post("/api/analytics/process", response_model=AnalyticsResponse)
async def process_analytics(request: AnalyticsRequest) -> AnalyticsResponse:
    """
    Process analytics data and return results.
    
    Args:
        request: Analytics request with data and parameters
        
    Returns:
        Analytics results with status and summary
        
    Raises:
        HTTPException: If processing fails
    """
    try:
        # Processing logic here
        results = []
        summary = {"count": len(request.data)}
        
        return AnalyticsResponse(
            status="success",
            results=results,
            summary=summary
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {e}"
        )
```

## Related Patterns

- See `ml/app.py` for existing FastAPI endpoints
- See `cxflow_core/gateway.py` for API Gateway patterns
- See `.github/instructions/python.instructions.md` for Python coding standards

## Follow-up Prompts

After generating the endpoint:

1. **Add Tests:**
   ```
   Write pytest tests for this endpoint:
   - Test successful processing
   - Test validation errors
   - Test error handling
   - Use fixtures and mocks
   ```

2. **Add Documentation:**
   ```
   Generate API documentation for this endpoint including:
   - Request/response examples
   - Error responses
   - Status codes
   - Usage examples in curl and Python
   ```

3. **Integrate with Gateway:**
   ```
   Show how to register this endpoint with the CXFlow API Gateway
   ```
