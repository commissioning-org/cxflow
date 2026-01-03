# GitHub Copilot Quick Start for CXFlow

This repository has custom GitHub Copilot instructions configured. Here's how to get the most out of them:

## 🚀 Quick Test

Open GitHub Copilot Chat and ask:

```
What is the architecture of this project?
```

You should get a detailed answer about CXFlow's multi-service architecture!

## 📚 What's Configured

We have custom instructions for:

- **Python** (FastAPI, ML services, workflows)
- **PHP** (Laravel, ingestion scripts)
- **JavaScript/TypeScript** (React, frontend)
- **Docker** (Compose, Dockerfiles)

## 💡 Example Prompts

### Python
```
Create a FastAPI health check endpoint
How do I use the Event Bus?
Show me the pattern for type hints
```

### PHP/Laravel
```
Create a Laravel service with dependency injection
How do I connect to the database in Docker?
Show me the queue job pattern
```

### Docker
```
Add a new service with health checks
How do services communicate?
```

## 📖 Full Documentation

- **Instructions Documentation**: [docs/COPILOT_INSTRUCTIONS.md](docs/COPILOT_INSTRUCTIONS.md)
- **Testing Guide**: [docs/TESTING_COPILOT_INSTRUCTIONS.md](docs/TESTING_COPILOT_INSTRUCTIONS.md)
- **Main README**: [README.md](README.md) (see GitHub Copilot Integration section)

## 🎯 Key Benefits

✅ Context-aware code suggestions
✅ Project-specific patterns
✅ Faster onboarding for new developers
✅ Consistent code quality
✅ Built-in best practices

## 🛠️ Instruction Files

Located in `.github/`:
- `copilot-instructions.md` - Repository-wide context
- `instructions/python.instructions.md` - Python patterns
- `instructions/php.instructions.md` - PHP/Laravel patterns
- `instructions/javascript.instructions.md` - TS/React patterns
- `instructions/docker.instructions.md` - Infrastructure patterns

## 🔍 Need Help?

If Copilot suggestions don't match project patterns:
1. Check [docs/TESTING_COPILOT_INSTRUCTIONS.md](docs/TESTING_COPILOT_INSTRUCTIONS.md)
2. Review the relevant instruction file in `.github/instructions/`
3. Update examples if needed

---

**Pro Tip**: The more context you provide in your prompts, the better Copilot's suggestions will be!
