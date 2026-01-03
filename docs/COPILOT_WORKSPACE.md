# GitHub Copilot Workspace Solution Guide

Welcome to the CXFlow GitHub Copilot Workspace! This guide covers everything you need to know about using the comprehensive Copilot workspace solution in this repository.

## What is a Copilot Workspace?

A GitHub Copilot Workspace is a fully configured development environment optimized for AI-assisted coding with GitHub Copilot. It includes:

- **Custom Instructions**: Repository and language-specific guidance for Copilot
- **Workspace Configuration**: VS Code/Codespaces settings and extensions
- **Cookbook Examples**: Ready-to-use prompts for common tasks
- **Development Tools**: Integrated linting, testing, and debugging
- **Architecture Context**: Deep understanding of the project structure

## Quick Start

### Option 1: GitHub Codespaces (Recommended)

1. Click "Code" → "Create codespace on main"
2. Wait for environment to initialize
3. GitHub Copilot is pre-configured and ready!
4. Start coding with AI assistance

### Option 2: Local Development with VS Code

1. Clone the repository
2. Open in VS Code
3. Install recommended extensions (popup will appear)
4. Enable GitHub Copilot in settings
5. Start the development environment: `bin/up`

### Option 3: Local Development with Other IDEs

1. Clone the repository
2. Ensure GitHub Copilot is installed in your IDE
3. Custom instructions will be automatically loaded
4. Start the development environment: `bin/up`

## Workspace Features

### 1. Custom Copilot Instructions

Located in `.github/` directory:

#### Repository-Wide Instructions
- **File**: `.github/copilot-instructions.md`
- **Applies to**: All files
- **Contains**: Architecture, technology stack, development workflow, common patterns

#### Language-Specific Instructions
- **Python**: `.github/instructions/python.instructions.md`
  - FastAPI patterns, async/await, type hints, testing
- **PHP**: `.github/instructions/php.instructions.md`
  - Laravel conventions, PSR-12, dependency injection, Eloquent
- **JavaScript/TypeScript**: `.github/instructions/javascript.instructions.md`
  - React patterns, TypeScript, API clients, testing
- **Docker**: `.github/instructions/docker.instructions.md`
  - Compose patterns, multi-stage builds, health checks

### 2. Cookbook Examples

**File**: `docs/COPILOT_COOKBOOK_EXAMPLES.md`

Contains ready-to-use prompts organized by category:
- Code Generation
- Testing & Quality
- Refactoring & Optimization
- Debugging & Troubleshooting
- Documentation & Comments
- DevOps & CI/CD
- Database & Migrations
- API Development
- Integration Patterns
- Learning & Exploration

### 3. Development Environment Configuration

#### VS Code Settings (`.vscode/`)

**extensions.json**: Recommended extensions including:
- GitHub Copilot & Copilot Chat
- Python (with Pylance, Black, Ruff)
- PHP (Intelephense)
- Docker
- ESLint & Prettier

**settings.json**: Workspace settings including:
- Auto-formatting on save
- Language-specific formatters
- Linting configurations
- GitHub Copilot enabled
- Terminal PATH configuration

**launch.json**: Debug configurations for:
- Python (FastAPI, ML Service, Research Agent, Workflows)
- PHP (Xdebug, Artisan commands)
- Docker (Attach to containers)
- Pytest (Test runner)

#### Devcontainer Configuration (`.devcontainer/`)

**devcontainer.json**: GitHub Codespaces configuration including:
- Docker Compose integration
- Pre-installed tools (GitHub CLI, Node, Python)
- Port forwarding (all services)
- Post-create commands
- Extension auto-install

### 4. Integrated Services

The workspace is aware of all CXFlow services:

| Service | Port | Purpose |
|---------|------|---------|
| Laravel App | 80 | Main web application |
| CXFlow Gateway | 8100 | API Gateway (unified access) |
| ML Service | 8090 | Machine learning endpoints |
| Research Agent | 8002 | GitHub repository analysis |
| Webhook Engine | 8001 | Event processing |
| JupyterBook | 8003 | Documentation generation |
| MySQL | 3306 | Database |
| Redis | 6379 | Cache and queues |
| phpMyAdmin | 8080 | Database management UI |
| Mailhog | 8025 | Email testing |

