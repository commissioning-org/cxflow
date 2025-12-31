"""
CXFlow Jupyter Book Module

Jupyter Book-inspired documentation and book building system.
"""

from .book_builder import (
    BookBuilder,
    BookConfig,
    ProjectConfig,
    SiteConfig,
    ExportFormat,
    ThemeType,
    MystParser,
    NotebookExecutor,
    BuildResult,
    init_project,
    build,
    start_server,
)

from .cross_references import (
    ReferenceManager,
    ReferenceType,
    Reference,
    Citation,
    GlossaryTerm,
    LinkResolver,
    BibliographyGenerator,
    GlossaryGenerator,
)

from .api_service import (
    create_book_router,
    create_app,
    BuildManager,
)

__all__ = [
    # Book Builder
    "BookBuilder",
    "BookConfig",
    "ProjectConfig",
    "SiteConfig",
    "ExportFormat",
    "ThemeType",
    "MystParser",
    "NotebookExecutor",
    "BuildResult",
    "init_project",
    "build",
    "start_server",
    # Cross References
    "ReferenceManager",
    "ReferenceType",
    "Reference",
    "Citation",
    "GlossaryTerm",
    "LinkResolver",
    "BibliographyGenerator",
    "GlossaryGenerator",
    # API
    "create_book_router",
    "create_app",
    "BuildManager",
]

__version__ = "1.0.0"
