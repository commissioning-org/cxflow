"""
CXFlow Book Builder

A Jupyter Book-inspired documentation and book building system.
Supports MyST Markdown, Jupyter Notebooks, and multi-format exports.

Based on concepts from https://github.com/jupyter-book/jupyter-book

Features:
- MyST Markdown parsing with directives and roles
- Jupyter Notebook execution and caching
- PDF, HTML, and Word document export
- Table of contents generation
- Cross-references and citations
- Interactive web previews
"""

from __future__ import annotations

import os
import re
import json
import shutil
import hashlib
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal, Callable
from enum import Enum
import logging

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Models
# ============================================================================

class ExportFormat(str, Enum):
    """Supported export formats."""
    HTML = "html"
    PDF = "pdf"
    LATEX = "latex"
    DOCX = "docx"
    MD = "md"
    JATS = "jats"  # Journal Article Tag Suite


class ThemeType(str, Enum):
    """Available themes."""
    BOOK = "book-theme"
    ARTICLE = "article-theme"
    CUSTOM = "custom"


class Author(BaseModel):
    """Author information."""
    name: str
    email: Optional[str] = None
    affiliation: Optional[str] = None
    orcid: Optional[str] = None
    url: Optional[str] = None


class TOCItem(BaseModel):
    """Table of contents item."""
    file: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    children: List["TOCItem"] = Field(default_factory=list)
    numbered: bool = True
    
    class Config:
        arbitrary_types_allowed = True


class ExportConfig(BaseModel):
    """Export configuration."""
    format: ExportFormat
    template: Optional[str] = None
    output: Optional[str] = None
    articles: List[str] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)


class ProjectConfig(BaseModel):
    """Project configuration (myst.yml equivalent)."""
    id: Optional[str] = None
    title: str = "Untitled Project"
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    authors: List[Author] = Field(default_factory=list)
    github: Optional[str] = None
    license: Optional[str] = None
    bibliography: List[str] = Field(default_factory=list)
    toc: List[TOCItem] = Field(default_factory=list)
    exports: List[ExportConfig] = Field(default_factory=list)
    execute: bool = False
    exclude: List[str] = Field(default_factory=list)


class SiteConfig(BaseModel):
    """Site configuration."""
    template: ThemeType = ThemeType.BOOK
    title: Optional[str] = None
    logo: Optional[str] = None
    favicon: Optional[str] = None
    nav: List[Dict[str, str]] = Field(default_factory=list)
    actions: List[Dict[str, str]] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)


class BookConfig(BaseModel):
    """Complete book configuration."""
    version: int = 1
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    site: SiteConfig = Field(default_factory=SiteConfig)
    extends: List[str] = Field(default_factory=list)


# ============================================================================
# MyST Markdown Parser
# ============================================================================

@dataclass
class ParsedContent:
    """Parsed content from MyST Markdown."""
    title: Optional[str] = None
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    figures: List[Dict[str, Any]] = field(default_factory=list)
    equations: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    cross_refs: List[str] = field(default_factory=list)
    code_cells: List[Dict[str, Any]] = field(default_factory=list)
    admonitions: List[Dict[str, Any]] = field(default_factory=list)


