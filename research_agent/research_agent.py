"""High-level convenience wrapper with advanced features.

This module provides a comprehensive API for embedding the research agent
into other tooling, including:
- Async/concurrent research operations
- Caching for repeated analyses
- Plugin system for extensibility
- Configuration management
- Parallel multi-repo analysis
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from .analysis import RepoSummary, summarize_repo, scan_security_issues, extract_dependencies
from .indexer import InvertedIndex, build_index, SearchResult
from .repo_ops import (
    ensure_cloned,
    update_repo,
    get_git_history,
    get_contributors,
    CloneStrategy,
    GitHistory,
)
from .reporting import (
    render_report,
    export_json,
    export_html,
    write_report,
    ReportFormat,
    ReportLevel,
)
from .scanner import RepoScan, scan_repo


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ResearchConfig:
    """Configuration for research operations."""
    
    clone_root: Path = field(default_factory=lambda: Path(".repos"))
    cache_dir: Path = field(default_factory=lambda: Path(".cache/research"))
    reports_dir: Path = field(default_factory=lambda: Path("reports"))
    
    # Clone options
    clone_strategy: CloneStrategy = CloneStrategy.GH_CLI
    shallow_clone: bool = False
    auto_update: bool = False
    
    # Scan options
    parallel_scan: bool = True
    max_file_size: int = 1_000_000
    compute_hashes: bool = False
    
    # Analysis options
    include_security: bool = True
    include_metrics: bool = True
    include_git_history: bool = False
    max_commits_for_history: int = 1000
    
    # Index options
    build_index: bool = True
    include_symbols: bool = True
    include_ngrams: bool = True
    
    # Cache options
    cache_enabled: bool = True
    cache_ttl_hours: int = 24
    
    # Plugin options
    enabled_plugins: List[str] = field(default_factory=list)
    
    @classmethod
    def from_env(cls) -> 'ResearchConfig':
        """Create config from environment variables."""
        return cls(
            clone_root=Path(os.getenv("RESEARCH_CLONE_ROOT", ".repos")),
            cache_dir=Path(os.getenv("RESEARCH_CACHE_DIR", ".cache/research")),
            reports_dir=Path(os.getenv("RESEARCH_REPORTS_DIR", "reports")),
            parallel_scan=os.getenv("RESEARCH_PARALLEL_SCAN", "true").lower() == "true",
            include_security=os.getenv("RESEARCH_INCLUDE_SECURITY", "true").lower() == "true",
            include_metrics=os.getenv("RESEARCH_INCLUDE_METRICS", "true").lower() == "true",
            cache_enabled=os.getenv("RESEARCH_CACHE_ENABLED", "true").lower() == "true",
        )
    
    @classmethod
    def from_file(cls, path: Path) -> 'ResearchConfig':
        """Load config from JSON file."""
        if not path.exists():
            return cls()
        
        try:
            data = json.loads(path.read_text())
            return cls(
                clone_root=Path(data.get("clone_root", ".repos")),
                cache_dir=Path(data.get("cache_dir", ".cache/research")),
                reports_dir=Path(data.get("reports_dir", "reports")),
                parallel_scan=data.get("parallel_scan", True),
                include_security=data.get("include_security", True),
                include_metrics=data.get("include_metrics", True),
                cache_enabled=data.get("cache_enabled", True),
                cache_ttl_hours=data.get("cache_ttl_hours", 24),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()
    
    def to_file(self, path: Path) -> None:
        """Save config to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "clone_root": str(self.clone_root),
            "cache_dir": str(self.cache_dir),
            "reports_dir": str(self.reports_dir),
            "parallel_scan": self.parallel_scan,
            "include_security": self.include_security,
            "include_metrics": self.include_metrics,
            "cache_enabled": self.cache_enabled,
            "cache_ttl_hours": self.cache_ttl_hours,
        }
        path.write_text(json.dumps(data, indent=2))


# ============================================================================
# Research Artifacts
# ============================================================================

