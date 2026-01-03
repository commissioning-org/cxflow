# Pytest Testing Template

## Purpose
Write comprehensive pytest tests following CXFlow patterns.

## Prompt Template

```
Write pytest tests for [FUNCTION/CLASS/MODULE]:

Code to Test:
[PASTE CODE OR DESCRIBE FUNCTIONALITY]

Test Requirements:
- Test happy path (successful execution)
- Test error handling and edge cases
- Test with different input types
- Use pytest.mark.asyncio for async functions
- Mock external dependencies
- Use fixtures for common setup
- Include clear test names and docstrings
- Achieve >80% code coverage

Optional:
- Parametrize tests for multiple inputs
- Test performance/timing
- Test concurrency
```

## Variables to Fill In

- `[FUNCTION/CLASS/MODULE]`: What you're testing
- `[PASTE CODE OR DESCRIBE FUNCTIONALITY]`: The actual code or description

## Example

```
Write pytest tests for the following async function:

Code to Test:
```python
async def process_data(items: list[dict], threshold: float = 0.5) -> dict:
    """Process items and filter by threshold."""
    if not items:
        raise ValueError("Items list cannot be empty")
    
    results = [item for item in items if item.get('score', 0) >= threshold]
    
    return {
        "processed": len(items),
        "matched": len(results),
        "results": results
    }
```

Test Requirements:
- Test happy path (successful execution)
- Test error handling (empty list)
- Test edge cases (all match, none match, threshold edge)
- Use pytest.mark.asyncio for async functions
- Mock external dependencies if any
- Use fixtures for sample data
- Include clear test names and docstrings
- Achieve >80% code coverage

Optional:
- Parametrize tests for different thresholds
```

## Expected Result

```python
import pytest
from typing import Any

# Assuming the function is in data_processor module
from data_processor import process_data


@pytest.fixture
def sample_items() -> list[dict[str, Any]]:
    """Fixture providing sample items for testing."""
    return [
        {"id": 1, "name": "Item 1", "score": 0.8},
        {"id": 2, "name": "Item 2", "score": 0.3},
        {"id": 3, "name": "Item 3", "score": 0.6},
        {"id": 4, "name": "Item 4", "score": 0.9},
    ]


@pytest.mark.asyncio
async def test_process_data_success(sample_items):
    """Test successful processing with default threshold."""
    result = await process_data(sample_items, threshold=0.5)
    
    assert result["processed"] == 4
    assert result["matched"] == 3
    assert len(result["results"]) == 3
    assert all(item["score"] >= 0.5 for item in result["results"])


@pytest.mark.asyncio
async def test_process_data_empty_list():
    """Test that empty list raises ValueError."""
    with pytest.raises(ValueError, match="Items list cannot be empty"):
        await process_data([])


@pytest.mark.asyncio
async def test_process_data_all_match(sample_items):
    """Test when all items exceed threshold."""
    result = await process_data(sample_items, threshold=0.0)
    
    assert result["matched"] == 4
    assert len(result["results"]) == 4


@pytest.mark.asyncio
async def test_process_data_none_match(sample_items):
    """Test when no items exceed threshold."""
    result = await process_data(sample_items, threshold=1.0)
    
    assert result["matched"] == 0
    assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_process_data_missing_score():
    """Test handling items without score field."""
    items = [{"id": 1, "name": "No score"}]
    result = await process_data(items, threshold=0.5)
    
    assert result["matched"] == 0  # Missing score defaults to 0


@pytest.mark.asyncio
@pytest.mark.parametrize("threshold,expected_count", [
    (0.0, 4),
    (0.4, 3),
    (0.7, 2),
    (1.0, 0),
])
async def test_process_data_thresholds(sample_items, threshold, expected_count):
    """Test different threshold values."""
    result = await process_data(sample_items, threshold=threshold)
    assert result["matched"] == expected_count


@pytest.mark.asyncio
async def test_process_data_edge_case_exact_threshold():
    """Test items exactly at threshold value."""
    items = [{"id": 1, "score": 0.5}]
    result = await process_data(items, threshold=0.5)
    
    assert result["matched"] == 1  # Should include item at threshold
```

## Related Patterns

- See `ml/tests/` for existing pytest examples
- See `workflows/tests/` for async test patterns
- See `.github/instructions/python.instructions.md` for testing guidelines

## Follow-up Prompts

1. **Add Integration Tests:**
   ```
   Add integration tests that:
   - Test with real database
   - Test with external API
   - Use docker-compose for dependencies
   ```

2. **Measure Coverage:**
   ```
   Show how to run pytest with coverage reporting:
   - Generate coverage report
   - Identify untested code
   - Suggest additional tests
   ```

3. **Add Performance Tests:**
   ```
   Add performance tests using pytest-benchmark:
   - Test execution time
   - Test memory usage
   - Compare different implementations
   ```
