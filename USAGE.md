# CXFlow Usage Guide

## Research Agent (Python - Ready to Use)

The research agent is a standalone Python tool that clones and analyzes GitHub repositories.

```bash
# Show help
python -m research_agent --help

# Clone a repository
python -m research_agent clone meilisearch/meilisearch

# Generate a markdown analysis report
python -m research_agent report meilisearch/meilisearch

# Search for code across the repo
python -m research_agent search meilisearch/meilisearch "IndexScheduler"
```

### Features
- Uses `gh repo clone` (falls back to `git clone`)
- Scans files and builds an inverted index
- Extracts Cargo workspace members, README, env vars
- Generates markdown reports

---

## Assistant Command (PHP/Laravel - Stub Files)

The `.stubs/assistant/` directory contains Laravel Artisan command stubs. These need to be copied into an existing Laravel project.

### Installation

```bash
# Copy into your Laravel project
cp -r .stubs/assistant/app/* /path/to/your-laravel-app/app/
cp -r .stubs/assistant/config/* /path/to/your-laravel-app/config/
```

### Environment Variables

Add to your `.env`:

```env
ASSISTANT_BASE_URL=https://models.inference.ai.azure.com
ASSISTANT_API_KEY=your-api-key
ASSISTANT_MODEL=gpt-4o
```

### Usage Examples

```bash
# Basic text completion
php artisan assistant:run "Explain quantum computing"

# JSON mode with schema validation
php artisan assistant:run "Extract entities from this text" --json --schema-file=schema.json

# Using built-in templates
php artisan assistant:run "function hello() { console.log('hi'); }" --template=code-review

# Template with variables
php artisan assistant:run "Hello world" --template=translate --var=language=French

# Load context from files
php artisan assistant:run "Review this code" \
    --context-file=src/MyClass.php \
    --context-file=tests/MyClassTest.php

# Batch processing
php artisan assistant:run --batch-file=prompts.txt --output=json --out-file=results.json

# Interactive chat mode
php artisan assistant:run --mode=chat --chat-history-file=history.json

# Workflow execution
php artisan assistant:run --workflow-file=pipeline.json --var=topic=AI

# Async queue dispatch with polling
php artisan assistant:run "Long running task" --queue=default --poll --poll-timeout=120

# Pipe from stdin
echo "Summarize this document" | php artisan assistant:run --stdin --template=summarize

# Dry run (debug what would be sent)
php artisan assistant:run "Test prompt" --dry-run --verbose
```

### Available Templates

| Template | Description |
|----------|-------------|
| `summarize` | Summarize content concisely |
| `explain` | Explain in simple terms |
| `translate` | Translate to specified language |
| `code-review` | Review code for bugs/security |
| `extract-json` | Extract structured data as JSON |
| `classify` | Classify into categories |
| `qa` | Answer questions from context |
| `rewrite` | Rewrite with specified style |
| `fix-grammar` | Fix grammar and spelling |
| `generate-tests` | Generate unit tests |

### Output Formats

- `--output=plain` (default)
- `--output=json`
- `--output=table`
- `--output=csv`
- `--output=yaml`

### Workflow Files

Create a `workflow.json`:

```json
{
  "name": "Extract and Summarize",
  "steps": [
    {
      "name": "extract",
      "type": "json",
      "prompt": "Extract key entities from: {{input}}"
    },
    {
      "name": "summarize",
      "type": "text",
      "prompt": "Summarize these entities: {{results.extract}}"
    }
  ]
}
```

Run with:
```bash
php artisan assistant:run "Your content here" --workflow-file=workflow.json
```

---

## Other Components

### Power BI Integration
See `powerbi/` and `docs/POWERBI_AUTOMATION.md`

### Jupyter Book Builder
See `jupyterbook/` and `docs/JUPYTER_BOOK.md`

### Power Automate Sync
See `workflows/` and `docs/POWER_AUTOMATE_SYNC.md`