## Using GitHub Copilot in This Workspace

### Chat Interface

Open Copilot Chat and ask questions:

#### Architecture Questions
```
What is the architecture of this project?
How do services communicate with each other?
What ports do the services use?
```

#### Development Questions
```
How do I add a new FastAPI endpoint?
What's the pattern for creating a Laravel service?
How do I connect to the database in Docker?
```

#### Troubleshooting
```
Why am I getting "Connection refused" to MySQL?
How do I debug the ML service?
What's the correct way to use the Event Bus?
```

### Code Completion

As you type, Copilot suggests context-aware completions:

**Python Example:**
```python
# Type this:
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
async def

# Copilot suggests:
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "my-service"}
```

**PHP Example:**
```php
<?php
// Type this:
class MyService
{
    public function __construct(

// Copilot suggests:
    public function __construct(
        private readonly Repository $repo,
        private readonly Logger $logger
    ) {}
```

### Code Generation

Select code and ask Copilot to:
- Add tests
- Refactor for better performance
- Add error handling
- Generate documentation
- Explain functionality

### Code Review

Before committing, ask Copilot:
```
Review this code for:
- Code quality
- Security issues
- Performance problems
- Missing tests
- Documentation gaps
```

## Cookbook Workflow Examples

### Example 1: Adding a New FastAPI Endpoint

**Step 1: Ask Copilot**
```
Create a FastAPI endpoint at /api/analyze that:
- Accepts JSON with 'data' field (list of dicts)
- Validates with Pydantic
- Returns analysis results
- Uses async/await
- Includes error handling
```

**Step 2: Generate Tests**
```
Write pytest tests for the /api/analyze endpoint:
- Test successful analysis
- Test validation errors
- Test error handling
- Use fixtures and mocks
```

**Step 3: Add Documentation**
```
Document the /api/analyze endpoint:
- Request format with example
- Response format
- Error responses
- Usage examples
```

### Example 2: Creating a Laravel Background Job

**Step 1: Ask Copilot**
```
Create a Laravel queue job ProcessDataJob that:
- Accepts array of data IDs
- Processes each ID with retry logic
- Uses dependency injection
- Includes error handling and logging
- Follows PSR-12
```

**Step 2: Add Tests**
```
Write PHPUnit tests for ProcessDataJob:
- Test successful processing
- Test retry logic
- Test error handling
- Mock external dependencies
```

**Step 3: Dispatch Job**
```
Show me how to dispatch ProcessDataJob:
- From a controller
- From a command
- With delay
- On specific queue
```

### Example 3: Docker Service Integration

**Step 1: Ask Copilot**
```
Add a new microservice to docker-compose.yml:
- Python FastAPI service
- Port 8200
- Health check endpoint
- Connect to Redis
- Include in cxflow network
```

**Step 2: Create Dockerfile**
```
Create a Dockerfile for the new service:
- Multi-stage build
- Python 3.11 slim
- Install dependencies separately
- Non-root user
- Health check
```

**Step 3: Integration**
```
How do I integrate this service with:
- CXFlow API Gateway
- Service Registry
- Event Bus
```

## Best Practices

### 1. Provide Context

**Good:**
```
In the ML service (FastAPI), create a training endpoint that
accepts data and target column, uses scikit-learn for training,
and saves the model to the models/ directory.
```

**Less Effective:**
```
Create a training endpoint.
```

### 2. Reference Existing Patterns

**Good:**
```
Following the pattern in ml/app.py, create a new endpoint for predictions.
```

**Less Effective:**
```
Create a prediction endpoint.
```

### 3. Specify Constraints

**Good:**
```
Create a service with:
- Constructor dependency injection
- Readonly properties (PHP 8.3)
- Database transactions
- PSR-12 compliance
- Error logging
```

**Less Effective:**
```
Create a service.
```

### 4. Iterate and Refine