class MystParser:
    """
    MyST Markdown parser.
    
    Parses MyST Markdown files including:
    - YAML frontmatter
    - Directives (```{directive})
    - Roles ({role}`content`)
    - Cross-references
    - Math equations
    - Code cells
    """
    
    # Directive patterns
    FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    DIRECTIVE_PATTERN = re.compile(
        r'```\{(\w+)\}\s*(\S*)?\s*\n(.*?)```',
        re.DOTALL
    )
    ROLE_PATTERN = re.compile(r'\{(\w+)\}`([^`]+)`')
    MATH_BLOCK_PATTERN = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    MATH_INLINE_PATTERN = re.compile(r'\$([^\$]+)\$')
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    LABEL_PATTERN = re.compile(r'\(([a-z0-9_-]+)\)=')
    REF_PATTERN = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    
    # Supported directives
    ADMONITION_TYPES = [
        'note', 'warning', 'tip', 'important', 'attention',
        'caution', 'danger', 'error', 'hint', 'seealso'
    ]
    
    def __init__(self):
        """Initialize parser."""
        self.directives: Dict[str, Callable] = {}
        self._register_default_directives()
    
    def _register_default_directives(self):
        """Register default directive handlers."""
        for admon in self.ADMONITION_TYPES:
            self.directives[admon] = self._parse_admonition
        
        self.directives['code-block'] = self._parse_code_block
        self.directives['code-cell'] = self._parse_code_cell
        self.directives['figure'] = self._parse_figure
        self.directives['image'] = self._parse_image
        self.directives['math'] = self._parse_math
        self.directives['table'] = self._parse_table
        self.directives['mermaid'] = self._parse_mermaid
        self.directives['include'] = self._parse_include
        self.directives['toctree'] = self._parse_toctree
        self.directives['glossary'] = self._parse_glossary
        self.directives['bibliography'] = self._parse_bibliography
        self.directives['card'] = self._parse_card
        self.directives['grid'] = self._parse_grid
        self.directives['tab-set'] = self._parse_tabs
    
    def parse(self, content: str, filepath: Optional[str] = None) -> ParsedContent:
        """
        Parse MyST Markdown content.
        
        Args:
            content: MyST Markdown string
            filepath: Optional source file path
            
        Returns:
            ParsedContent object
        """
        result = ParsedContent()
        
        # Extract frontmatter
        fm_match = self.FRONTMATTER_PATTERN.match(content)
        if fm_match:
            try:
                result.frontmatter = yaml.safe_load(fm_match.group(1)) or {}
                result.title = result.frontmatter.get('title')
                content = content[fm_match.end():]
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
        
        # Extract title from first heading if not in frontmatter
        if not result.title:
            heading_match = self.HEADING_PATTERN.search(content)
            if heading_match and heading_match.group(1) == '#':
                result.title = heading_match.group(2).strip()
        
        # Parse sections (headings)
        for match in self.HEADING_PATTERN.finditer(content):
            level = len(match.group(1))
            title = match.group(2).strip()
            result.sections.append({
                'level': level,
                'title': title,
                'position': match.start(),
            })
        
        # Parse directives
        for match in self.DIRECTIVE_PATTERN.finditer(content):
            directive_name = match.group(1).lower()
            directive_arg = match.group(2) or ""
            directive_body = match.group(3).strip()
            
            if directive_name in self.directives:
                parsed = self.directives[directive_name](
                    directive_arg, directive_body
                )
                
                # Categorize parsed directive
                if directive_name in self.ADMONITION_TYPES:
                    result.admonitions.append(parsed)
                elif directive_name in ('figure', 'image'):
                    result.figures.append(parsed)
                elif directive_name == 'math':
                    result.equations.append(parsed)
                elif directive_name in ('code-cell', 'code-block'):
                    result.code_cells.append(parsed)
        
        # Parse roles (inline)
        for match in self.ROLE_PATTERN.finditer(content):
            role_name = match.group(1)
            role_content = match.group(2)
            
            if role_name == 'cite':
                result.citations.append(role_content)
            elif role_name == 'ref':
                result.cross_refs.append(role_content)
        
        # Parse math
        for match in self.MATH_BLOCK_PATTERN.finditer(content):
            result.equations.append({
                'type': 'block',
                'content': match.group(1).strip(),
            })
        
        # Parse labels and references
        for match in self.LABEL_PATTERN.finditer(content):
            result.cross_refs.append(match.group(1))
        
        result.content = content
        return result
    
    def _parse_admonition(self, arg: str, body: str) -> Dict:
        """Parse admonition directive."""
        lines = body.split('\n')
        title = arg if arg else None
        content_lines = []
        
        for line in lines:
            if line.startswith(':'):
                # Option line
                pass
            else:
                content_lines.append(line)
        
        return {
            'title': title,
            'content': '\n'.join(content_lines).strip(),
        }
    
    def _parse_code_block(self, arg: str, body: str) -> Dict:
        """Parse code-block directive."""
        language = arg or 'text'
        lines = body.split('\n')
        options = {}
        code_lines = []
        
        for line in lines:
            if line.startswith(':'):
                key, _, value = line[1:].partition(':')
                options[key.strip()] = value.strip()
            else:
                code_lines.append(line)
        
        return {
            'type': 'code-block',
            'language': language,
            'code': '\n'.join(code_lines),
            'options': options,
        }
    
    def _parse_code_cell(self, arg: str, body: str) -> Dict:
        """Parse code-cell directive (executable)."""
        result = self._parse_code_block(arg, body)
        result['type'] = 'code-cell'
        result['executable'] = True
        return result
    
    def _parse_figure(self, arg: str, body: str) -> Dict:
        """Parse figure directive."""
        lines = body.split('\n')
        options = {'src': arg}
        caption_lines = []
        
        for line in lines:
            if line.startswith(':'):
                key, _, value = line[1:].partition(':')
                options[key.strip()] = value.strip()
            else:
                caption_lines.append(line)
        
        return {
            'type': 'figure',
            'caption': '\n'.join(caption_lines).strip(),
            **options,
        }
    
    def _parse_image(self, arg: str, body: str) -> Dict:
        """Parse image directive."""
        return self._parse_figure(arg, body)
    
    def _parse_math(self, arg: str, body: str) -> Dict:
        """Parse math directive."""
        return {
            'type': 'block',
            'label': arg if arg else None,
            'content': body,
        }
    
    def _parse_table(self, arg: str, body: str) -> Dict:
        """Parse table directive."""
        return {
            'type': 'table',
            'caption': arg,
            'content': body,
        }
    
    def _parse_mermaid(self, arg: str, body: str) -> Dict:
        """Parse mermaid diagram directive."""
        return {
            'type': 'mermaid',
            'content': body,
        }
    
    def _parse_include(self, arg: str, body: str) -> Dict:
        """Parse include directive."""
        return {
            'type': 'include',
            'file': arg,
        }
    
    def _parse_toctree(self, arg: str, body: str) -> Dict:
        """Parse toctree directive (Sphinx compatibility)."""
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        return {
            'type': 'toctree',
            'entries': lines,
        }
    
    def _parse_glossary(self, arg: str, body: str) -> Dict:
        """Parse glossary directive."""
        return {
            'type': 'glossary',
            'content': body,
        }
    
    def _parse_bibliography(self, arg: str, body: str) -> Dict:
        """Parse bibliography directive."""
        return {
            'type': 'bibliography',
            'file': arg,
        }
    
    def _parse_card(self, arg: str, body: str) -> Dict:
        """Parse card directive."""
        lines = body.split('\n')
        options = {}
        content_lines = []
        
        for line in lines:
            if line.startswith(':'):
                key, _, value = line[1:].partition(':')
                options[key.strip()] = value.strip()
            else:
                content_lines.append(line)
        
        return {
            'type': 'card',
            'title': arg,
            'content': '\n'.join(content_lines).strip(),
            **options,
        }
    
    def _parse_grid(self, arg: str, body: str) -> Dict:
        """Parse grid directive."""
        return {
            'type': 'grid',
            'columns': arg,
            'content': body,
        }
    
    def _parse_tabs(self, arg: str, body: str) -> Dict:
        """Parse tab-set directive."""
        return {
            'type': 'tab-set',
            'content': body,
        }
    
    def parse_file(self, filepath: str | Path) -> ParsedContent:
        """Parse a MyST Markdown file."""
        filepath = Path(filepath)
        content = filepath.read_text(encoding='utf-8')
        return self.parse(content, str(filepath))


