"""Automated research agent utilities.

This package is intentionally stdlib-only so it can run in minimal environments.
It provides comprehensive tools for analyzing, indexing, and researching GitHub
repositories with advanced features including:

- Multi-language code analysis and metrics
- Security vulnerability scanning
- Dependency extraction and analysis
- Full-text search with TF-IDF ranking
- Git history and contributor analysis
- Multiple report formats (Markdown, JSON, HTML, CSV)
- Plugin architecture for extensibility
- Async/parallel processing support
"""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "Research Agent Team"
__license__ = "MIT"

# Core components
from .cli import main
from .scanner import (
    FileInfo,
    RepoScan,
    LanguageStats,
    GitMetadata,
    scan_repo,
    iter_files,
    read_text,
    detect_language,
    DEFAULT_IGNORE_DIRS,
)
from .analysis import (
    RepoSummary,
    CodeMetrics,
    DependencyInfo,
    SecurityFinding,
    summarize_repo,
    analyze_code_quality,
    extract_dependencies,
    scan_security_issues,
)
from .indexer import (
    Match,
    SearchResult,
    InvertedIndex,
    build_index,
    TFIDFScorer,
)
from .repo_ops import (
    CommandResult,
    RepoOperationError,
    GitHistory,
    ContributorStats,
    ensure_cloned,
    update_repo,
    get_git_history,
    get_contributors,
    get_branches,
)
from .reporting import (
    ReportFormat,
    render_report,
    write_report,
    export_json,
    export_html,
    export_csv,
)
from .research_agent import (
    ResearchArtifact,
    ResearchConfig,
    ResearchPlugin,
    ResearchCache,
    MultiRepoArtifact,
    PluginManager,
    research_repo,
    research_repos_parallel,
    quick_research,
    cached_research,
    compare_repos,
    register_plugin,
    unregister_plugin,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # CLI
    "main",
    # Scanner
    "FileInfo",
    "RepoScan",
    "LanguageStats",
    "GitMetadata",
    "scan_repo",
    "iter_files",
    "read_text",
    "detect_language",
    "DEFAULT_IGNORE_DIRS",
    # Analysis
    "RepoSummary",
    "CodeMetrics",
    "DependencyInfo",
    "SecurityFinding",
    "summarize_repo",
    "analyze_code_quality",
    "extract_dependencies",
    "scan_security_issues",
    # Indexer
    "Match",
    "SearchResult",
    "InvertedIndex",
    "build_index",
    "TFIDFScorer",
    # Repo operations
    "CommandResult",
    "RepoOperationError",
    "GitHistory",
    "ContributorStats",
    "ensure_cloned",
    "update_repo",
    "get_git_history",
    "get_contributors",
    "get_branches",
    # Reporting
    "ReportFormat",
    "render_report",
    "write_report",
    "export_json",
    "export_html",
    "export_csv",
    # Research agent
    "ResearchArtifact",
    "ResearchConfig",
    "ResearchPlugin",
    "ResearchCache",
    "MultiRepoArtifact",
    "PluginManager",
    "research_repo",
    "research_repos_parallel",
    "quick_research",
    "cached_research",
    "compare_repos",
    "register_plugin",
    "unregister_plugin",
]


# Package-level constants
DEFAULT_CLONE_ROOT = ".repos"
DEFAULT_REPORTS_DIR = "reports"
MAX_FILE_SIZE_BYTES = 1_000_000
MAX_INDEX_TOKENS = 500_000

# Supported languages for analysis
SUPPORTED_LANGUAGES = frozenset({
    "python", "rust", "javascript", "typescript", "go", "java",
    "c", "cpp", "csharp", "ruby", "php", "swift", "kotlin",
    "scala", "haskell", "elixir", "clojure", "lua", "r",
})

# File categories
FILE_CATEGORIES = {
    "source": {".py", ".rs", ".js", ".ts", ".go", ".java", ".c", ".cpp", ".h", ".hpp"},
    "config": {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"},
    "docs": {".md", ".rst", ".txt", ".adoc", ".org"},
    "data": {".csv", ".tsv", ".xml", ".sql"},
    "build": {"Makefile", "CMakeLists.txt", "Cargo.toml", "package.json", "pyproject.toml"},
}
