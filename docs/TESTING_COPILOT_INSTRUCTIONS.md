# Testing GitHub Copilot Custom Instructions

This document describes how to test that the GitHub Copilot custom instructions are working correctly in the CXFlow repository.

## Prerequisites

- GitHub Copilot subscription (Individual, Business, or Enterprise)
- IDE with GitHub Copilot installed (VS Code, JetBrains, Visual Studio, etc.)
- This repository cloned locally

## Verification Steps

### 1. Check Files Are Present

Verify all instruction files exist:

```bash
# Main instructions file
ls -la .github/copilot-instructions.md

# Language-specific instructions
ls -la .github/instructions/

# Expected files:
# - python.instructions.md
# - php.instructions.md
# - javascript.instructions.md
# - docker.instructions.md
```

### 2. Test in Your IDE

#### Test 1: General Project Questions

Open GitHub Copilot Chat and ask:

```
What is the architecture of this project?
```

**Expected**: Copilot should describe the multi-service architecture with Laravel, Python microservices, CXFlow Core, Docker, etc.

#### Test 2: Python-Specific Questions

Open any `.py` file and ask:

```
Show me the pattern for creating a new FastAPI endpoint with proper type hints
```

**Expected**: Code following the project's FastAPI patterns with Pydantic models, async/await, proper type hints.

#### Test 3: PHP-Specific Questions

Open any `.php` file and ask:

```
How do I create a new Laravel service with dependency injection?
```

**Expected**: Code with PSR-12 style, constructor injection, readonly properties, following project patterns.

#### Test 4: Docker Questions

Open `docker-compose.yml` and ask:

```
How do I add a new service with health checks?
```

**Expected**: Service definition with health check, proper networking, volume patterns from the project.

### 3. Test Code Completion

#### Python Test

Create a new file `test_copilot.py`:

```python
# Start typing:
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def
```

**Expected**: Copilot should suggest a health check function that returns `{"status": "healthy"}` with proper type hints.

#### PHP Test

Create a new file `test_copilot.php`:

```php
<?php

declare(strict_types=1);

namespace App\Services;

class TestService
{
    public function __construct(
```

**Expected**: Copilot should suggest constructor with dependency injection using `private readonly`.

### 4. Test Context Awareness

#### Test Database Connection

In a PHP file, start typing:

```php
// Database configuration for Docker:
$host =
```

**Expected**: Copilot should suggest `'db'` (the Docker service name) not `'localhost'`.

#### Test Type Hints

In a Python file, start typing:

```python
def process_items(items:
```

**Expected**: Copilot should suggest modern Python type hints like `list[dict]` not `List[Dict]`.

## Sample Test Prompts

### Architecture & Setup

```
How do I start the development environment?
What ports do the services run on?
How do services communicate with each other?
```

### Python Development

```
Create a FastAPI endpoint that accepts JSON and returns a Pydantic model
How do I use the Event Bus in CXFlow Core?
Write a pytest test for an async function
Show me how to use the Service Registry
```

### PHP/Laravel Development

```
Create a queue job with retry logic
How do I create a migration?
Show me the pattern for form validation
How do I use database transactions?
```

### Docker & Infrastructure

```
How do I add a new microservice to docker-compose?
What's the health check pattern?
How do I debug a container?
Show me the volume pattern for development
```

## Validation Checklist

- [ ] Copilot describes the multi-service architecture correctly
- [ ] Python code suggestions use modern type hints (Python 3.10+)
- [ ] PHP code suggestions follow PSR-12 and use readonly properties
- [ ] Docker suggestions include health checks and service names
- [ ] Database connections use service names ('db', 'redis') not 'localhost'
- [ ] TypeScript suggestions use strict typing
- [ ] Code follows project-specific patterns (not generic examples)
- [ ] Build/test commands are correct (bin/lint, bin/test, etc.)

## Common Issues

### Issue: Copilot not using custom instructions

**Solutions:**
1. Ensure you're using a recent version of GitHub Copilot
2. Try restarting your IDE
3. Check that files are in the correct location (`.github/` not `github/`)
4. Verify YAML frontmatter in instruction files is valid

### Issue: Instructions not applying to specific files

**Check:**
- YAML frontmatter `applyTo` pattern matches the file
- File extension is correct (`.py`, `.php`, etc.)
- No syntax errors in the instruction file

### Issue: Generic suggestions instead of project-specific

**This might mean:**
- Instructions need more specific examples
- Context isn't being loaded properly
- File might not match any `applyTo` pattern

## Updating Instructions

If you find that Copilot is suggesting incorrect patterns:

1. Identify which instruction file needs updating
2. Add or modify the relevant section
3. Include concrete examples from the actual codebase
4. Test with Copilot Chat
5. Commit and push the changes

## Success Indicators

✅ **Good signs:**
- Copilot suggests `DB_HOST=db` not `localhost`
- Python code uses `list[dict]` not `List[Dict]`
- PHP code has `declare(strict_types=1);`
- FastAPI endpoints are async with type hints
- Docker services include health checks
- Code follows project patterns consistently

❌ **Signs instructions aren't working:**
- Generic Laravel code without readonly properties
- Python without type hints
- Docker without health checks
- Wrong database connection strings
- Inconsistent coding style

## Reporting Issues

If custom instructions aren't working as expected:

1. Document the specific prompt or file
2. Show what was expected vs what was suggested
3. Check which instruction file should apply
4. Update the instruction file with better examples
5. Test again

## Resources

- [GitHub Copilot Chat Cookbook](https://docs.github.com/copilot/tutorials/copilot-chat-cookbook)
- [Custom Instructions Docs](https://docs.github.com/copilot/how-tos/configure-custom-instructions/add-repository-instructions)
- [Project Instructions Documentation](docs/COPILOT_INSTRUCTIONS.md)

---

**Remember:** Custom instructions make Copilot context-aware for your specific project. The more accurate and detailed the instructions, the better the suggestions!
