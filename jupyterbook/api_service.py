"""
Jupyter Book FastAPI Service

REST API endpoints for the CXFlow Book Builder.
Provides web service access to documentation building capabilities.
"""

from __future__ import annotations

import os
import json
import tempfile
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

_FASTAPI_AVAILABLE = True
try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form  # type: ignore
    from fastapi.responses import FileResponse, StreamingResponse  # type: ignore
except Exception:  # pragma: no cover
    _FASTAPI_AVAILABLE = False
    # Provide minimal placeholders so this module can be imported without fastapi.
    FastAPI = Any  # type: ignore
    HTTPException = Exception  # type: ignore
    BackgroundTasks = Any  # type: ignore
    UploadFile = Any  # type: ignore
    File = Any  # type: ignore
    Form = Any  # type: ignore
    FileResponse = Any  # type: ignore
    StreamingResponse = Any  # type: ignore

try:
    from pydantic import BaseModel, Field  # type: ignore
except Exception:  # pragma: no cover
    # Keep API models importable when pydantic isn't installed.
    from copy import deepcopy
    from typing import Callable

    class _FieldInfo:
        def __init__(self, default: Any = None, default_factory: Optional[Callable[[], Any]] = None):
            self.default = default
            self.default_factory = default_factory

        def get_default(self) -> Any:
            if self.default_factory is not None:
                return self.default_factory()
            return deepcopy(self.default)

    def Field(default: Any = None, default_factory: Optional[Callable[[], Any]] = None, **_: Any) -> Any:  # type: ignore
        return _FieldInfo(default=default, default_factory=default_factory)

    class BaseModel:  # type: ignore
        def __init__(self, **data: Any):
            annotations = getattr(self.__class__, '__annotations__', {}) or {}
            for key in annotations.keys():
                if key in data:
                    setattr(self, key, data[key])
                    continue
                if hasattr(self.__class__, key):
                    v = getattr(self.__class__, key)
                    if isinstance(v, _FieldInfo):
                        setattr(self, key, v.get_default())
                    elif isinstance(v, (list, dict, set)):
                        setattr(self, key, deepcopy(v))
                    else:
                        setattr(self, key, v)
                else:
                    setattr(self, key, None)
            for k, v in data.items():
                if not hasattr(self, k):
                    setattr(self, k, v)

# Import book builder components
from .book_builder import (
    BookBuilder,
    BookConfig,
    ProjectConfig,
    SiteConfig,
    ExportFormat,
    ThemeType,
    init_project,
    build,
    MystParser,
    NotebookExecutor,
    BuildResult,
)
from .cross_references import (
    ReferenceManager,
    LinkResolver,
    BibliographyGenerator,
    GlossaryGenerator,
)

logger = logging.getLogger(__name__)


# ============================================================================
# API Models
# ============================================================================

class BookInitRequest(BaseModel):
    """Request to initialize a new book project."""
    title: str = "My Book"
    description: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    template: str = "book-theme"


class BookBuildRequest(BaseModel):
    """Request to build a book."""
    project_path: str
    format: str = "html"  # html, pdf, latex, docx
    execute_notebooks: bool = False
    strict: bool = False
    output_path: Optional[str] = None


class MystParseRequest(BaseModel):
    """Request to parse MyST Markdown content."""
    content: str
    extract_metadata: bool = True
    resolve_references: bool = False


class NotebookExecuteRequest(BaseModel):
    """Request to execute a notebook."""
    notebook_path: str
    kernel: str = "python3"
    timeout: int = 600
    allow_errors: bool = False
    use_cache: bool = True


class CrossRefRequest(BaseModel):
    """Request to resolve cross-references."""
    content: str
    source_file: str = "document.md"
    project_path: Optional[str] = None
    bibliography_files: List[str] = Field(default_factory=list)


class BibliographyRequest(BaseModel):
    """Request to generate bibliography."""
    bib_files: List[str]
    style: str = "apa"  # apa, chicago, mla, ieee
    format: str = "html"  # html, markdown


class BuildProgress(BaseModel):
    """Build progress update."""
    status: str
    progress: float
    current_file: Optional[str] = None
    message: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