# ============================================================================
# Notebook Execution Engine
# ============================================================================

@dataclass
class CellOutput:
    """Notebook cell output."""
    output_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    text: Optional[str] = None
    traceback: Optional[List[str]] = None


@dataclass
class ExecutedCell:
    """Executed notebook cell."""
    cell_type: str
    source: str
    outputs: List[CellOutput] = field(default_factory=list)
    execution_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class NotebookExecutor:
    """
    Jupyter Notebook execution engine.
    
    Executes notebooks and caches results for faster rebuilds.
    """
    
    def __init__(
        self,
        kernel_name: str = "python3",
        timeout: int = 600,
        cache_dir: Optional[Path] = None,
        allow_errors: bool = False,
    ):
        """
        Initialize executor.
        
        Args:
            kernel_name: Jupyter kernel to use
            timeout: Cell execution timeout in seconds
            cache_dir: Directory for execution cache
            allow_errors: Continue execution on errors
        """
        self.kernel_name = kernel_name
        self.timeout = timeout
        self.cache_dir = cache_dir or Path("./_build/cache")
        self.allow_errors = allow_errors
        self._executed_notebooks: Dict[str, Any] = {}
    
    def _get_cache_key(self, notebook_path: Path) -> str:
        """Generate cache key for notebook."""
        content = notebook_path.read_bytes()
        return hashlib.md5(content).hexdigest()
    
    def _get_cached(self, notebook_path: Path) -> Optional[Dict]:
        """Get cached execution result."""
        cache_key = self._get_cache_key(notebook_path)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                return None
        return None
    
    def _save_cache(self, notebook_path: Path, result: Dict):
        """Save execution result to cache."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = self._get_cache_key(notebook_path)
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_file.write_text(json.dumps(result, indent=2))
    
    def execute_notebook(
        self,
        notebook_path: Path,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a Jupyter notebook.
        
        Args:
            notebook_path: Path to .ipynb file
            use_cache: Use cached results if available
            
        Returns:
            Executed notebook as dict
        """
        notebook_path = Path(notebook_path)
        
        # Check cache
        if use_cache:
            cached = self._get_cached(notebook_path)
            if cached:
                logger.info(f"Using cached execution for {notebook_path}")
                return cached
        
        logger.info(f"Executing notebook: {notebook_path}")
        
        # Read notebook
        with open(notebook_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        # Try nbclient execution
        try:
            import nbformat
            from nbclient import NotebookClient
            
            nb = nbformat.read(notebook_path, as_version=4)
            client = NotebookClient(
                nb,
                timeout=self.timeout,
                kernel_name=self.kernel_name,
                allow_errors=self.allow_errors,
            )
            
            # Execute
            client.execute()
            
            # Convert back to dict
            result = json.loads(nbformat.writes(nb))
            
        except ImportError:
            # Fallback: execute via subprocess
            logger.warning("nbclient not available, using subprocess execution")
            result = self._execute_via_subprocess(notebook_path, notebook)
        
        except Exception as e:
            logger.error(f"Notebook execution failed: {e}")
            if not self.allow_errors:
                raise
            result = notebook
        
        # Cache result
        if use_cache:
            self._save_cache(notebook_path, result)
        
        self._executed_notebooks[str(notebook_path)] = result
        return result
    
    def _execute_via_subprocess(
        self,
        notebook_path: Path,
        notebook: Dict,
    ) -> Dict:
        """Execute notebook using jupyter nbconvert subprocess."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.ipynb',
            delete=False
        ) as tmp:
            json.dump(notebook, tmp)
            tmp_path = tmp.name
        
        try:
            # Try nbconvert execution
            result = subprocess.run(
                [
                    'jupyter', 'nbconvert',
                    '--to', 'notebook',
                    '--execute',
                    '--inplace',
                    '--ExecutePreprocessor.timeout=' + str(self.timeout),
                    tmp_path,
                ],
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0 and not self.allow_errors:
                raise RuntimeError(f"Notebook execution failed: {result.stderr}")
            
            # Read executed notebook
            with open(tmp_path, 'r') as f:
                return json.load(f)
                
        finally:
            os.unlink(tmp_path)
    
    def clear_cache(self):
        """Clear execution cache."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            logger.info("Execution cache cleared")


# ============================================================================
# Book Builder
# ============================================================================

@dataclass
class BuildResult:
    """Build result."""
    success: bool
    output_dir: Path
    files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: int = 0


class BookBuilder:
    """
    Book builder - main orchestrator.
    
    Coordinates parsing, execution, and export of book content.
    """
    
    def __init__(
        self,
        project_dir: Path,
        config: Optional[BookConfig] = None,
    ):
        """
        Initialize book builder.
        
        Args:
            project_dir: Project root directory
            config: Book configuration (loaded from myst.yml if not provided)
        """
        self.project_dir = Path(project_dir)
        self.build_dir = self.project_dir / "_build"
        self.config = config or self._load_config()
        
        self.parser = MystParser()
        self.executor = NotebookExecutor(
            cache_dir=self.build_dir / "cache"
        )
        
        self._parsed_files: Dict[str, ParsedContent] = {}
        self._toc_structure: List[Dict] = []
    
    def _load_config(self) -> BookConfig:
        """Load configuration from myst.yml."""
        config_path = self.project_dir / "myst.yml"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Handle extends
            if 'extends' in data:
                for ext_file in data['extends']:
                    ext_path = self.project_dir / ext_file
                    if ext_path.exists():
                        with open(ext_path, 'r') as f:
                            ext_data = yaml.safe_load(f)
                        # Merge configurations
                        data = self._merge_configs(data, ext_data)
            
            return BookConfig(**data)
        
        return BookConfig()
    
    def _merge_configs(self, base: Dict, ext: Dict) -> Dict:
        """Merge configuration dictionaries."""
        result = base.copy()
        for key, value in ext.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def discover_content(self) -> List[Path]:
        """
        Discover content files in the project.
        
        Returns:
            List of content file paths
        """
        content_files = []
        
        # Supported extensions
        extensions = ['.md', '.ipynb', '.rst']
        
        for ext in extensions:
            for f in self.project_dir.rglob(f'*{ext}'):
                # Skip hidden files and build directory
                if f.name.startswith('.'):
                    continue
                if '_build' in f.parts:
                    continue
                if any(ex in str(f) for ex in self.config.project.exclude):
                    continue
                
                content_files.append(f)
        
        return sorted(content_files)
    
    def build_toc(self) -> List[Dict]:
        """
        Build table of contents from configuration or discovery.
        
        Returns:
            List of TOC entries
        """
        if self.config.project.toc:
            return [item.model_dump() for item in self.config.project.toc]
        
        # Auto-generate from discovered files
        files = self.discover_content()
        toc = []
        
        # Look for index/README first
        for f in files:
            if f.stem.lower() in ('index', 'readme', 'intro'):
                toc.append({'file': str(f.relative_to(self.project_dir))})
                break
        
        # Add remaining files
        for f in files:
            rel_path = str(f.relative_to(self.project_dir))
            if not any(item.get('file') == rel_path for item in toc):
                toc.append({'file': rel_path})
        
        self._toc_structure = toc
        return toc
    
    def parse_all(self) -> Dict[str, ParsedContent]:
        """
        Parse all content files.
        
        Returns:
            Dict mapping file paths to parsed content
        """
        files = self.discover_content()
        
        for f in files:
            rel_path = str(f.relative_to(self.project_dir))
            
            if f.suffix == '.md':
                self._parsed_files[rel_path] = self.parser.parse_file(f)
            elif f.suffix == '.ipynb':
                # Extract markdown cells for parsing
                with open(f, 'r') as nb:
                    notebook = json.load(nb)
                
                md_content = []
                for cell in notebook.get('cells', []):
                    if cell['cell_type'] == 'markdown':
                        md_content.append(''.join(cell['source']))
                
                self._parsed_files[rel_path] = self.parser.parse(
                    '\n\n'.join(md_content),
                    str(f)
                )
        
        return self._parsed_files
    
    def build_html(
        self,
        output_dir: Optional[Path] = None,
        execute: bool = False,
    ) -> BuildResult:
        """
        Build HTML site.
        
        Args:
            output_dir: Output directory
            execute: Execute notebooks
            
        Returns:
            BuildResult
        """
        start_time = datetime.now()
        output_dir = output_dir or (self.build_dir / "site")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        errors = []
        warnings = []
        built_files = []
        
        # Parse all content
        self.parse_all()
        
        # Build TOC
        toc = self.build_toc()
        
        # Process each file
        for rel_path, parsed in self._parsed_files.items():
            src_path = self.project_dir / rel_path
            
            try:
                # Execute notebooks if needed
                if execute and src_path.suffix == '.ipynb':
                    self.executor.execute_notebook(src_path)
                
                # Generate HTML
                html_content = self._render_html(rel_path, parsed)
                
                # Write output
                out_path = output_dir / rel_path.replace('.md', '.html').replace('.ipynb', '.html')
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(html_content)
                
                built_files.append(str(out_path))
                
            except Exception as e:
                errors.append(f"{rel_path}: {e}")
                logger.error(f"Failed to build {rel_path}: {e}")
        
        # Generate index
        index_html = self._generate_index_html(toc)
        index_path = output_dir / "index.html"
        index_path.write_text(index_html)
        built_files.append(str(index_path))
        
        # Copy static assets
        self._copy_assets(output_dir)
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return BuildResult(
            success=len(errors) == 0,
            output_dir=output_dir,
            files=built_files,
            errors=errors,
            warnings=warnings,
            duration_ms=duration,
        )
    
    def _render_html(self, rel_path: str, parsed: ParsedContent) -> str:
        """Render parsed content to HTML."""
        # Simple HTML template
        title = parsed.title or Path(rel_path).stem
        
        # Convert MyST content to HTML (simplified)
        content_html = self._myst_to_html(parsed.content)
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {self.config.project.title}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <nav class="sidebar">
        <h1>{self.config.project.title}</h1>
        <div id="toc"></div>
    </nav>
    <main>
        <article>
            <h1>{title}</h1>
            {content_html}
        </article>
    </main>
    <script src="/static/book.js"></script>
</body>
</html>
"""
    
    def _myst_to_html(self, content: str) -> str:
        """Convert MyST Markdown to HTML (simplified)."""
        import html
        
        # Escape HTML
        content = html.escape(content)
        
        # Convert headings
        content = re.sub(r'^#{6}\s+(.+)$', r'<h6>\1</h6>', content, flags=re.MULTILINE)
        content = re.sub(r'^#{5}\s+(.+)$', r'<h5>\1</h5>', content, flags=re.MULTILINE)
        content = re.sub(r'^#{4}\s+(.+)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
        content = re.sub(r'^#{3}\s+(.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^#{2}\s+(.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        
        # Convert bold/italic
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
        
        # Convert code
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        
        # Convert paragraphs
        paragraphs = content.split('\n\n')
        content = '\n'.join(f'<p>{p}</p>' if not p.startswith('<') else p for p in paragraphs if p.strip())
        
        return content
    
    def _generate_index_html(self, toc: List[Dict]) -> str:
        """Generate index HTML page."""
        toc_html = self._toc_to_html(toc)
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.project.title}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <nav class="sidebar">
        <h1>{self.config.project.title}</h1>
        {toc_html}
    </nav>
    <main>
        <article>
            <h1>{self.config.project.title}</h1>
            <p>{self.config.project.description or ''}</p>
            <h2>Table of Contents</h2>
            {toc_html}
        </article>
    </main>
</body>
</html>
"""
    
    def _toc_to_html(self, toc: List[Dict]) -> str:
        """Convert TOC to HTML list."""
        if not toc:
            return ''
        
        items = []
        for entry in toc:
            file_path = entry.get('file', '')
            title = entry.get('title') or Path(file_path).stem if file_path else ''
            href = file_path.replace('.md', '.html').replace('.ipynb', '.html')
            
            item = f'<li><a href="/{href}">{title}</a>'
            
            if entry.get('children'):
                item += self._toc_to_html(entry['children'])
            
            item += '</li>'
            items.append(item)
        
        return '<ul>' + '\n'.join(items) + '</ul>'
    
    def _copy_assets(self, output_dir: Path):
        """Copy static assets to output directory."""
        static_dir = output_dir / "static"
        static_dir.mkdir(exist_ok=True)
        
        # Create default stylesheet
        css = """
:root {
    --primary: #1565c0;
    --bg: #fafafa;
    --sidebar-bg: #f5f5f5;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    display: grid;
    grid-template-columns: 280px 1fr;
    min-height: 100vh;
}

.sidebar {
    background: var(--sidebar-bg);
    padding: 2rem;
    border-right: 1px solid #e0e0e0;
}

.sidebar h1 {
    font-size: 1.25rem;
    margin-bottom: 1.5rem;
    color: var(--primary);
}

.sidebar ul {
    list-style: none;
}

.sidebar li {
    margin: 0.5rem 0;
}

.sidebar a {
    color: #333;
    text-decoration: none;
}

.sidebar a:hover {
    color: var(--primary);
}

main {
    padding: 3rem;
    max-width: 800px;
}

article h1 { font-size: 2rem; margin-bottom: 1rem; }
article h2 { font-size: 1.5rem; margin: 2rem 0 1rem; }
article h3 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }

article p { line-height: 1.6; margin-bottom: 1rem; }

article code {
    background: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
}

article pre {
    background: #2d2d2d;
    color: #f8f8f2;
    padding: 1rem;
    border-radius: 5px;
    overflow-x: auto;
    margin: 1rem 0;
}
"""
        (static_dir / "style.css").write_text(css)
        
        # Create minimal JS
        js = """
document.addEventListener('DOMContentLoaded', () => {
    // Highlight current page in navigation
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar a').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.style.fontWeight = 'bold';
            link.style.color = 'var(--primary)';
        }
    });
});
"""
        (static_dir / "book.js").write_text(js)
    
    def build_pdf(
        self,
        output_file: Optional[Path] = None,
        template: str = "default",
    ) -> BuildResult:
        """
        Build PDF export.
        
        Requires typst or pandoc to be installed.
        """
        start_time = datetime.now()
        output_file = output_file or (self.build_dir / "exports" / f"{self.config.project.title}.pdf")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        errors = []
        
        # Collect all content into single document
        self.parse_all()
        toc = self.build_toc()
        
        # Build combined markdown
        combined_md = f"# {self.config.project.title}\n\n"
        if self.config.project.description:
            combined_md += f"{self.config.project.description}\n\n"
        
        for entry in toc:
            file_path = entry.get('file')
            if file_path and file_path in self._parsed_files:
                parsed = self._parsed_files[file_path]
                combined_md += f"\n\n{parsed.content}\n\n"
        
        # Try typst first, then pandoc
        try:
            if shutil.which('typst'):
                self._build_pdf_typst(combined_md, output_file)
            elif shutil.which('pandoc'):
                self._build_pdf_pandoc(combined_md, output_file)
            else:
                errors.append("No PDF engine found (install typst or pandoc)")
        except Exception as e:
            errors.append(str(e))
        
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return BuildResult(
            success=len(errors) == 0,
            output_dir=output_file.parent,
            files=[str(output_file)] if output_file.exists() else [],
            errors=errors,
            duration_ms=duration,
        )
    
    def _build_pdf_typst(self, content: str, output_file: Path):
        """Build PDF using Typst."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            md_path = f.name
        
        try:
            # Convert MD to Typst (simplified)
            typ_content = self._md_to_typst(content)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.typ', delete=False) as f:
                f.write(typ_content)
                typ_path = f.name
            
            subprocess.run(
                ['typst', 'compile', typ_path, str(output_file)],
                check=True,
                capture_output=True,
            )
        finally:
            os.unlink(md_path)
            if 'typ_path' in locals():
                os.unlink(typ_path)
    
    def _md_to_typst(self, content: str) -> str:
        """Convert Markdown to Typst format."""
        # Basic conversion
        lines = []
        for line in content.split('\n'):
            if line.startswith('# '):
                lines.append(f"= {line[2:]}")
            elif line.startswith('## '):
                lines.append(f"== {line[3:]}")
            elif line.startswith('### '):
                lines.append(f"=== {line[4:]}")
            elif line.startswith('- '):
                lines.append(f"- {line[2:]}")
            else:
                lines.append(line)
        
        return '\n'.join(lines)
    
    def _build_pdf_pandoc(self, content: str, output_file: Path):
        """Build PDF using Pandoc."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            md_path = f.name
        
        try:
            subprocess.run(
                [
                    'pandoc',
                    md_path,
                    '-o', str(output_file),
                    '--pdf-engine=xelatex',
                    '-V', 'geometry:margin=1in',
                ],
                check=True,
                capture_output=True,
            )
        finally:
            os.unlink(md_path)
    
    def clean(self, all_: bool = False):
        """
        Clean build directory.
        
        Args:
            all_: Also remove cache and templates
        """
        if self.build_dir.exists():
            if all_:
                shutil.rmtree(self.build_dir)
            else:
                # Keep cache and templates
                for item in self.build_dir.iterdir():
                    if item.name not in ('cache', 'templates'):
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
        
        logger.info(f"Cleaned build directory: {self.build_dir}")


# ============================================================================
# CLI Functions
# ============================================================================

def init_project(
    path: Path,
    title: str = "My Book",
    write_toc: bool = False,
) -> BookConfig:
    """
    Initialize a new Jupyter Book project.
    
    Args:
        path: Project directory
        title: Book title
        write_toc: Auto-generate table of contents
        
    Returns:
        Generated configuration
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    
    # Generate config
    config = BookConfig(
        project=ProjectConfig(
            title=title,
            id=hashlib.md5(title.encode()).hexdigest()[:8],
        ),
        site=SiteConfig(template=ThemeType.BOOK),
    )
    
    # Auto-generate TOC if requested
    if write_toc:
        builder = BookBuilder(path, config)
        files = builder.discover_content()
        
        toc_items = []
        for f in files:
            rel = str(f.relative_to(path))
            toc_items.append(TOCItem(file=rel))
        
        config.project.toc = toc_items
    
    # Write myst.yml
    config_data = {
        'version': 1,
        'project': {
            'id': config.project.id,
            'title': config.project.title,
            'keywords': [],
            'authors': [],
        },
        'site': {
            'template': 'book-theme',
        },
    }
    
    if config.project.toc:
        config_data['project']['toc'] = [
            {'file': item.file} for item in config.project.toc
        ]
    
    config_path = path / "myst.yml"
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Created myst.yml at {config_path}")
    
    return config


def build(
    path: Path,
    format_: ExportFormat = ExportFormat.HTML,
    execute: bool = False,
    strict: bool = False,
) -> BuildResult:
    """
    Build a Jupyter Book.
    
    Args:
        path: Project directory
        format_: Output format
        execute: Execute notebooks
        strict: Treat warnings as errors
        
    Returns:
        Build result
    """
    builder = BookBuilder(path)
    
    if format_ == ExportFormat.HTML:
        result = builder.build_html(execute=execute)
    elif format_ == ExportFormat.PDF:
        result = builder.build_pdf()
    else:
        raise ValueError(f"Unsupported format: {format_}")
    
    if strict and result.warnings:
        result.errors.extend(result.warnings)
        result.success = False
    
    return result


def start_server(
    path: Path,
    port: int = 3000,
    execute: bool = False,
):
    """
    Start local development server.
    
    Args:
        path: Project directory
        port: Server port
        execute: Execute notebooks
    """
    import http.server
    import socketserver
    
    # Build first
    builder = BookBuilder(path)
    result = builder.build_html(execute=execute)
    
    if not result.success:
        logger.error(f"Build failed: {result.errors}")
        return
    
    # Start server
    os.chdir(result.output_dir)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    with socketserver.TCPServer(("", port), Handler) as httpd:
        logger.info(f"Serving at http://localhost:{port}")
        print(f"\n🚀 Server started at http://localhost:{port}\n")
        httpd.serve_forever()


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="CXFlow Book Builder")
    subparsers = parser.add_subparsers(dest="command")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new book")
    init_parser.add_argument("path", nargs="?", default=".", help="Project path")
    init_parser.add_argument("--title", default="My Book", help="Book title")
    init_parser.add_argument("--write-toc", action="store_true", help="Generate TOC")
    
    # build command
    build_parser = subparsers.add_parser("build", help="Build the book")
    build_parser.add_argument("path", nargs="?", default=".", help="Project path")
    build_parser.add_argument("--html", action="store_true", help="Build HTML")
    build_parser.add_argument("--pdf", action="store_true", help="Build PDF")
    build_parser.add_argument("--execute", action="store_true", help="Execute notebooks")
    build_parser.add_argument("--strict", action="store_true", help="Strict mode")
    
    # start command
    start_parser = subparsers.add_parser("start", help="Start dev server")
    start_parser.add_argument("path", nargs="?", default=".", help="Project path")
    start_parser.add_argument("--port", type=int, default=3000, help="Port")
    start_parser.add_argument("--execute", action="store_true", help="Execute notebooks")
    
    # clean command
    clean_parser = subparsers.add_parser("clean", help="Clean build directory")
    clean_parser.add_argument("path", nargs="?", default=".", help="Project path")
    clean_parser.add_argument("--all", action="store_true", help="Remove all build files")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_project(Path(args.path), args.title, args.write_toc)
    
    elif args.command == "build":
        format_ = ExportFormat.PDF if args.pdf else ExportFormat.HTML
        result = build(Path(args.path), format_, args.execute, args.strict)
        
        if result.success:
            print(f"✅ Build completed in {result.duration_ms}ms")
            print(f"   Output: {result.output_dir}")
        else:
            print(f"❌ Build failed:")
            for error in result.errors:
                print(f"   - {error}")
    
    elif args.command == "start":
        start_server(Path(args.path), args.port, args.execute)
    
    elif args.command == "clean":
        builder = BookBuilder(Path(args.path))
        builder.clean(args.all)
        print("✅ Build directory cleaned")
    
    else:
        parser.print_help()
