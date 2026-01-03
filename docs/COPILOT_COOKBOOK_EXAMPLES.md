# GitHub Copilot Cookbook Examples for CXFlow

This document provides practical, ready-to-use prompts organized by category for using GitHub Copilot effectively in the CXFlow repository.

## Table of Contents

1. [Code Generation](#code-generation)
2. [Testing & Quality](#testing--quality)
3. [Refactoring & Optimization](#refactoring--optimization)
4. [Debugging & Troubleshooting](#debugging--troubleshooting)
5. [Documentation & Comments](#documentation--comments)
6. [DevOps & CI/CD](#devops--cicd)
7. [Database & Migrations](#database--migrations)
8. [API Development](#api-development)
9. [Integration Patterns](#integration-patterns)
10. [Learning & Exploration](#learning--exploration)

---

## Code Generation

### Python - FastAPI Endpoint

**Prompt:**
```
Create a FastAPI endpoint at /api/data/process that:
- Accepts JSON with fields: data (list of dicts), threshold (float)
- Validates input with Pydantic
- Returns processed results with proper type hints
- Includes error handling
- Follows the project's async/await pattern
```

**Expected Result:** Async endpoint with Pydantic model, type hints, error handling

### PHP - Laravel Service

**Prompt:**
```
Create a Laravel service class DataProcessingService in app/Services that:
- Uses constructor dependency injection with readonly properties
- Has a method processData(array $data): array
- Uses database transactions
- Includes error handling and logging
- Follows PSR-12 and project conventions
```

**Expected Result:** Service with DI, transactions, logging, PSR-12 compliant

### Python - Event Bus Integration

**Prompt:**
```
Create a function that publishes an event to the CXFlow Event Bus when data processing completes:
- Event type: "data.processing.completed"
- Include processing metadata (duration, records, status)
- Use proper Event and EventPriority classes from cxflow_core
- Handle publishing errors gracefully
```

**Expected Result:** Event publishing with proper error handling

---

## Testing & Quality

### Python - Pytest for Async Function

**Prompt:**
```
Write pytest tests for the following async function [paste function].
Include:
- Happy path test
- Error handling test
- Edge case tests
- Use pytest.mark.asyncio
- Mock external dependencies
```

**Expected Result:** Comprehensive pytest test suite with fixtures and mocks

### PHP - PHPUnit for Service

**Prompt:**
```
Write PHPUnit tests for [ServiceClass]:
- Test successful execution
- Test validation failures
- Test database transactions
- Use RefreshDatabase trait
- Mock external services
```

**Expected Result:** PHPUnit test class with database testing

### Linting and Format Check

**Prompt:**
```
Review this code for:
- Python: PEP 8 compliance, type hints, docstrings
- PHP: PSR-12 compliance, type declarations, documentation
- Suggest improvements for code quality
```

**Expected Result:** Code review with specific improvement suggestions

---

## Refactoring & Optimization

### Extract Service Pattern

**Prompt:**
```
Refactor this controller method to extract business logic into a service class:
- Follow dependency injection pattern
- Maintain single responsibility
- Add proper error handling
- Keep controller thin
```

**Expected Result:** Separated service class with clean controller

### Performance Optimization

**Prompt:**
```
Optimize this code for performance:
- Identify N+1 queries
- Suggest eager loading
- Recommend caching strategies
- Improve algorithm efficiency
```

**Expected Result:** Optimized code with explanations

### Database Query Optimization

**Prompt:**
```
Review this database query and suggest optimizations:
- Add indexes where needed
- Reduce query count
- Use query builder efficiently
- Consider chunking for large datasets
```

**Expected Result:** Optimized queries with index suggestions

---

## Debugging & Troubleshooting

### Error Analysis

**Prompt:**
```
This error is occurring: [paste error].
Help me:
- Identify the root cause
- Suggest fixes
- Show how to prevent it in the future
- Add proper error handling
```

**Expected Result:** Root cause analysis with solution

### Docker Connection Issues

**Prompt:**
```
I'm getting "Connection refused" when connecting to MySQL from PHP.
Check:
- DB_HOST configuration (should be 'db' not 'localhost')
- Docker networking setup
- Service health checks
- Connection string format
```

**Expected Result:** Docker-specific troubleshooting steps

### API Integration Debugging

**Prompt:**
```
Debug why this API call is failing:
- Check request format
- Verify authentication
- Review response handling
- Add proper logging
```

**Expected Result:** Debugging steps with improved code

---

## Documentation & Comments

### Function Documentation

**Prompt:**
```
Add comprehensive docstrings to this function following:
- Python: Google-style docstrings
- PHP: PHPDoc format
Include: description, parameters, return value, exceptions, examples
```

**Expected Result:** Well-documented function with examples

### API Endpoint Documentation

**Prompt:**
```
Generate API documentation for this endpoint:
- Request format with examples
- Response format with status codes
- Error responses
- Authentication requirements
- Usage examples in curl and Python
```

**Expected Result:** Complete API documentation

### README Section

**Prompt:**
```
Write a README section for this feature:
- Overview and purpose
- Installation/setup steps
- Configuration options
- Usage examples
- Troubleshooting tips
```

**Expected Result:** Clear, comprehensive README section

---

## DevOps & CI/CD

### GitHub Actions Workflow

**Prompt:**
```
Create a GitHub Actions workflow for:
- Running Python tests with pytest
- Linting with flake8
- Building Docker images
- Running on push and pull request
- Caching dependencies
```

**Expected Result:** Complete .github/workflows/test.yml file

### Docker Health Check

**Prompt:**
```
Add a health check to this Docker service:
- Check HTTP endpoint availability
- Set appropriate intervals and timeouts
- Use curl or Python for checking
- Follow project patterns
```

**Expected Result:** Dockerfile with health check configuration

### Deployment Script

**Prompt:**
```
Create a deployment script that:
- Backs up current state
- Pulls latest changes
- Runs migrations
- Restarts services
- Validates deployment
- Includes rollback capability
```

**Expected Result:** Bash deployment script with error handling

---

## Database & Migrations

### Laravel Migration

**Prompt:**
```
Create a Laravel migration for a new table 'data_processing_logs':
- id (auto-increment)
- process_id (string, indexed)
- status (enum: pending, processing, completed, failed)
- data (json)
- error_message (text, nullable)
- timestamps
```

**Expected Result:** Complete migration with proper column types and indexes

### Eloquent Model

**Prompt:**
```
Create an Eloquent model for the data_processing_logs table:
- Mass assignable fields
- Cast JSON and datetime fields
- Add relationships if applicable
- Include common query scopes
```

**Expected Result:** Eloquent model with casts and scopes

### Database Seeder

**Prompt:**
```
Create a database seeder for testing:
- Generate 100 sample records
- Use Factory pattern
- Include realistic test data
- Handle relationships
```

**Expected Result:** Seeder with factory definitions

---

## API Development

### RESTful API Resource

**Prompt:**
```
Create a complete RESTful API for managing [resource]:
- Laravel: Controller, Resource, Request validation
- Python: FastAPI router, Pydantic models
- Include CRUD operations
- Add pagination
- Implement filtering and sorting
```

**Expected Result:** Complete API implementation with validation

### API Rate Limiting

**Prompt:**
```
Implement rate limiting for this API endpoint:
- Use Redis for storage
- 100 requests per minute per user
- Return appropriate HTTP status codes
- Include retry-after header
```

**Expected Result:** Rate limiting implementation

### API Versioning

**Prompt:**
```
Add versioning to this API:
- Support /v1/ and /v2/ endpoints
- Maintain backward compatibility
- Document version differences
- Implement version detection
```

**Expected Result:** Versioned API structure

---

## Integration Patterns

### Event Bus Usage

**Prompt:**
```
Implement an event-driven workflow using CXFlow Event Bus:
1. Publisher service emits events
2. Multiple subscribers react to events
3. Include error handling
4. Use appropriate event priorities
```

**Expected Result:** Complete event-driven implementation

### Service Registry Integration

**Prompt:**
```
Register and discover a service using CXFlow Service Registry:
- Register service with health check
- Discover and connect to ML service
- Handle service unavailability
- Implement retry logic
```

**Expected Result:** Service discovery implementation

### API Gateway Pattern

**Prompt:**
```
Route requests through the CXFlow API Gateway:
- Configure routes for multiple services
- Add authentication middleware
- Implement request/response transformation
- Add logging and monitoring
```

**Expected Result:** Gateway configuration and usage

---

## Learning & Exploration

### Explain Architecture

**Prompt:**
```
Explain how the CXFlow architecture works:
- How do services communicate?
- What is the role of the Event Bus?
- How does the Service Registry work?
- Diagram the data flow for a typical request
```

**Expected Result:** Detailed architecture explanation with examples

### Best Practices

**Prompt:**
```
What are the best practices for:
- Adding a new Python microservice
- Creating a Laravel background job
- Implementing error handling
- Writing tests
```

**Expected Result:** Best practices list with examples

### Code Review

**Prompt:**
```
Review this code and suggest improvements for:
- Code quality and maintainability
- Performance
- Security
- Testing coverage
- Documentation
```

**Expected Result:** Comprehensive code review with suggestions

---

## Quick Reference Prompts

### General Questions

```
What is the project structure?
How do I start the development environment?
Where should I put [type of code]?
What's the pattern for [specific task]?
```

### Python Development

```
Show me the FastAPI endpoint pattern
How do I use type hints correctly?
What's the async/await pattern?
How do I test this async function?
```

### PHP Development

```
Show me the Laravel service pattern
How do I use dependency injection?
What's the queue job pattern?
How do I write a migration?
```

### Docker & Infrastructure

```
How do services communicate in Docker?
What's the correct database host?
How do I add a health check?
How do I debug a container?
```

---

## Tips for Effective Copilot Usage

1. **Be Specific**: Include requirements, constraints, and patterns to follow
2. **Provide Context**: Mention the file type, framework, and related components
3. **Reference Patterns**: Refer to existing code patterns in the project
4. **Request Examples**: Ask for usage examples along with the code
5. **Iterate**: Refine prompts based on initial results
6. **Validate**: Always test and validate generated code
7. **Learn**: Use Copilot to understand existing code patterns

---

## Advanced Prompt Techniques

### Multi-Step Prompts

**Step 1:** "Create a service interface for data processing"
**Step 2:** "Implement the interface with validation"
**Step 3:** "Add error handling and logging"
**Step 4:** "Write tests for the implementation"

### Context-Rich Prompts

```
Given that:
- This is a Laravel application using PHP 8.3
- We use dependency injection with readonly properties
- Database is MySQL accessed via Docker service name 'db'
- All business logic should be in service classes

Create a service that processes payment data...
```

### Constraint-Based Prompts

```
Create a function that [task] with these constraints:
- Must be async
- Use type hints
- Handle errors gracefully
- Follow PEP 8
- Include docstring
- Be testable
```

---

## Common Patterns Quick Reference

### Python FastAPI Health Check

```python
@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "my-service"}
```

### PHP Laravel Service

```php
class MyService
{
    public function __construct(
        private readonly Repository $repo
    ) {}
    
    public function process(array $data): array
    {
        return DB::transaction(function () use ($data) {
            // Implementation
        });
    }
}
```

### Event Bus Publishing

```python
from cxflow_core import EventBus, Event, EventPriority

bus = EventBus()
await bus.publish(Event(
    type="data.processed",
    data={"id": "123"},
    priority=EventPriority.NORMAL
))
```

---

## Resources

- [Main Instructions](../.github/copilot-instructions.md)
- [Python Instructions](../.github/instructions/python.instructions.md)
- [PHP Instructions](../.github/instructions/php.instructions.md)
- [Docker Instructions](../.github/instructions/docker.instructions.md)
- [Testing Guide](./TESTING_COPILOT_INSTRUCTIONS.md)

---

**Remember:** These are starting points. Customize prompts based on your specific needs and always validate generated code!