class BuildResponse(BaseModel):
    """Build response."""
    success: bool
    output_dir: Optional[str] = None
    files_built: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ParseResponse(BaseModel):
    """Parse response."""
    title: Optional[str] = None
    frontmatter: Dict[str, Any] = Field(default_factory=dict)
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    figures: List[Dict[str, Any]] = Field(default_factory=list)
    equations: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    cross_refs: List[str] = Field(default_factory=list)
    code_cells: List[Dict[str, Any]] = Field(default_factory=list)
    html_preview: Optional[str] = None


class RefResolveResponse(BaseModel):
    """Reference resolution response."""
    resolved_content: str
    resolved_count: int = 0
    unresolved: List[str] = Field(default_factory=list)
    broken_links: List[Dict[str, str]] = Field(default_factory=list)


class ProjectInfoResponse(BaseModel):
    """Project information response."""
    title: str
    description: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    toc: List[Dict[str, Any]] = Field(default_factory=list)
    content_files: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Build Manager (Background Tasks)
# ============================================================================

class BuildManager:
    """
    Manages book builds with progress tracking.
    """
    
    def __init__(self):
        self.builds: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def start_build(
        self,
        build_id: str,
        project_path: Path,
        format_: ExportFormat,
        execute: bool = False,
    ) -> str:
        """Start a new build."""
        async with self._lock:
            self.builds[build_id] = {
                'status': 'starting',
                'progress': 0.0,
                'started_at': datetime.now().isoformat(),
                'completed_at': None,
                'result': None,
                'errors': [],
            }
        
        return build_id
    
    async def update_progress(
        self,
        build_id: str,
        progress: float,
        status: str = 'building',
        current_file: Optional[str] = None,
    ):
        """Update build progress."""
        async with self._lock:
            if build_id in self.builds:
                self.builds[build_id]['progress'] = progress
                self.builds[build_id]['status'] = status
                if current_file:
                    self.builds[build_id]['current_file'] = current_file
    
    async def complete_build(
        self,
        build_id: str,
        result: BuildResult,
    ):
        """Mark build as complete."""
        async with self._lock:
            if build_id in self.builds:
                self.builds[build_id]['status'] = 'completed' if result.success else 'failed'
                self.builds[build_id]['progress'] = 1.0
                self.builds[build_id]['completed_at'] = datetime.now().isoformat()
                self.builds[build_id]['result'] = {
                    'success': result.success,
                    'output_dir': str(result.output_dir),
                    'files': result.files,
                    'errors': result.errors,
                    'warnings': result.warnings,
                    'duration_ms': result.duration_ms,
                }
    
    async def get_status(self, build_id: str) -> Optional[Dict]:
        """Get build status."""
        return self.builds.get(build_id)
    
    async def cleanup_old_builds(self, max_age_hours: int = 24):
        """Clean up old build records."""
        now = datetime.now()
        async with self._lock:
            to_remove = []
            for build_id, build in self.builds.items():
                started = datetime.fromisoformat(build['started_at'])
                age = (now - started).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(build_id)
            
            for build_id in to_remove:
                del self.builds[build_id]


# Global build manager
build_manager = BuildManager()


# ============================================================================
# FastAPI Router
# ============================================================================

