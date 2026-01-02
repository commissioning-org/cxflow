"""Repository scanning with advanced file analysis.

This module provides comprehensive file scanning capabilities including:
- Language detection and statistics
- Git metadata extraction
- File categorization and fingerprinting
- Parallel scanning for large repositories
- Content analysis and pattern detection
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from .ignore import IgnoreSpec, load_ignore_rules


# ============================================================================
# Constants
# ============================================================================

DEFAULT_IGNORE_DIRS: FrozenSet[str] = frozenset({
    ".git",
    "target",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "coverage",
    ".coverage",
    "htmlcov",
    ".eggs",
    ".sass-cache",
    ".cache",
    "vendor",
})

# Default ignore globs (applied in addition to DEFAULT_IGNORE_DIRS)
DEFAULT_IGNORE_PATTERNS: FrozenSet[str] = frozenset({
    "*.egg-info",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.min.js",
    "*.min.css",
    "*.map",
})

# Language detection by file extension
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    ".py": "python", ".pyi": "python", ".pyx": "python",
    ".rs": "rust",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hxx": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".m": "objective-c", ".mm": "objective-cpp",
    ".pl": "perl", ".pm": "perl",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".fish": "shell",
    ".lua": "lua",
    ".r": "r", ".R": "r",
    ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang", ".hrl": "erlang",
    ".hs": "haskell", ".lhs": "haskell",
    ".clj": "clojure", ".cljs": "clojure", ".cljc": "clojure",
    ".sql": "sql",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".vue": "vue", ".svelte": "svelte",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".xml": "xml",
    ".md": "markdown", ".rst": "restructuredtext", ".tex": "latex",
    ".dockerfile": "dockerfile",
}

# File type categories
FILE_CATEGORIES: Dict[str, FrozenSet[str]] = {
    "source": frozenset({
        ".py", ".rs", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".kt",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala",
    }),
    "config": frozenset({
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties", ".xml",
    }),
    "documentation": frozenset({".md", ".rst", ".txt", ".adoc", ".org", ".tex", ".pdf"}),
    "data": frozenset({".csv", ".tsv", ".sql", ".parquet", ".avro", ".jsonl"}),
    "web": frozenset({".html", ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte"}),
    "test": frozenset({"_test.py", "_test.go", "_test.rs", ".test.js", ".test.ts", ".spec.js", ".spec.ts"}),
    "build": frozenset({
        "Makefile", "CMakeLists.txt", "Cargo.toml", "package.json", "pyproject.toml",
        "setup.py", "setup.cfg", "pom.xml", "build.gradle", "build.gradle.kts",
    }),
}

# Binary file extensions to skip
BINARY_EXTENSIONS: FrozenSet[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".gz", ".tar", ".rar", ".7z", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".a", ".o", ".obj",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wav", ".flac",
    ".pyc", ".pyo", ".class", ".jar", ".war", ".lock", ".wasm",
})


# ============================================================================
# Data Classes
# ============================================================================

@dataclass(frozen=True)
class FileInfo:
    """Information about a single file in the repository."""
    path: str
    size_bytes: int
    language: Optional[str] = None
    category: Optional[str] = None
    is_binary: bool = False
    content_hash: Optional[str] = None
    line_count: Optional[int] = None
    last_modified: Optional[datetime] = None

    @property
    def extension(self) -> str:
        return Path(self.path).suffix.lower()

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def parent(self) -> str:
        return str(Path(self.path).parent)


@dataclass(frozen=True)
class LanguageStats:
    """Statistics for a programming language in the repository."""
    language: str
    file_count: int
    total_bytes: int
    total_lines: int
    percentage: float

    def to_dict(self) -> Dict:
        return {
            "language": self.language,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "total_lines": self.total_lines,
            "percentage": round(self.percentage, 2),
        }


@dataclass(frozen=True)
class GitMetadata:
    """Git metadata for the repository."""
    remote_url: Optional[str] = None
    current_branch: Optional[str] = None
    current_commit: Optional[str] = None
    commit_count: int = 0
    first_commit_date: Optional[datetime] = None
    last_commit_date: Optional[datetime] = None
    tags: Tuple[str, ...] = ()
    is_dirty: bool = False

    def to_dict(self) -> Dict:
        return {
            "remote_url": self.remote_url,
            "current_branch": self.current_branch,
            "current_commit": self.current_commit,
            "commit_count": self.commit_count,
            "first_commit_date": self.first_commit_date.isoformat() if self.first_commit_date else None,
            "last_commit_date": self.last_commit_date.isoformat() if self.last_commit_date else None,
            "tags": list(self.tags),
            "is_dirty": self.is_dirty,
        }


@dataclass
class RepoScan:
    """Complete scan results for a repository."""
    root: str
    files: List[FileInfo]
    total_bytes: int
    by_extension: Dict[str, int]
    by_language: Dict[str, LanguageStats] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    git_metadata: Optional[GitMetadata] = None
    scan_duration_ms: int = 0
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def source_files(self) -> List[FileInfo]:
        return [f for f in self.files if f.category == "source"]

    @property
    def test_files(self) -> List[FileInfo]:
        return [f for f in self.files if f.category == "test" or "test" in f.path.lower()]

    @property
    def config_files(self) -> List[FileInfo]:
        return [f for f in self.files if f.category == "config"]

    @property
    def primary_language(self) -> Optional[str]:
        if not self.by_language:
            return None
        return max(self.by_language.items(), key=lambda x: x[1].total_bytes)[0]

    def to_dict(self) -> Dict:
        return {
            "root": self.root,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "by_extension": self.by_extension,
            "by_language": {k: v.to_dict() for k, v in self.by_language.items()},
            "by_category": self.by_category,
            "git_metadata": self.git_metadata.to_dict() if self.git_metadata else None,
            "scan_duration_ms": self.scan_duration_ms,
            "primary_language": self.primary_language,
        }


# ============================================================================
# Language Detection
# ============================================================================

def detect_language(path: Union[str, Path]) -> Optional[str]:
    """Detect programming language from file path."""
    p = Path(path)
    ext = p.suffix.lower()
    name = p.name.lower()

    special_files = {
        "dockerfile": "dockerfile", "makefile": "makefile", "cmakelists.txt": "cmake",
        "rakefile": "ruby", "gemfile": "ruby", "podfile": "ruby", "vagrantfile": "ruby",
        ".gitignore": "gitignore", ".dockerignore": "dockerignore", ".editorconfig": "editorconfig",
        ".eslintrc": "json", ".prettierrc": "json", "package.json": "json", "tsconfig.json": "json",
        "cargo.toml": "toml", "pyproject.toml": "toml", "requirements.txt": "requirements", "pipfile": "toml",
    }

    if name in special_files:
        return special_files[name]
    return EXTENSION_TO_LANGUAGE.get(ext)


def categorize_file(path: Union[str, Path]) -> Optional[str]:
    """Categorize a file based on its path and extension."""
    p = Path(path)
    ext = p.suffix.lower()
    name = p.name.lower()
    path_str = str(path).lower()

    test_patterns = ["test", "spec", "_test", ".test", ".spec", "tests/", "__tests__/"]
    if any(pat in path_str for pat in test_patterns):
        return "test"

    if name in [n.lower() for n in FILE_CATEGORIES.get("build", set())]:
        return "build"

    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return None


def is_binary_file(path: Union[str, Path]) -> bool:
    """Check if a file is likely binary based on extension."""
    return Path(path).suffix.lower() in BINARY_EXTENSIONS


# ============================================================================
# File Reading
# ============================================================================

def read_text(root: Path, rel_path: str, *, max_chars: int = 200_000, encoding: str = "utf-8") -> str:
    """Read text content from a file with error handling."""
    p = root / rel_path
    try:
        data = p.read_bytes()
    except OSError as e:
        raise OSError(f"Failed to read {rel_path}: {e}") from e

    if data.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    elif data.startswith(b'\xff\xfe'):
        encoding = 'utf-16-le'
    elif data.startswith(b'\xfe\xff'):
        encoding = 'utf-16-be'

    text = data.decode(encoding, errors="ignore")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n[...truncated at {max_chars:,} chars...]\n"
    return text


def count_lines(content: str) -> int:
    """Count lines in text content."""
    if not content:
        return 0
    return content.count('\n') + (1 if not content.endswith('\n') else 0)


def compute_hash(content: bytes, algorithm: str = "sha256") -> str:
    """Compute hash of file content."""
    h = hashlib.new(algorithm)
    h.update(content)
    return h.hexdigest()


# ============================================================================
# Git Metadata Extraction
# ============================================================================

def _run_git(args: List[str], cwd: Path) -> Optional[str]:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args, cwd=str(cwd), capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def extract_git_metadata(repo_root: Path) -> Optional[GitMetadata]:
    """Extract Git metadata from repository."""
    if not (repo_root / ".git").exists():
        return None

    try:
        remote_url = _run_git(["remote", "get-url", "origin"], repo_root)
        current_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
        current_commit = _run_git(["rev-parse", "HEAD"], repo_root)

        commit_count_str = _run_git(["rev-list", "--count", "HEAD"], repo_root)
        commit_count = int(commit_count_str) if commit_count_str else 0

        first_date = last_date = None
        if commit_count > 0:
            first_ts = _run_git(["log", "--reverse", "--format=%ct", "-1"], repo_root)
            last_ts = _run_git(["log", "--format=%ct", "-1"], repo_root)
            if first_ts:
                first_date = datetime.fromtimestamp(int(first_ts))
            if last_ts:
                last_date = datetime.fromtimestamp(int(last_ts))

        tags_output = _run_git(["tag", "--list"], repo_root)
        tags = tuple(tags_output.splitlines()) if tags_output else ()

        status = _run_git(["status", "--porcelain"], repo_root)
        is_dirty = bool(status)

        return GitMetadata(
            remote_url=remote_url, current_branch=current_branch, current_commit=current_commit,
            commit_count=commit_count, first_commit_date=first_date, last_commit_date=last_date,
            tags=tags[:50], is_dirty=is_dirty,
        )
    except Exception:
        return None


# ============================================================================
# File Iteration
# ============================================================================

def iter_files(
    root: Path,
    *,
    ignore_dirs: Optional[Sequence[str]] = None,
    ignore_patterns: Optional[Sequence[str]] = None,
    respect_gitignore: bool = True,
    ignore_files: Sequence[str] = (".gitignore", ".research-agentignore"),
    max_file_size_bytes: int = 1_000_000,
    include_hidden: bool = False,
    file_filter: Optional[Callable[[Path], bool]] = None,
) -> Iterator[Path]:
    """Iterate over files in a repository."""
    ignore = set(ignore_dirs) if ignore_dirs else set(DEFAULT_IGNORE_DIRS)

    extra_patterns = list(ignore_patterns or [])
    # Always include a small set of safe defaults (noise reducers).
    extra_patterns.extend(sorted(DEFAULT_IGNORE_PATTERNS))

    rules = load_ignore_rules(root, ignore_files) if respect_gitignore else []
    spec = IgnoreSpec(root=root, rules=rules, extra_patterns=extra_patterns)

    for dirpath, dirnames, filenames in os.walk(root):
        # Ensure deterministic traversal for stable reports.
        dirnames.sort()
        filenames.sort()

        # Filter directories in-place so os.walk doesn't descend into ignored ones.
        kept_dirs: List[str] = []
        for d in dirnames:
            if d in ignore:
                continue
            if not include_hidden and d.startswith('.'):
                continue

            dp = Path(dirpath) / d
            if spec.is_ignored(dp, is_dir=True):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fn in filenames:
            if not include_hidden and fn.startswith('.'):
                continue

            p = Path(dirpath) / fn
            if spec.is_ignored(p, is_dir=False):
                continue
            if file_filter and not file_filter(p):
                continue

            try:
                st = p.stat()
            except OSError:
                continue

            if st.st_size <= 0 or st.st_size > max_file_size_bytes:
                continue
            yield p


# ============================================================================
# Repository Scanning
# ============================================================================

def _scan_single_file(
    root: Path, file_path: Path, *, compute_hashes: bool = False, count_file_lines: bool = True,
) -> Optional[FileInfo]:
    """Scan a single file and return FileInfo."""
    try:
        st = file_path.stat()
        rel_path = str(file_path.relative_to(root))

        language = detect_language(file_path)
        category = categorize_file(file_path)
        is_binary = is_binary_file(file_path)

        content_hash = None
        line_count = None

        if not is_binary and (compute_hashes or count_file_lines):
            try:
                content = file_path.read_bytes()
                if compute_hashes:
                    content_hash = compute_hash(content)
                if count_file_lines:
                    text = content.decode("utf-8", errors="ignore")
                    line_count = count_lines(text)
            except OSError:
                pass

        last_modified = None
        try:
            last_modified = datetime.fromtimestamp(st.st_mtime)
        except (OSError, ValueError):
            pass

        return FileInfo(
            path=rel_path, size_bytes=st.st_size, language=language, category=category,
            is_binary=is_binary, content_hash=content_hash, line_count=line_count, last_modified=last_modified,
        )
    except Exception:
        return None


def scan_repo(
    root: Path,
    *,
    ignore_dirs: Optional[Sequence[str]] = None,
    ignore_patterns: Optional[Sequence[str]] = None,
    respect_gitignore: bool = True,
    include_hidden: bool = False,
    max_file_size_bytes: int = 1_000_000,
    parallel: bool = True,
    max_workers: int = 0,
    compute_hashes: bool = False,
    count_lines_enabled: bool = True,
    include_git_metadata: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> RepoScan:
    """Scan a repository and collect comprehensive file information."""
    start_time = time.time()

    files: List[FileInfo] = []
    total_bytes = 0
    by_ext: Dict[str, int] = Counter()
    by_lang_bytes: Dict[str, int] = Counter()
    by_lang_files: Dict[str, int] = Counter()
    by_lang_lines: Dict[str, int] = Counter()
    by_category: Dict[str, int] = Counter()
    errors = 0
    warnings: List[str] = []

    # If max_workers isn't specified, scale sensibly with CPU count.
    if max_workers <= 0:
        cpu = os.cpu_count() or 4
        max_workers = min(32, max(4, cpu))

    file_paths = list(iter_files(
        root,
        ignore_dirs=ignore_dirs,
        ignore_patterns=ignore_patterns,
        respect_gitignore=respect_gitignore,
        include_hidden=include_hidden,
        max_file_size_bytes=max_file_size_bytes,
    ))
    total_files = len(file_paths)

    def process_file(idx: int, file_path: Path) -> Optional[FileInfo]:
        nonlocal errors
        fi = _scan_single_file(root, file_path, compute_hashes=compute_hashes, count_file_lines=count_lines_enabled)
        if progress_callback and idx % 100 == 0:
            progress_callback(idx, total_files)
        return fi

    if parallel and total_files > 100:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, i, fp): fp for i, fp in enumerate(file_paths)}
            for future in as_completed(futures):
                try:
                    fi = future.result()
                    if fi:
                        files.append(fi)
                except Exception as e:
                    errors += 1
                    warnings.append(f"Error processing file: {e}")
    else:
        for i, fp in enumerate(file_paths):
            fi = process_file(i, fp)
            if fi:
                files.append(fi)

    for fi in files:
        total_bytes += fi.size_bytes
        ext = fi.extension.lstrip('.') or "(noext)"
        by_ext[ext] += 1

        if fi.language:
            by_lang_bytes[fi.language] += fi.size_bytes
            by_lang_files[fi.language] += 1
            if fi.line_count:
                by_lang_lines[fi.language] += fi.line_count

        if fi.category:
            by_category[fi.category] += 1

    by_language: Dict[str, LanguageStats] = {}
    total_lang_bytes = sum(by_lang_bytes.values()) or 1
    for lang in by_lang_bytes:
        by_language[lang] = LanguageStats(
            language=lang, file_count=by_lang_files[lang], total_bytes=by_lang_bytes[lang],
            total_lines=by_lang_lines[lang], percentage=(by_lang_bytes[lang] / total_lang_bytes) * 100,
        )

    git_metadata = extract_git_metadata(root) if include_git_metadata else None

    files.sort(key=lambda f: (f.path.count("/"), f.path))
    scan_duration = int((time.time() - start_time) * 1000)

    return RepoScan(
        root=str(root), files=files, total_bytes=total_bytes,
        by_extension=dict(sorted(by_ext.items(), key=lambda x: -x[1])),
        by_language=dict(sorted(by_language.items(), key=lambda x: -x[1].total_bytes)),
        by_category=dict(sorted(by_category.items(), key=lambda x: -x[1])),
        git_metadata=git_metadata, scan_duration_ms=scan_duration, error_count=errors, warnings=warnings[:100],
    )


# ============================================================================
# Advanced Scanning Utilities
# ============================================================================

def find_files_by_pattern(
    root: Path, pattern: str, *, ignore_case: bool = True, include_content: bool = False, max_results: int = 100,
) -> List[Tuple[str, Optional[str]]]:
    """Find files matching a regex pattern."""
    flags = re.IGNORECASE if ignore_case else 0
    rx = re.compile(pattern, flags)
    results: List[Tuple[str, Optional[str]]] = []

    for fp in iter_files(root):
        if len(results) >= max_results:
            break

        rel_path = str(fp.relative_to(root))
        if rx.search(fp.name):
            content = None
            if include_content:
                try:
                    content = read_text(root, rel_path, max_chars=1000)
                except OSError:
                    pass
            results.append((rel_path, content))
    return results


def find_duplicate_files(scan: RepoScan, root: Path, *, min_size: int = 100) -> Dict[str, List[str]]:
    """Find duplicate files based on content hash."""
    hash_to_files: Dict[str, List[str]] = {}
    for fi in scan.files:
        if fi.content_hash and fi.size_bytes >= min_size:
            if fi.content_hash not in hash_to_files:
                hash_to_files[fi.content_hash] = []
            hash_to_files[fi.content_hash].append(fi.path)
    return {h: paths for h, paths in hash_to_files.items() if len(paths) > 1}


def get_largest_files(scan: RepoScan, *, top_n: int = 20, category: Optional[str] = None) -> List[FileInfo]:
    """Get the largest files in the repository."""
    files = scan.files
    if category:
        files = [f for f in files if f.category == category]
    return sorted(files, key=lambda f: -f.size_bytes)[:top_n]


def get_recently_modified(scan: RepoScan, *, top_n: int = 20) -> List[FileInfo]:
    """Get the most recently modified files."""
    files_with_dates = [f for f in scan.files if f.last_modified]
    return sorted(files_with_dates, key=lambda f: f.last_modified or datetime.min, reverse=True)[:top_n]
