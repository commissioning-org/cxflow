# CXFlow Jupyter Book Documentation Builder

A comprehensive Jupyter Book-inspired documentation and book building system integrated into CXFlow. Build beautiful, interactive documentation from MyST Markdown files and Jupyter Notebooks.

## Overview

Based on [jupyter-book/jupyter-book](https://github.com/jupyter-book/jupyter-book), this implementation provides:

- **MyST Markdown Parsing** - Extended Markdown with directives, roles, and cross-references
- **Notebook Execution** - Execute Jupyter notebooks during build with caching
- **Multi-Format Export** - HTML websites, PDF documents, Word files
- **Cross-References** - Link between sections, figures, equations, citations
- **Bibliography Management** - BibTeX, YAML, and CSL-JSON support
- **FastAPI Integration** - REST API for building documentation programmatically

## Architecture

```
jupyterbook/
├── __init__.py           # Module exports
├── book_builder.py       # Core build system and MyST parser
├── cross_references.py   # Reference manager and link resolver
└── api_service.py        # FastAPI endpoints
```

## Quick Start

### 1. Initialize a Book Project

```python
from jupyterbook import init_project
from pathlib import Path

# Initialize new book
config = init_project(
    Path("./my-book"),
    title="My Documentation",
    write_toc=True
)
```

This creates a `myst.yml` configuration file:

```yaml
version: 1
project:
  id: abc12345
  title: My Documentation
  keywords: []
  authors: []
  toc:
    - file: index.md
    - file: chapter1.md
site:
  template: book-theme
```

### 2. Write MyST Markdown Content

Create `index.md`:

```markdown
---
title: Welcome to My Book
description: A comprehensive guide
---

# Welcome

This is my documentation built with CXFlow Book Builder.

## Features

```{note}
MyST Markdown supports rich content like admonitions!
```

See {ref}`getting-started` for the tutorial.

```{figure} images/diagram.png
:name: fig-architecture
:width: 80%

System architecture diagram
```

Refer to {numref}`Figure %s <fig-architecture>` above.
```

### 3. Build the Book

```python
from jupyterbook import build, ExportFormat
from pathlib import Path

# Build HTML website
result = build(
    Path("./my-book"),
    format_=ExportFormat.HTML,
    execute=True,  # Execute notebooks
)

print(f"Built in {result.duration_ms}ms")
print(f"Output: {result.output_dir}")
```

### 4. Start Development Server

```python
from jupyterbook import start_server
from pathlib import Path

# Start live preview server
start_server(
    Path("./my-book"),
    port=3000,
    execute=True
)
# Visit http://localhost:3000
```

## MyST Markdown Features

### Directives

Block-level elements with special behavior:

```markdown
```{note}
This is a note admonition.
```

```{warning}
Be careful with this feature!
```

```{code-block} python
:linenos:
:emphasize-lines: 2,3

def hello():
    print("Hello")
    return True
```

```{figure} path/to/image.png
:name: fig-example
:width: 50%
:align: center

Caption for the figure.
```
```

#### Supported Directives

| Directive | Purpose |
|-----------|---------|
| `note`, `warning`, `tip`, `important` | Admonitions |
| `code-block` | Syntax-highlighted code |
| `code-cell` | Executable code cell |
| `figure`, `image` | Images with captions |
| `math` | Math equations |
| `mermaid` | Diagrams |
| `table` | Tables with captions |
| `card`, `grid` | Layout components |
| `tab-set` | Tabbed content |
| `include` | Include other files |
| `glossary` | Glossary definitions |
| `bibliography` | Bibliography |

### Roles

Inline elements for special formatting:

```markdown
See the {ref}`section-label` for more details.

Reference {numref}`Figure %s <fig-example>`.

As shown in {cite}`smith2023`.

The {term}`API` is well documented.

Use the {kbd}`Ctrl+C` shortcut.

The {math}`E = mc^2` equation.
```

#### Supported Roles

| Role | Purpose |
|------|---------|
| `{ref}` | Cross-reference to labeled section |
| `{numref}` | Numbered reference (Figure 1, Table 2) |
| `{doc}` | Link to another document |
| `{cite}` | Citation reference |
| `{term}` | Glossary term |
| `{kbd}` | Keyboard shortcut |
| `{math}` | Inline math |

### Labels and Targets

Create reference targets:

```markdown
(getting-started)=
## Getting Started

This section can be referenced with {ref}`getting-started`.
```

### Math Equations

Inline and block math using KaTeX/MathJax:

```markdown
The equation $E = mc^2$ is famous.

$$
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
$$ (eq-gaussian)

Reference {eq}`eq-gaussian`.
```

## Configuration (myst.yml)

### Project Settings

```yaml
version: 1
project:
  id: unique-project-id
  title: "My Book Title"
  description: "A comprehensive guide to..."
  
  keywords:
    - documentation
    - tutorial
    - python
  
  authors:
    - name: John Doe
      email: john@example.com
      orcid: 0000-0000-0000-0000
  
  github: https://github.com/user/repo
  license: CC-BY-4.0
  
  # Bibliography files
  bibliography:
    - references.bib
    - citations.yaml
  
  # Table of contents
  toc:
    - file: index.md
    - title: Getting Started
      children:
        - file: installation.md
        - file: quickstart.md
    - title: User Guide
      children:
        - file: guide/basics.md
        - file: guide/advanced.md
    - file: api-reference.md
  
  # Export configurations
  exports:
    - format: pdf
      template: lapreprint-typst
      output: exports/book.pdf
  
  # Execution settings
  execute: true
  
  # Exclude patterns
  exclude:
    - "_build/**"
    - "drafts/**"

site:
  template: book-theme
  title: My Book
  logo: images/logo.png
  favicon: images/favicon.ico
  
  # Navigation bar
  nav:
    - title: GitHub
      url: https://github.com/user/repo
    - title: API Docs
      url: /api-reference.html
  
  # Call-to-action buttons
  actions:
    - title: Get Started
      url: /quickstart.html
    - title: Download PDF
      url: /exports/book.pdf
  
  # Custom domain
  domains:
    - docs.example.com
```

### Extending Configuration

```yaml
extends:
  - base-config.yml
  - theme-config.yml

project:
  title: My Extended Book
```

## Cross-References

### Reference Manager

```python
from jupyterbook import ReferenceManager, Reference, ReferenceType
from pathlib import Path

# Create manager
ref_manager = ReferenceManager(Path("./my-book"))

# Register references from content
ref_manager.extract_from_content(content, "chapter1.md")

# Load bibliography
ref_manager.load_bibliography(Path("references.bib"))

# Load glossary
ref_manager.load_glossary(Path("glossary.yaml"))

# Resolve a reference
ref = ref_manager.resolve("fig-architecture")
print(f"Figure {ref.number}: {ref.title}")
```

### Link Resolver

```python
from jupyterbook import LinkResolver

resolver = LinkResolver(ref_manager)

# Resolve all links in content
resolved_content = resolver.resolve_content(
    content,
    source_file="chapter1.md",
    output_format="html"
)

# Get statistics
stats = resolver.get_statistics()
print(f"Resolved {stats['resolved_count']} references")
print(f"Broken links: {stats['broken_links']}")
```

### Bibliography

```python
from jupyterbook import BibliographyGenerator

generator = BibliographyGenerator(ref_manager, style="apa")

# Generate HTML bibliography
html = generator.generate_html()

# Generate Markdown
md = generator.generate_markdown()
```

Supported bibliography formats:
- BibTeX (`.bib`)
- YAML (`.yaml`, `.yml`)
- CSL-JSON (`.json`)

### Glossary

Create `glossary.yaml`:

```yaml
API:
  definition: Application Programming Interface
  abbreviation: API
  see_also:
    - REST
    - GraphQL

REST:
  definition: Representational State Transfer, an architectural style for web services.
  see_also:
    - API

MyST:
  definition: Markedly Structured Text, an extended Markdown syntax.
```

## Notebook Execution

### Executor Configuration

```python
from jupyterbook import NotebookExecutor
from pathlib import Path

executor = NotebookExecutor(
    kernel_name="python3",
    timeout=600,  # 10 minutes per cell
    cache_dir=Path("./_build/cache"),
    allow_errors=False,
)

# Execute notebook
result = executor.execute_notebook(
    Path("notebooks/analysis.ipynb"),
    use_cache=True,
)

# Clear cache
executor.clear_cache()
```

### Execution in Build

```python
from jupyterbook import BookBuilder
from pathlib import Path

builder = BookBuilder(Path("./my-book"))

# Build with notebook execution
result = builder.build_html(
    execute=True,
)
```

## Export Formats

### HTML Website

```python
result = builder.build_html(
    output_dir=Path("./_build/html"),
    execute=True,
)
```

Features:
- Responsive book-theme layout
- Navigation sidebar
- Search functionality
- Syntax highlighting
- Math rendering

### PDF Document

```python
result = builder.build_pdf(
    output_file=Path("./_build/book.pdf"),
    template="default",
)
```

Requires one of:
- **Typst** (recommended): Fast, modern typesetting
- **Pandoc + LaTeX**: Traditional PDF generation

### LaTeX Source

```python
result = build(
    Path("./my-book"),
    format_=ExportFormat.LATEX,
)
```

## FastAPI Service

### Starting the Server

```python
from jupyterbook.api_service import app
import uvicorn

uvicorn.run(app, host="0.0.0.0", port=8000)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/book/health` | GET | Health check |
| `/book/formats` | GET | List supported formats |
| `/book/init` | POST | Initialize new project |
| `/book/project` | GET | Get project info |
| `/book/build` | POST | Build book (sync) |
| `/book/build/async` | POST | Build book (async) |
| `/book/build/{id}/status` | GET | Get build status |
| `/book/parse` | POST | Parse MyST content |
| `/book/parse/file` | POST | Parse uploaded file |
| `/book/execute` | POST | Execute notebook |
| `/book/resolve` | POST | Resolve references |
| `/book/bibliography` | POST | Generate bibliography |
| `/book/download/{id}` | GET | Download built book |
| `/book/preview/{id}/{path}` | GET | Preview built file |

### Example API Usage

```bash
# Initialize project
curl -X POST http://localhost:8000/book/init \
  -H "Content-Type: application/json" \
  -d '{"title": "My Documentation", "template": "book-theme"}'

# Parse MyST content
curl -X POST http://localhost:8000/book/parse \
  -H "Content-Type: application/json" \
  -d '{"content": "# Hello\n\n```{note}\nThis is a note.\n```"}'

# Build book
curl -X POST http://localhost:8000/book/build \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/book", "format": "html", "execute_notebooks": true}'

# Start async build
curl -X POST http://localhost:8000/book/build/async \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/book", "format": "pdf"}'

# Check build status
curl http://localhost:8000/book/build/abc123/status

# Download built book
curl -O http://localhost:8000/book/download/abc123
```

## CLI Usage

```bash
# Initialize new book
python -m jupyterbook.book_builder init ./my-book --title "My Book"

# Build HTML
python -m jupyterbook.book_builder build ./my-book --html --execute

# Build PDF
python -m jupyterbook.book_builder build ./my-book --pdf

# Start development server
python -m jupyterbook.book_builder start ./my-book --port 3000

# Clean build directory
python -m jupyterbook.book_builder clean ./my-book --all
```

## Integration with CXFlow

### Adding to Existing FastAPI App

```python
from fastapi import FastAPI
from jupyterbook import create_book_router

app = FastAPI()

# Add book builder endpoints
book_router = create_book_router()
app.include_router(book_router)
```

### Using with ML Pipeline

```python
from jupyterbook import BookBuilder, init_project
from pathlib import Path

# Generate documentation from ML experiment
def document_experiment(experiment_data: dict, output_dir: Path):
    # Initialize book
    init_project(output_dir, title=f"Experiment: {experiment_data['name']}")
    
    # Create index
    index_content = f"""---
title: {experiment_data['name']}
---

# {experiment_data['name']}

## Metrics

| Metric | Value |
|--------|-------|
"""
    for metric, value in experiment_data['metrics'].items():
        index_content += f"| {metric} | {value} |\n"
    
    (output_dir / "index.md").write_text(index_content)
    
    # Build documentation
    builder = BookBuilder(output_dir)
    result = builder.build_html()
    
    return result.output_dir
```

## Themes and Customization

### Available Themes

- **book-theme**: Classic multi-page book layout
- **article-theme**: Single-page article format

### Custom CSS

Add to your project:

```css
/* _static/custom.css */

:root {
    --primary-color: #1565c0;
    --sidebar-bg: #f5f5f5;
}

.sidebar h1 {
    color: var(--primary-color);
}
```

Reference in `myst.yml`:

```yaml
site:
  options:
    custom_css: _static/custom.css
```

## Best Practices

1. **Organize Content** - Use clear directory structure with logical groupings
2. **Use Labels** - Label all figures, tables, and sections for cross-referencing
3. **Cache Notebooks** - Enable caching for faster rebuilds
4. **Version Bibliography** - Keep references in version control
5. **Validate Links** - Check for broken references before publishing
6. **Preview Locally** - Use development server before deploying

## Troubleshooting

### Common Issues

**Build fails with "unresolved reference"**
- Check that the target label exists
- Verify the label syntax `(label-name)=`

**Notebook execution timeout**
- Increase timeout in executor configuration
- Check for infinite loops in code

**PDF generation fails**
- Install Typst: `cargo install typst-cli`
- Or Pandoc: `apt install pandoc texlive-xetex`

**Missing bibliography entries**
- Verify BibTeX syntax
- Check file path in configuration

## Contributing

Contributions welcome! See the main CXFlow contribution guidelines.

## License

Same license as CXFlow project.