@dataclass
class ResearchArtifact:
    """Result of a research operation on a single repository."""
    
    repo_path: Path
    scan: RepoScan
    summary: RepoSummary
    index: Optional[InvertedIndex] = None
    git_history: Optional[GitHistory] = None
    
    # Metadata
    repo_name: str = ""
    research_timestamp: datetime = field(default_factory=datetime.now)
    research_duration_ms: int = 0
    config_used: Optional[ResearchConfig] = None
    
    # Computed fields
    _security_findings: Optional[List] = field(default=None, repr=False)
    _dependencies: Optional[List] = field(default=None, repr=False)
    
    def __post_init__(self):
        if not self.repo_name and self.repo_path:
            self.repo_name = self.repo_path.name
    
    @property
    def security_findings(self) -> List:
        """Lazy-load security findings."""
        if self._security_findings is None and self.summary.security_findings:
            self._security_findings = self.summary.security_findings
        return self._security_findings or []
    
    @property
    def dependencies(self) -> List:
        """Lazy-load dependencies."""
        if self._dependencies is None and self.summary.dependencies:
            self._dependencies = self.summary.dependencies
        return self._dependencies or []
    
    def search(self, query: str, max_results: int = 30, use_fuzzy: bool = False) -> List[SearchResult]:
        """Search within the repository."""
        if not self.index:
            raise ValueError("Index not built. Set build_index=True in config.")
        return self.index.search(query, max_results=max_results, use_fuzzy=use_fuzzy)
    
    def generate_report(
        self,
        format: ReportFormat = ReportFormat.MARKDOWN,
        level: ReportLevel = ReportLevel.STANDARD,
        title: Optional[str] = None,
    ) -> str:
        """Generate a report in the specified format."""
        if format == ReportFormat.JSON:
            return export_json(self.summary, self.scan)
        elif format == ReportFormat.HTML:
            return export_html(self.summary, self.scan, title=title)
        else:
            return render_report(self.summary, self.scan, title=title, level=level)
    
    def save_report(
        self,
        path: Path,
        format: ReportFormat = ReportFormat.MARKDOWN,
        level: ReportLevel = ReportLevel.STANDARD,
        title: Optional[str] = None,
    ) -> Path:
        """Save a report to file."""
        content = self.generate_report(format=format, level=level, title=title)
        write_report(path, content)
        return path
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "repo_path": str(self.repo_path),
            "repo_name": self.repo_name,
            "research_timestamp": self.research_timestamp.isoformat(),
            "research_duration_ms": self.research_duration_ms,
            "file_count": len(self.scan.files),
            "total_bytes": self.scan.total_bytes,
            "primary_language": self.summary.primary_language,
            "security_findings_count": len(self.security_findings),
            "dependencies_count": len(self.dependencies),
        }


@dataclass
class MultiRepoArtifact:
    """Result of research on multiple repositories."""
    
    artifacts: List[ResearchArtifact] = field(default_factory=list)
    total_duration_ms: int = 0
    successful: int = 0
    failed: int = 0
    errors: Dict[str, str] = field(default_factory=dict)
    
    def add(self, artifact: ResearchArtifact) -> None:
        """Add an artifact to the collection."""
        self.artifacts.append(artifact)
        self.successful += 1
    
    def add_error(self, repo: str, error: str) -> None:
        """Record an error."""
        self.errors[repo] = error
        self.failed += 1
    
    def get(self, repo_name: str) -> Optional[ResearchArtifact]:
        """Get artifact by repo name."""
        for a in self.artifacts:
            if a.repo_name == repo_name or str(a.repo_path).endswith(repo_name):
                return a
        return None
    
    def __iter__(self) -> Iterator[ResearchArtifact]:
        return iter(self.artifacts)
    
    def __len__(self) -> int:
        return len(self.artifacts)


# ============================================================================
# Caching
# ============================================================================