1. Start with a high-level prompt
2. Review the generated code
3. Ask for refinements
4. Add tests
5. Request documentation

### 5. Validate Everything

Always:
- Run linters: `bin/lint`
- Run tests: `bin/test`
- Check type hints
- Review security implications
- Test in development environment

## Troubleshooting

### Copilot Not Using Custom Instructions

**Check:**
1. Instructions files exist in `.github/`
2. Files have correct YAML frontmatter
3. IDE has latest Copilot extension
4. Restart IDE to reload instructions

### Suggestions Don't Match Project Patterns

**Solutions:**
1. Be more specific in prompts
2. Reference existing code patterns
3. Mention the specific instruction file
4. Update instructions if patterns have changed

### Copilot Suggests Wrong Database Host

**Fix:**
Mention in prompt: "Remember DB_HOST should be 'db' not 'localhost' for Docker"

### Missing Context for New Features

**Update Instructions:**
1. Add examples to relevant instruction file
2. Document new patterns in main instructions
3. Test with Copilot Chat
4. Commit and push changes

## Advanced Features

### Multi-File Editing

Ask Copilot to make changes across multiple files:
```
Rename the service method processData to analyzeData across:
- Service class
- Controller
- Tests
- Documentation
```

### Workflow Automation

Use Copilot to create automation scripts:
```
Create a script that:
- Runs all linters
- Executes tests
- Checks type coverage
- Generates report
```

### Architecture Exploration

Ask Copilot to explain complex flows:
```
Explain the data flow when:
1. A request comes to the API Gateway
2. It's routed to the ML service
3. An event is published
4. Multiple subscribers react
Show the code for each step.
```

## Maintenance

### Keeping Instructions Updated

**When to Update:**
- New service added
- Framework upgraded
- Patterns changed
- Best practices evolved
- Common mistakes discovered

**How to Update:**
1. Edit relevant `.md` file in `.github/instructions/`
2. Add concrete examples from codebase
3. Test with Copilot Chat
4. Commit changes
5. Verify improvements

### Testing Instructions

Use prompts from `docs/TESTING_COPILOT_INSTRUCTIONS.md` to verify:
- Copilot understands architecture
- Suggestions match project patterns
- Language-specific guidance works
- Docker patterns are correct

## Resources

### Documentation
- [Copilot Instructions](../docs/COPILOT_INSTRUCTIONS.md)
- [Cookbook Examples](../docs/COPILOT_COOKBOOK_EXAMPLES.md)
- [Testing Guide](../docs/TESTING_COPILOT_INSTRUCTIONS.md)
- [Quick Start](../COPILOT_QUICKSTART.md)

### Instruction Files
- [Main Instructions](../.github/copilot-instructions.md)
- [Python Instructions](../.github/instructions/python.instructions.md)
- [PHP Instructions](../.github/instructions/php.instructions.md)
- [JavaScript Instructions](../.github/instructions/javascript.instructions.md)
- [Docker Instructions](../.github/instructions/docker.instructions.md)

### External Resources
- [GitHub Copilot Chat Cookbook](https://docs.github.com/copilot/tutorials/copilot-chat-cookbook)
- [Custom Instructions Documentation](https://docs.github.com/copilot/how-tos/configure-custom-instructions/add-repository-instructions)
- [Copilot Best Practices](https://docs.github.com/copilot/get-started/best-practices)

## Getting Help

### In the Repository
1. Check documentation in `docs/`
2. Review examples in `examples/`
3. Ask Copilot Chat
4. Check existing code patterns

### Community
1. Create GitHub issue for bugs
2. Submit PR with improvements
3. Share cookbook examples
4. Document new patterns

## Feedback

Found an issue or have a suggestion?
1. Update instruction files
2. Add to cookbook examples
3. Improve documentation
4. Submit PR with changes

---

**Welcome to AI-Assisted Development with CXFlow!** 🚀

This workspace is designed to make you more productive from day one. Use GitHub Copilot as your AI pair programmer, and let it help you navigate the codebase, write better code, and learn faster.