def create_book_router() -> FastAPI:
    """Create FastAPI router for book builder endpoints."""
    
    from fastapi import APIRouter
    router = APIRouter(prefix="/book", tags=["Jupyter Book"])
    
    # -------------------------------------------------------------------------
    # Health & Info
    # -------------------------------------------------------------------------
    
    @router.get("/health")
    async def health_check():
        """Check book builder health."""
        return {
            "status": "healthy",
            "service": "jupyter-book-builder",
            "version": "1.0.0",
        }
    
    @router.get("/formats")
    async def list_formats():
        """List supported export formats."""
        return {
            "formats": [
                {"id": "html", "name": "HTML Website", "description": "Interactive web documentation"},
                {"id": "pdf", "name": "PDF Document", "description": "Printable PDF (requires typst or pandoc)"},
                {"id": "latex", "name": "LaTeX", "description": "LaTeX source files"},
                {"id": "docx", "name": "Word Document", "description": "Microsoft Word format"},
            ],
            "themes": [
                {"id": "book-theme", "name": "Book Theme", "description": "Classic book layout"},
                {"id": "article-theme", "name": "Article Theme", "description": "Single-page article"},
            ],
        }
    
    # -------------------------------------------------------------------------
    # Project Management
    # -------------------------------------------------------------------------
    
    @router.post("/init")
    async def initialize_project(request: BookInitRequest):
        """
        Initialize a new book project.
        
        Creates myst.yml configuration and project structure.
        """
        try:
            # Create temporary project directory
            project_dir = Path(tempfile.mkdtemp(prefix="book_"))
            
            config = init_project(
                project_dir,
                title=request.title,
                write_toc=False,
            )
            
            # Update with additional fields
            if request.description:
                config.project.description = request.description
            
            return {
                "success": True,
                "project_path": str(project_dir),
                "config_file": str(project_dir / "myst.yml"),
                "config": config.model_dump(),
            }
            
        except Exception as e:
            logger.exception("Failed to initialize project")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/project")
    async def get_project_info(project_path: str) -> ProjectInfoResponse:
        """
        Get project information.
        
        Returns configuration, content files, and TOC structure.
        """
        try:
            project_dir = Path(project_path)
            
            if not project_dir.exists():
                raise HTTPException(status_code=404, detail="Project not found")
            
            builder = BookBuilder(project_dir)
            files = builder.discover_content()
            toc = builder.build_toc()
            
            return ProjectInfoResponse(
                title=builder.config.project.title,
                description=builder.config.project.description,
                authors=[a.name for a in builder.config.project.authors],
                toc=toc,
                content_files=[str(f.relative_to(project_dir)) for f in files],
                config=builder.config.model_dump(),
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to get project info")
            raise HTTPException(status_code=500, detail=str(e))
    
    # -------------------------------------------------------------------------
    # Build Operations
    # -------------------------------------------------------------------------
    
    @router.post("/build", response_model=BuildResponse)
    async def build_book(request: BookBuildRequest, background_tasks: BackgroundTasks):
        """
        Build a book project.
        
        Supports HTML, PDF, LaTeX, and DOCX output formats.
        """
        try:
            project_dir = Path(request.project_path)
            
            if not project_dir.exists():
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Map format string to enum
            format_map = {
                'html': ExportFormat.HTML,
                'pdf': ExportFormat.PDF,
                'latex': ExportFormat.LATEX,
                'docx': ExportFormat.DOCX,
            }
            
            format_ = format_map.get(request.format.lower(), ExportFormat.HTML)
            
            # Build synchronously for now (could be async with build_id)
            result = build(
                project_dir,
                format_=format_,
                execute=request.execute_notebooks,
                strict=request.strict,
            )
            
            return BuildResponse(
                success=result.success,
                output_dir=str(result.output_dir),
                files_built=result.files,
                duration_ms=result.duration_ms,
                errors=result.errors,
                warnings=result.warnings,
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Build failed")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/build/async")
    async def build_book_async(
        request: BookBuildRequest,
        background_tasks: BackgroundTasks,
    ):
        """
        Start asynchronous book build.
        
        Returns a build ID for progress tracking.
        """
        import uuid
        
        build_id = str(uuid.uuid4())
        project_dir = Path(request.project_path)
        
        format_map = {
            'html': ExportFormat.HTML,
            'pdf': ExportFormat.PDF,
        }
        format_ = format_map.get(request.format.lower(), ExportFormat.HTML)
        
        await build_manager.start_build(build_id, project_dir, format_, request.execute_notebooks)
        
        async def run_build():
            try:
                result = build(
                    project_dir,
                    format_=format_,
                    execute=request.execute_notebooks,
                    strict=request.strict,
                )
                await build_manager.complete_build(build_id, result)
            except Exception as e:
                from dataclasses import dataclass
                @dataclass
                class ErrorResult:
                    success: bool = False
                    output_dir: Path = project_dir / "_build"
                    files: list = None
                    errors: list = None
                    warnings: list = None
                    duration_ms: int = 0
                    
                    def __post_init__(self):
                        self.files = []
                        self.errors = [str(e)]
                        self.warnings = []
                
                await build_manager.complete_build(build_id, ErrorResult())
        
        background_tasks.add_task(run_build)
        
        return {
            "build_id": build_id,
            "status": "started",
            "message": "Build started in background",
        }
    
    @router.get("/build/{build_id}/status")
    async def get_build_status(build_id: str):
        """Get status of an async build."""
        status = await build_manager.get_status(build_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Build not found")
        
        return status
    
    # -------------------------------------------------------------------------
    # Content Parsing
    # -------------------------------------------------------------------------
    
    @router.post("/parse", response_model=ParseResponse)
    async def parse_myst_content(request: MystParseRequest):
        """
        Parse MyST Markdown content.
        
        Extracts structure, references, and metadata.
        """
        try:
            parser = MystParser()
            parsed = parser.parse(request.content)
            
            response = ParseResponse(
                title=parsed.title,
                frontmatter=parsed.frontmatter,
                sections=[s for s in parsed.sections],
                figures=parsed.figures,
                equations=parsed.equations,
                citations=parsed.citations,
                cross_refs=parsed.cross_refs,
                code_cells=parsed.code_cells,
            )
            
            # Generate HTML preview if requested
            if request.resolve_references:
                # Simple preview
                preview_html = f"<h1>{parsed.title or 'Untitled'}</h1>\n"
                for section in parsed.sections:
                    level = section.get('level', 2)
                    title = section.get('title', '')
                    preview_html += f"<h{level}>{title}</h{level}>\n"
                
                response.html_preview = preview_html
            
            return response
            
        except Exception as e:
            logger.exception("Parse failed")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/parse/file")
    async def parse_file(
        file: UploadFile = File(...),
        extract_metadata: bool = Form(True),
    ):
        """
        Parse an uploaded MyST Markdown file.
        """
        try:
            content = await file.read()
            content = content.decode('utf-8')
            
            parser = MystParser()
            parsed = parser.parse(content, file.filename)
            
            return {
                "filename": file.filename,
                "title": parsed.title,
                "frontmatter": parsed.frontmatter,
                "section_count": len(parsed.sections),
                "figure_count": len(parsed.figures),
                "equation_count": len(parsed.equations),
                "citation_count": len(parsed.citations),
            }
            
        except Exception as e:
            logger.exception("File parse failed")
            raise HTTPException(status_code=500, detail=str(e))
    
    # -------------------------------------------------------------------------
    # Notebook Execution
    # -------------------------------------------------------------------------
    
    @router.post("/execute")
    async def execute_notebook(request: NotebookExecuteRequest):
        """
        Execute a Jupyter notebook.
        
        Returns notebook with outputs.
        """
        try:
            notebook_path = Path(request.notebook_path)
            
            if not notebook_path.exists():
                raise HTTPException(status_code=404, detail="Notebook not found")
            
            executor = NotebookExecutor(
                kernel_name=request.kernel,
                timeout=request.timeout,
                allow_errors=request.allow_errors,
            )
            
            result = executor.execute_notebook(
                notebook_path,
                use_cache=request.use_cache,
            )
            
            # Count outputs
            cell_count = len(result.get('cells', []))
            output_count = sum(
                len(cell.get('outputs', []))
                for cell in result.get('cells', [])
                if cell.get('cell_type') == 'code'
            )
            
            return {
                "success": True,
                "notebook_path": str(notebook_path),
                "cell_count": cell_count,
                "output_count": output_count,
                "cached": request.use_cache,
            }
            
        except Exception as e:
            logger.exception("Notebook execution failed")
            raise HTTPException(status_code=500, detail=str(e))
    
    # -------------------------------------------------------------------------
    # Cross-References
    # -------------------------------------------------------------------------
    
    @router.post("/resolve", response_model=RefResolveResponse)
    async def resolve_references(request: CrossRefRequest):
        """
        Resolve cross-references in content.
        
        Processes {ref}, {numref}, {cite}, {term} roles.
        """
        try:
            # Create reference manager
            if request.project_path:
                project_dir = Path(request.project_path)
            else:
                project_dir = Path(tempfile.mkdtemp())
            
            ref_manager = ReferenceManager(project_dir)
            
            # Load bibliographies
            for bib_file in request.bibliography_files:
                bib_path = project_dir / bib_file
                if bib_path.exists():
                    ref_manager.load_bibliography(bib_path)
            
            # Extract references from content
            ref_manager.extract_from_content(request.content, request.source_file)
            
            # Resolve links
            resolver = LinkResolver(ref_manager)
            resolved = resolver.resolve_content(
                request.content,
                request.source_file,
                output_format="html",
            )
            
            stats = resolver.get_statistics()
            
            return RefResolveResponse(
                resolved_content=resolved,
                resolved_count=stats['resolved_count'],
                unresolved=list(ref_manager.unresolved),
                broken_links=[
                    {"file": f, "target": t}
                    for f, t in stats['broken_link_details']
                ],
            )
            
        except Exception as e:
            logger.exception("Reference resolution failed")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/bibliography")
    async def generate_bibliography(request: BibliographyRequest):
        """
        Generate formatted bibliography.
        """
        try:
            ref_manager = ReferenceManager(Path("."))
            
            for bib_file in request.bib_files:
                path = Path(bib_file)
                if path.exists():
                    ref_manager.load_bibliography(path)
            
            generator = BibliographyGenerator(ref_manager, style=request.style)
            
            if request.format == "html":
                output = generator.generate_html()
            else:
                output = generator.generate_markdown()
            
            return {
                "bibliography": output,
                "citation_count": len(ref_manager.citations),
                "style": request.style,
                "format": request.format,
            }
            
        except Exception as e:
            logger.exception("Bibliography generation failed")
            raise HTTPException(status_code=500, detail=str(e))
    
    # -------------------------------------------------------------------------
    # Static Files & Downloads
    # -------------------------------------------------------------------------
    
    @router.get("/download/{build_id}")
    async def download_build(build_id: str):
        """
        Download built book as ZIP archive.
        """
        status = await build_manager.get_status(build_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Build not found")
        
        if status['status'] != 'completed':
            raise HTTPException(status_code=400, detail="Build not complete")
        
        result = status.get('result', {})
        output_dir = result.get('output_dir')
        
        if not output_dir or not Path(output_dir).exists():
            raise HTTPException(status_code=404, detail="Build output not found")
        
        # Create ZIP archive
        zip_path = shutil.make_archive(
            tempfile.mktemp(),
            'zip',
            output_dir,
        )
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename=f'book_{build_id[:8]}.zip',
        )
    
    @router.get("/preview/{build_id}/{path:path}")
    async def preview_file(build_id: str, path: str):
        """
        Preview a built file.
        """
        status = await build_manager.get_status(build_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Build not found")
        
        result = status.get('result', {})
        output_dir = result.get('output_dir')
        
        if not output_dir:
            raise HTTPException(status_code=404, detail="Build output not found")
        
        file_path = Path(output_dir) / path
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine media type
        suffix = file_path.suffix.lower()
        media_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.pdf': 'application/pdf',
        }
        
        media_type = media_types.get(suffix, 'application/octet-stream')
        
        return FileResponse(file_path, media_type=media_type)
    
    return router


# ============================================================================
# Main FastAPI Application
# ============================================================================

def create_app() -> FastAPI:
    """Create the FastAPI application."""

    if not _FASTAPI_AVAILABLE:
        raise ImportError("fastapi is required to use the CXFlow Book Builder API service")
    
    app = FastAPI(
        title="CXFlow Book Builder API",
        description="Jupyter Book-inspired documentation building service",
        version="1.0.0",
    )
    
    # Include router
    router = create_book_router()
    app.include_router(router)
    
    @app.get("/")
    async def root():
        return {
            "service": "CXFlow Book Builder",
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": {
                "health": "/book/health",
                "init": "/book/init",
                "build": "/book/build",
                "parse": "/book/parse",
                "execute": "/book/execute",
                "resolve": "/book/resolve",
            },
        }
    
    return app


# Create app instance
try:
    app = create_app() if _FASTAPI_AVAILABLE else None
except Exception as e:  # pragma: no cover
    logger.warning(f"CXFlow Book Builder API is disabled: {e}")
    app = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