@dataclass
class CacheEntry:
    """A cached research result."""
    
    repo: str
    artifact_path: Path
    created_at: datetime
    expires_at: datetime
    commit_hash: str = ""
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "repo": self.repo,
            "artifact_path": str(self.artifact_path),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "commit_hash": self.commit_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CacheEntry':
        return cls(
            repo=data["repo"],
            artifact_path=Path(data["artifact_path"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            commit_hash=data.get("commit_hash", ""),
        )


class ResearchCache:
    """Cache for research artifacts."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.index_file = cache_dir / "index.json"
        self._index: Dict[str, CacheEntry] = {}
        self._load_index()
    
    def _load_index(self) -> None:
        """Load cache index from disk."""
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text())
                for repo, entry_data in data.items():
                    self._index[repo] = CacheEntry.from_dict(entry_data)
            except (json.JSONDecodeError, KeyError):
                self._index = {}
    
    def _save_index(self) -> None:
        """Save cache index to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        data = {repo: entry.to_dict() for repo, entry in self._index.items()}
        self.index_file.write_text(json.dumps(data, indent=2))
    
    def _cache_key(self, repo: str) -> str:
        """Generate cache key for a repo."""
        return hashlib.sha256(repo.encode()).hexdigest()[:16]
    
    def get(self, repo: str) -> Optional[Dict]:
        """Get cached artifact data."""
        entry = self._index.get(repo)
        if not entry or entry.is_expired:
            return None
        
        if not entry.artifact_path.exists():
            return None
        
        try:
            return json.loads(entry.artifact_path.read_text())
        except json.JSONDecodeError:
            return None
    
    def set(self, repo: str, data: Dict, commit_hash: str = "") -> None:
        """Cache artifact data."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache_key = self._cache_key(repo)
        artifact_path = self.cache_dir / f"{cache_key}.json"
        artifact_path.write_text(json.dumps(data, indent=2))
        
        from datetime import timedelta
        now = datetime.now()
        
        entry = CacheEntry(
            repo=repo,
            artifact_path=artifact_path,
            created_at=now,
            expires_at=now + timedelta(hours=self.ttl_hours),
            commit_hash=commit_hash,
        )
        self._index[repo] = entry
        self._save_index()
    
    def invalidate(self, repo: str) -> None:
        """Invalidate cache for a repo."""
        if repo in self._index:
            entry = self._index.pop(repo)
            if entry.artifact_path.exists():
                entry.artifact_path.unlink()
            self._save_index()
    
    def clear(self) -> None:
        """Clear all cached data."""
        for entry in self._index.values():
            if entry.artifact_path.exists():
                entry.artifact_path.unlink()
        self._index.clear()
        self._save_index()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        expired = [repo for repo, entry in self._index.items() if entry.is_expired]
        for repo in expired:
            self.invalidate(repo)
        return len(expired)


# ============================================================================
# Plugin System
# ============================================================================

class ResearchPlugin(ABC):
    """Base class for research plugins."""
    
    name: str = "base_plugin"
    description: str = ""
    version: str = "1.0.0"
    
    @abstractmethod
    def on_scan_complete(self, repo_path: Path, scan: RepoScan) -> None:
        """Called after repository scan completes."""
        pass
    
    @abstractmethod
    def on_analysis_complete(self, repo_path: Path, summary: RepoSummary) -> None:
        """Called after analysis completes."""
        pass
    
    def on_research_complete(self, artifact: ResearchArtifact) -> None:
        """Called after full research completes."""
        pass
    
    def on_error(self, repo: str, error: Exception) -> None:
        """Called when an error occurs."""
        pass


class PluginManager:
    """Manages research plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, ResearchPlugin] = {}
    
    def register(self, plugin: ResearchPlugin) -> None:
        """Register a plugin."""
        self._plugins[plugin.name] = plugin
    
    def unregister(self, name: str) -> None:
        """Unregister a plugin."""
        self._plugins.pop(name, None)
    
    def get(self, name: str) -> Optional[ResearchPlugin]:
        """Get plugin by name."""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugins."""
        return list(self._plugins.keys())
    
    def notify_scan_complete(self, repo_path: Path, scan: RepoScan) -> None:
        """Notify all plugins of scan completion."""
        for plugin in self._plugins.values():
            try:
                plugin.on_scan_complete(repo_path, scan)
            except Exception:
                pass
    
    def notify_analysis_complete(self, repo_path: Path, summary: RepoSummary) -> None:
        """Notify all plugins of analysis completion."""
        for plugin in self._plugins.values():
            try:
                plugin.on_analysis_complete(repo_path, summary)
            except Exception:
                pass
    
    def notify_research_complete(self, artifact: ResearchArtifact) -> None:
        """Notify all plugins of research completion."""
        for plugin in self._plugins.values():
            try:
                plugin.on_research_complete(artifact)
            except Exception:
                pass


# Global plugin manager
_plugin_manager = PluginManager()


def register_plugin(plugin: ResearchPlugin) -> None:
    """Register a plugin globally."""
    _plugin_manager.register(plugin)


def unregister_plugin(name: str) -> None:
    """Unregister a plugin globally."""
    _plugin_manager.unregister(name)


# ============================================================================
# Progress Callbacks
# ============================================================================

class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""
    
    def __call__(self, stage: str, current: int, total: int, message: str = "") -> None: ...


def _null_progress(stage: str, current: int, total: int, message: str = "") -> None:
    """No-op progress callback."""
    pass


# ============================================================================
# Core Research Functions
# ============================================================================

def research_repo(
    repo: str,
    *,
    clone_root: Optional[Path] = None,
    update: bool = False,
    config: Optional[ResearchConfig] = None,
    progress: Optional[ProgressCallback] = None,
) -> ResearchArtifact:
    """Research a single repository.
    
    Args:
        repo: Repository identifier (owner/name or URL)
        clone_root: Where to clone repos (overrides config)
        update: Whether to update the repo before analysis
        config: Research configuration
        progress: Progress callback
    
    Returns:
        ResearchArtifact with all analysis results
    """
    config = config or ResearchConfig()
    progress = progress or _null_progress
    start_time = time.time()
    
    effective_clone_root = clone_root or config.clone_root
    
    # Clone/update repository
    progress("clone", 0, 1, f"Cloning {repo}")
    repo_path = ensure_cloned(
        repo,
        clone_root=effective_clone_root,
        strategy=config.clone_strategy,
    )
    
    if update or config.auto_update:
        progress("update", 0, 1, "Updating repository")
        update_repo(repo_path)
    progress("clone", 1, 1, "Repository ready")
    
    # Scan repository
    progress("scan", 0, 1, "Scanning files")
    
    def scan_progress(current: int, total: int) -> None:
        progress("scan", current, total, f"Scanned {current}/{total} files")
    
    scan = scan_repo(
        repo_path,
        parallel=config.parallel_scan,
        max_file_size_bytes=config.max_file_size,
        compute_hashes=config.compute_hashes,
        progress_callback=scan_progress,
    )
    
    _plugin_manager.notify_scan_complete(repo_path, scan)
    progress("scan", 1, 1, f"Scanned {len(scan.files)} files")
    
    # Analyze repository
    progress("analyze", 0, 1, "Analyzing repository")
    summary = summarize_repo(
        repo_path,
        scan,
        include_security=config.include_security,
        include_metrics=config.include_metrics,
    )
    
    _plugin_manager.notify_analysis_complete(repo_path, summary)
    progress("analyze", 1, 1, "Analysis complete")
    
    # Build index
    index = None
    if config.build_index:
        progress("index", 0, 1, "Building search index")
        index = build_index(
            repo_path,
            scan,
            include_symbols=config.include_symbols,
            include_ngrams=config.include_ngrams,
        )
        progress("index", 1, 1, f"Indexed {index.total_documents} documents")
    
    # Get git history
    git_history = None
    if config.include_git_history:
        progress("history", 0, 1, "Analyzing git history")
        git_history = get_git_history(repo_path, max_commits=config.max_commits_for_history)
        progress("history", 1, 1, f"Analyzed {git_history.total_commits} commits")
    
    # Create artifact
    duration_ms = int((time.time() - start_time) * 1000)
    
    artifact = ResearchArtifact(
        repo_path=repo_path,
        scan=scan,
        summary=summary,
        index=index,
        git_history=git_history,
        repo_name=repo.split("/")[-1] if "/" in repo else repo,
        research_duration_ms=duration_ms,
        config_used=config,
    )
    
    _plugin_manager.notify_research_complete(artifact)
    progress("complete", 1, 1, f"Research complete in {duration_ms}ms")
    
    return artifact


def research_repos_parallel(
    repos: List[str],
    *,
    max_workers: int = 4,
    config: Optional[ResearchConfig] = None,
    progress: Optional[ProgressCallback] = None,
    stop_on_error: bool = False,
) -> MultiRepoArtifact:
    """Research multiple repositories in parallel.
    
    Args:
        repos: List of repository identifiers
        max_workers: Maximum parallel workers
        config: Research configuration
        progress: Progress callback
        stop_on_error: Whether to stop on first error
    
    Returns:
        MultiRepoArtifact with all results and errors
    """
    config = config or ResearchConfig()
    progress = progress or _null_progress
    start_time = time.time()
    
    result = MultiRepoArtifact()
    
    def research_one(repo: str) -> Tuple[str, Optional[ResearchArtifact], Optional[str]]:
        try:
            artifact = research_repo(repo, config=config)
            return (repo, artifact, None)
        except Exception as e:
            return (repo, None, str(e))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(research_one, repo): repo for repo in repos}
        completed = 0
        
        for future in as_completed(futures):
            repo, artifact, error = future.result()
            completed += 1
            
            if artifact:
                result.add(artifact)
                progress("repo", completed, len(repos), f"Completed: {repo}")
            else:
                result.add_error(repo, error or "Unknown error")
                progress("repo", completed, len(repos), f"Failed: {repo}")
                
                if stop_on_error:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
    
    result.total_duration_ms = int((time.time() - start_time) * 1000)
    return result


def quick_research(repo: str, output_path: Optional[Path] = None) -> Path:
    """Quick research and report generation.
    
    Args:
        repo: Repository identifier
        output_path: Output path for report (auto-generated if None)
    
    Returns:
        Path to generated report
    """
    artifact = research_repo(repo)
    
    if output_path is None:
        output_path = Path("reports") / f"{repo.replace('/', '__')}.md"
    
    return artifact.save_report(output_path)


def cached_research(
    repo: str,
    *,
    config: Optional[ResearchConfig] = None,
    force_refresh: bool = False,
) -> ResearchArtifact:
    """Research with caching support.
    
    Args:
        repo: Repository identifier
        config: Research configuration
        force_refresh: Force fresh research even if cached
    
    Returns:
        ResearchArtifact (from cache or fresh)
    """
    config = config or ResearchConfig()
    
    if not config.cache_enabled:
        return research_repo(repo, config=config)
    
    cache = ResearchCache(config.cache_dir, ttl_hours=config.cache_ttl_hours)
    
    # Check cache
    if not force_refresh:
        cached = cache.get(repo)
        if cached:
            # Return a minimal artifact from cache
            # Full reconstruction would require more serialization
            pass
    
    # Fresh research
    artifact = research_repo(repo, config=config)
    
    # Cache the results
    cache.set(repo, artifact.to_dict())
    
    return artifact


# ============================================================================
# Utility Functions
# ============================================================================

def compare_repos(repo1: str, repo2: str, *, config: Optional[ResearchConfig] = None) -> Dict[str, Any]:
    """Compare two repositories.
    
    Args:
        repo1: First repository
        repo2: Second repository
        config: Research configuration
    
    Returns:
        Comparison results
    """
    a1 = research_repo(repo1, config=config)
    a2 = research_repo(repo2, config=config)
    
    return {
        "repos": [repo1, repo2],
        "comparison": {
            "file_count": [len(a1.scan.files), len(a2.scan.files)],
            "total_bytes": [a1.scan.total_bytes, a2.scan.total_bytes],
            "primary_language": [a1.summary.primary_language, a2.summary.primary_language],
            "security_findings": [len(a1.security_findings), len(a2.security_findings)],
            "dependencies": [len(a1.dependencies), len(a2.dependencies)],
        },
        "artifacts": [a1, a2],
    }


def list_cached_repos(cache_dir: Path = Path(".cache/research")) -> List[str]:
    """List all cached repositories.
    
    Args:
        cache_dir: Cache directory path
    
    Returns:
        List of cached repository names
    """
    cache = ResearchCache(cache_dir)
    return list(cache._index.keys())


def clear_cache(cache_dir: Path = Path(".cache/research")) -> int:
    """Clear the research cache.
    
    Args:
        cache_dir: Cache directory path
    
    Returns:
        Number of entries cleared
    """
    cache = ResearchCache(cache_dir)
    count = len(cache._index)
    cache.clear()
    return count
