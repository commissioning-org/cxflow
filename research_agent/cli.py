"""Enhanced CLI with rich features and improved UX.

This module provides a comprehensive command-line interface including:
- Multiple commands for different research workflows
- Progress indicators and colored output
- Configuration file support
- Interactive mode
- Batch processing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, TextIO

from .analysis import summarize_repo, scan_security_issues, extract_dependencies, Severity
from .indexer import build_index
from .repo_ops import (
    ensure_cloned,
    update_repo,
    get_git_history,
    get_contributors,
    get_branches,
    CloneStrategy,
    MergeStrategy,
)
from .reporting import (
    render_report,
    write_report,
    export_json,
    export_html,
    export_csv,
    write_multi_format,
    ReportFormat,
    ReportLevel,
)
from .scanner import scan_repo


# ============================================================================
# Constants and Configuration
# ============================================================================

VERSION = "2.0.0"
PROG_NAME = "research-agent"

# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @classmethod
    def disable(cls):
        """Disable all colors."""
        for attr in dir(cls):
            if not attr.startswith('_') and attr.isupper():
                setattr(cls, attr, "")


# Check if colors should be disabled
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    Colors.disable()


# ============================================================================
# Output Helpers
# ============================================================================

def _print(msg: str = "", *, file: TextIO = sys.stdout, end: str = "\n") -> None:
    """Print with optional color support."""
    print(msg, file=file, end=end)


def _info(msg: str) -> None:
    """Print info message."""
    _print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def _success(msg: str) -> None:
    """Print success message."""
    _print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def _warning(msg: str) -> None:
    """Print warning message."""
    _print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    """Print error message."""
    _print(f"{Colors.RED}✗{Colors.RESET} {msg}", file=sys.stderr)


def _header(msg: str) -> None:
    """Print header message."""
    _print(f"\n{Colors.BOLD}{Colors.CYAN}{msg}{Colors.RESET}")
    _print(f"{Colors.DIM}{'─' * len(msg)}{Colors.RESET}")


def _progress(current: int, total: int, prefix: str = "") -> None:
    """Print progress bar."""
    if total == 0:
        return
    pct = current / total
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    _print(f"\r{prefix}[{bar}] {pct*100:.0f}% ({current}/{total})", end="")
    if current >= total:
        _print()  # New line when complete


def _table(headers: List[str], rows: List[List[str]], *, max_width: int = 80) -> None:
    """Print a simple table."""
    if not rows:
        return

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Print header
    header_row = " │ ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    _print(f"{Colors.BOLD}{header_row}{Colors.RESET}")
    _print("─" * len(header_row))

    # Print rows
    for row in rows:
        row_str = " │ ".join(str(c).ljust(widths[i]) for i, c in enumerate(row) if i < len(widths))
        _print(row_str)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class Config:
    """CLI configuration."""
    clone_root: Path = Path(".repos")
    reports_dir: Path = Path("reports")
    default_format: ReportFormat = ReportFormat.MARKDOWN
    default_level: ReportLevel = ReportLevel.STANDARD
    parallel_scan: bool = True
    include_security: bool = True
    include_metrics: bool = True
    max_file_size: int = 1_000_000
    max_workers: int = 0
    include_hidden: bool = False
    respect_gitignore: bool = True
    ignore_patterns: List[str] = None  # populated in __post_init__
    verbose: bool = False
    quiet: bool = False
    no_color: bool = False

    def __post_init__(self) -> None:
        if self.ignore_patterns is None:
            self.ignore_patterns = []

    @classmethod
    def from_file(cls, path: Path) -> 'Config':
        """Load configuration from file."""
        if not path.exists():
            return cls()

        try:
            data = json.loads(path.read_text())
            return cls(
                clone_root=Path(data.get("clone_root", ".repos")),
                reports_dir=Path(data.get("reports_dir", "reports")),
                parallel_scan=data.get("parallel_scan", True),
                include_security=data.get("include_security", True),
                include_metrics=data.get("include_metrics", True),
                max_file_size=data.get("max_file_size", 1_000_000),
                max_workers=int(data.get("max_workers", 0) or 0),
                include_hidden=bool(data.get("include_hidden", False)),
                respect_gitignore=bool(data.get("respect_gitignore", True)),
                ignore_patterns=list(data.get("ignore_patterns", []) or []),
                verbose=data.get("verbose", False),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()

    def to_file(self, path: Path) -> None:
        """Save configuration to file."""
        data = {
            "clone_root": str(self.clone_root),
            "reports_dir": str(self.reports_dir),
            "parallel_scan": self.parallel_scan,
            "include_security": self.include_security,
            "include_metrics": self.include_metrics,
            "max_file_size": self.max_file_size,
            "max_workers": self.max_workers,
            "include_hidden": self.include_hidden,
            "respect_gitignore": self.respect_gitignore,
            "ignore_patterns": self.ignore_patterns,
            "verbose": self.verbose,
        }
        path.write_text(json.dumps(data, indent=2))


def _load_config(args: argparse.Namespace) -> Config:
    """Load configuration from file and command-line args."""
    config_path = Path(args.config) if hasattr(args, 'config') and args.config else Path(".research-agent.json")
    config = Config.from_file(config_path)

    # Override with command-line args
    if hasattr(args, 'clone_root') and args.clone_root:
        config.clone_root = Path(args.clone_root)
    if hasattr(args, 'verbose') and args.verbose:
        config.verbose = True
    if hasattr(args, 'quiet') and args.quiet:
        config.quiet = True
    if hasattr(args, 'no_color') and args.no_color:
        config.no_color = True
        Colors.disable()

    if hasattr(args, 'max_workers') and args.max_workers is not None:
        config.max_workers = int(args.max_workers)
    if hasattr(args, 'include_hidden') and args.include_hidden:
        config.include_hidden = True
    if hasattr(args, 'no_gitignore') and args.no_gitignore:
        config.respect_gitignore = False
    if hasattr(args, 'ignore') and args.ignore:
        # Allow repeating --ignore; keep existing config ignores too.
        config.ignore_patterns.extend(list(args.ignore))

    return config


# ============================================================================
# Path Helpers
# ============================================================================

def _default_out(repo: str, ext: str = ".md") -> Path:
    """Generate default output path for a repo."""
    return Path("reports") / (repo.replace("/", "__") + ext)


def _ensure_repo(args: argparse.Namespace, config: Config) -> Path:
    """Clone or locate repository."""
    if not config.quiet:
        _info(f"Ensuring repository: {args.repo}")

    start = time.time()
    repo_path = ensure_cloned(args.repo, clone_root=config.clone_root)

    if hasattr(args, 'update') and args.update:
        if not config.quiet:
            _info("Updating repository...")
        update_repo(repo_path)

    elapsed = time.time() - start
    if config.verbose:
        _success(f"Repository ready at {repo_path} ({elapsed:.1f}s)")

    return repo_path


# ============================================================================
# Commands
# ============================================================================

def cmd_clone(args: argparse.Namespace) -> int:
    """Clone a repository."""
    config = _load_config(args)

    try:
        repo_path = ensure_cloned(
            args.repo,
            clone_root=config.clone_root,
            strategy=CloneStrategy.SHALLOW if args.shallow else CloneStrategy.FULL,
            branch=args.branch if hasattr(args, 'branch') else None,
        )

        if args.update:
            _info("Updating repository...")
            update_repo(repo_path)

        _success(f"Repository cloned to: {repo_path}")
        print(str(repo_path))
        return 0

    except Exception as e:
        _error(f"Failed to clone repository: {e}")
        return 1


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a comprehensive report."""
    config = _load_config(args)

    try:
        repo_path = _ensure_repo(args, config)

        # Scan repository
        _header("Scanning Repository")
        start = time.time()

        def progress_cb(current: int, total: int) -> None:
            if not config.quiet:
                _progress(current, total, "Scanning: ")

        scan = scan_repo(
            repo_path,
            parallel=config.parallel_scan,
            max_file_size_bytes=config.max_file_size,
            max_workers=config.max_workers,
            include_hidden=config.include_hidden,
            respect_gitignore=config.respect_gitignore,
            ignore_patterns=config.ignore_patterns,
            progress_callback=progress_cb if not config.quiet else None,
        )

        scan_time = time.time() - start
        if not config.quiet:
            _success(f"Scanned {len(scan.files)} files in {scan_time:.1f}s")

        # Analyze repository
        _header("Analyzing Repository")
        summary = summarize_repo(
            repo_path,
            scan,
            include_security=config.include_security and not args.no_security,
            include_metrics=config.include_metrics and not args.no_metrics,
        )

        # Determine output format
        formats = []
        if args.format:
            formats = [ReportFormat(f) for f in args.format.split(",")]
        else:
            formats = [config.default_format]

        # Generate reports
        _header("Generating Report")

        if args.out:
            base_path = Path(args.out).with_suffix("")
        else:
            base_path = _default_out(args.repo, "")

        level = ReportLevel(args.level) if args.level else config.default_level

        if len(formats) == 1:
            fmt = formats[0]
            if fmt == ReportFormat.MARKDOWN:
                content = render_report(summary, scan, title=args.title, level=level)
                out_path = base_path.with_suffix(".md")
            elif fmt == ReportFormat.JSON:
                content = export_json(summary, scan, include_files=args.include_files)
                out_path = base_path.with_suffix(".json")
            elif fmt == ReportFormat.HTML:
                content = export_html(summary, scan, title=args.title)
                out_path = base_path.with_suffix(".html")
            elif fmt == ReportFormat.CSV:
                content = export_csv(scan, include_all_fields=True)
                out_path = base_path.with_suffix(".csv")
            else:
                content = render_report(summary, scan, title=args.title, level=level)
                out_path = base_path.with_suffix(".md")

            write_report(out_path, content)
            _success(f"Report written to: {out_path}")
            print(str(out_path))
        else:
            outputs = write_multi_format(summary, scan, base_path, formats=formats, title=args.title)
            for fmt, path in outputs.items():
                _success(f"{fmt.value.upper()}: {path}")
            print(str(list(outputs.values())[0]))

        # Print summary
        if config.verbose and not config.quiet:
            _header("Summary")
            _print(f"  Files: {len(scan.files)}")
            _print(f"  Size: {scan.total_bytes / 1024 / 1024:.1f} MB")
            if summary.primary_language:
                _print(f"  Primary Language: {summary.primary_language}")
            if summary.code_metrics:
                _print(f"  Code Quality: {summary.code_metrics.grade} ({summary.code_metrics.maintainability_index:.0f}/100)")
            if summary.security_findings:
                _print(f"  Security Findings: {len(summary.security_findings)}")
            _print(f"  Documentation Score: {summary.documentation_score:.0f}/100")

        return 0

    except Exception as e:
        _error(f"Failed to generate report: {e}")
        if config.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    """Search within a repository."""
    config = _load_config(args)

    try:
        repo_path = _ensure_repo(args, config)

        # Scan and build index
        if not config.quiet:
            _info("Building search index...")

        scan = scan_repo(
            repo_path,
            parallel=config.parallel_scan,
            max_workers=config.max_workers,
            include_hidden=config.include_hidden,
            respect_gitignore=config.respect_gitignore,
            ignore_patterns=config.ignore_patterns,
        )
        index = build_index(repo_path, scan, include_symbols=True, include_ngrams=True)

        if not config.quiet:
            _info(f"Indexed {len(index.token_to_matches)} tokens from {index.total_documents} files")

        # Search
        results = index.search(
            args.query,
            max_results=args.max_results,
            use_fuzzy=args.fuzzy if hasattr(args, 'fuzzy') else False,
        )

        if not results:
            _warning("No results found")
            return 0

        # Display results
        _header(f"Search Results ({len(results)} matches)")
        for r in results:
            m = r.match
            score_str = f" [{r.score:.2f}]" if config.verbose else ""
            _print(f"{Colors.CYAN}{m.path}{Colors.RESET}:{Colors.YELLOW}{m.line_no}{Colors.RESET}{score_str}")
            _print(f"  {Colors.DIM}{m.line[:100]}{Colors.RESET}")

        return 0

    except Exception as e:
        _error(f"Search failed: {e}")
        return 1


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan a repository without generating a full report."""
    config = _load_config(args)

    try:
        repo_path = _ensure_repo(args, config)

        _header("Scanning Repository")
        scan = scan_repo(
            repo_path,
            parallel=config.parallel_scan,
            compute_hashes=args.hashes if hasattr(args, 'hashes') else False,
            max_file_size_bytes=config.max_file_size,
            max_workers=config.max_workers,
            include_hidden=config.include_hidden,
            respect_gitignore=config.respect_gitignore,
            ignore_patterns=config.ignore_patterns,
        )

        _success(f"Scanned {len(scan.files)} files")

        # Display statistics
        _print(f"\n{Colors.BOLD}Statistics:{Colors.RESET}")
        _print(f"  Total Files: {len(scan.files)}")
        _print(f"  Total Size: {scan.total_bytes / 1024 / 1024:.2f} MB")
        _print(f"  Scan Time: {scan.scan_duration_ms}ms")

        if scan.primary_language:
            _print(f"  Primary Language: {scan.primary_language}")

        # Top languages
        if scan.by_language:
            _print(f"\n{Colors.BOLD}Top Languages:{Colors.RESET}")
            headers = ["Language", "Files", "Lines", "Percentage"]
            rows = []
            for lang, stats in list(scan.by_language.items())[:10]:
                rows.append([lang, str(stats.file_count), str(stats.total_lines), f"{stats.percentage:.1f}%"])
            _table(headers, rows)

        # Output JSON if requested
        if hasattr(args, 'json') and args.json:
            print(json.dumps(scan.to_dict(), indent=2))

        return 0

    except Exception as e:
        _error(f"Scan failed: {e}")
        return 1


def cmd_security(args: argparse.Namespace) -> int:
    """Run security analysis."""
    config = _load_config(args)

    try:
        repo_path = _ensure_repo(args, config)

        _header("Security Analysis")
        scan = scan_repo(
            repo_path,
            parallel=config.parallel_scan,
            max_workers=config.max_workers,
            include_hidden=config.include_hidden,
            respect_gitignore=config.respect_gitignore,
            ignore_patterns=config.ignore_patterns,
        )

        severity_threshold = Severity(args.severity) if hasattr(args, 'severity') and args.severity else Severity.LOW

        findings = scan_security_issues(
            repo_path,
            scan,
            severity_threshold=severity_threshold,
            max_findings=args.max_findings if hasattr(args, 'max_findings') else 500,
        )

        if not findings:
            _success("No security issues detected!")
            return 0

        # Group by severity
        by_severity: Dict[Severity, List] = {}
        for f in findings:
            if f.severity not in by_severity:
                by_severity[f.severity] = []
            by_severity[f.severity].append(f)

        # Display findings
        severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        for sev in severity_order:
            sev_findings = by_severity.get(sev, [])
            if not sev_findings:
                continue

            color = {
                Severity.CRITICAL: Colors.RED,
                Severity.HIGH: Colors.YELLOW,
                Severity.MEDIUM: Colors.YELLOW,
                Severity.LOW: Colors.CYAN,
                Severity.INFO: Colors.DIM,
            }.get(sev, Colors.RESET)

            _print(f"\n{color}{Colors.BOLD}{sev.value.upper()} ({len(sev_findings)}){Colors.RESET}")

            for f in sev_findings[:20]:
                _print(f"  {f.file_path}:{f.line_number}")
                _print(f"    {Colors.DIM}{f.message}{Colors.RESET}")

            if len(sev_findings) > 20:
                _print(f"  ... and {len(sev_findings) - 20} more")

        _print(f"\n{Colors.BOLD}Total: {len(findings)} findings{Colors.RESET}")

        # Output JSON if requested
        if hasattr(args, 'json') and args.json:
            out_data = [f.to_dict() for f in findings]
            if args.out:
                Path(args.out).write_text(json.dumps(out_data, indent=2))
                _success(f"Results written to: {args.out}")
            else:
                print(json.dumps(out_data, indent=2))

        return 0

    except Exception as e:
        _error(f"Security scan failed: {e}")
        return 1


def cmd_history(args: argparse.Namespace) -> int:
    """Analyze git history."""
    config = _load_config(args)

    try:
        repo_path = _ensure_repo(args, config)

        _header("Git History Analysis")
        history = get_git_history(
            repo_path,
            max_commits=args.max_commits if hasattr(args, 'max_commits') else 1000,
        )

        _print(f"\n{Colors.BOLD}Repository History:{Colors.RESET}")
        _print(f"  Total Commits: {history.total_commits}")
        _print(f"  Contributors: {history.contributor_count}")
        _print(f"  First Commit: {history.first_commit_date}")
        _print(f"  Last Commit: {history.last_commit_date}")
        _print(f"  Duration: {history.duration_days} days")
        _print(f"  Commits/Day: {history.commits_per_day:.2f}")

        # Top contributors
        if history.contributors:
            _print(f"\n{Colors.BOLD}Top Contributors:{Colors.RESET}")
            headers = ["Name", "Commits", "First", "Last"]
            rows = []
            sorted_contribs = sorted(history.contributors.values(), key=lambda c: -c.commit_count)
            for contrib in sorted_contribs[:10]:
                first = contrib.first_commit.strftime("%Y-%m-%d") if contrib.first_commit else "N/A"
                last = contrib.last_commit.strftime("%Y-%m-%d") if contrib.last_commit else "N/A"
                rows.append([contrib.name, str(contrib.commit_count), first, last])
            _table(headers, rows)

        # Most active files
        if history.most_active_files:
            _print(f"\n{Colors.BOLD}Most Changed Files:{Colors.RESET}")
            for path, count in history.most_active_files[:10]:
                _print(f"  {count:4d} changes: {path}")

        # Output JSON if requested
        if hasattr(args, 'json') and args.json:
            print(json.dumps(history.to_dict(), indent=2))

        return 0

    except Exception as e:
        _error(f"History analysis failed: {e}")
        return 1


def cmd_deps(args: argparse.Namespace) -> int:
    """Analyze dependencies."""
    config = _load_config(args)

    try:
        repo_path = _ensure_repo(args, config)

        _header("Dependency Analysis")
        scan = scan_repo(
            repo_path,
            parallel=config.parallel_scan,
            max_workers=config.max_workers,
            include_hidden=config.include_hidden,
            respect_gitignore=config.respect_gitignore,
            ignore_patterns=config.ignore_patterns,
        )
        deps = extract_dependencies(repo_path, scan)

        if not deps:
            _warning("No dependencies detected")
            return 0

        # Group by type
        by_type: Dict[str, List] = {}
        for d in deps:
            key = d.dep_type.value
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(d)

        for dep_type, type_deps in by_type.items():
            _print(f"\n{Colors.BOLD}{dep_type.upper()} ({len(type_deps)}){Colors.RESET}")
            for d in type_deps[:30]:
                version = f" {Colors.DIM}({d.version}){Colors.RESET}" if d.version else ""
                _print(f"  {d.name}{version}")
            if len(type_deps) > 30:
                _print(f"  ... and {len(type_deps) - 30} more")

        _print(f"\n{Colors.BOLD}Total: {len(deps)} dependencies{Colors.RESET}")

        # Output JSON if requested
        if hasattr(args, 'json') and args.json:
            out_data = [d.to_dict() for d in deps]
            print(json.dumps(out_data, indent=2))

        return 0

    except Exception as e:
        _error(f"Dependency analysis failed: {e}")
        return 1


def cmd_config(args: argparse.Namespace) -> int:
    """Manage configuration."""
    config_path = Path(args.path) if hasattr(args, 'path') and args.path else Path(".research-agent.json")

    if args.action == "show":
        config = Config.from_file(config_path)
        _print(json.dumps({
            "clone_root": str(config.clone_root),
            "reports_dir": str(config.reports_dir),
            "parallel_scan": config.parallel_scan,
            "include_security": config.include_security,
            "include_metrics": config.include_metrics,
            "max_file_size": config.max_file_size,
            "max_workers": config.max_workers,
            "include_hidden": config.include_hidden,
            "respect_gitignore": config.respect_gitignore,
            "ignore_patterns": config.ignore_patterns,
            "verbose": config.verbose,
        }, indent=2))

    elif args.action == "init":
        config = Config()
        config.to_file(config_path)
        _success(f"Configuration initialized at: {config_path}")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version information."""
    _print(f"{Colors.BOLD}Research Agent{Colors.RESET} v{VERSION}")
    _print("An automated tool for analyzing GitHub repositories")
    return 0


# ============================================================================
# Main Parser
# ============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    p = argparse.ArgumentParser(
        prog=PROG_NAME,
        description="Automated research agent for analyzing GitHub repositories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s report owner/repo              Generate a Markdown report
  %(prog)s report owner/repo --format json,html  Generate multiple formats
  %(prog)s search owner/repo "search query"      Search the codebase
  %(prog)s security owner/repo            Run security analysis
  %(prog)s history owner/repo             Analyze git history
        """,
    )

    # Global options
    p.add_argument("--version", "-V", action="store_true", help="Show version and exit")
    p.add_argument("--clone-root", default=None, help="Directory for cloned repos (default: .repos)")
    p.add_argument("--config", default=None, help="Path to config file")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    p.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output")
    p.add_argument("--no-color", action="store_true", help="Disable colored output")

    # Scan behavior (applies to commands that scan repositories)
    p.add_argument("--max-workers", type=int, default=None, help="Max scan workers (0=auto)")
    p.add_argument("--include-hidden", action="store_true", help="Include dotfiles and dot-directories")
    p.add_argument("--no-gitignore", action="store_true", help="Ignore .gitignore/.research-agentignore")
    p.add_argument(
        "--ignore",
        action="append",
        default=None,
        help="Extra ignore glob (repeatable). Example: --ignore '*.lock'",
    )

    sub = p.add_subparsers(dest="cmd", metavar="command")

    # Clone command
    p_clone = sub.add_parser("clone", help="Clone a repository")
    p_clone.add_argument("repo", help="Repository (owner/name or URL)")
    p_clone.add_argument("--update", "-u", action="store_true", help="Update after cloning")
    p_clone.add_argument("--shallow", action="store_true", help="Shallow clone (--depth 1)")
    p_clone.add_argument("--branch", "-b", help="Branch to clone")
    p_clone.set_defaults(func=cmd_clone)

    # Report command
    p_report = sub.add_parser("report", help="Generate a comprehensive report")
    p_report.add_argument("repo", help="Repository (owner/name or URL)")
    p_report.add_argument("--update", "-u", action="store_true", help="Update before analysis")
    p_report.add_argument("--out", "-o", help="Output file path")
    p_report.add_argument("--title", "-t", help="Report title")
    p_report.add_argument("--format", "-f", help="Output format(s): markdown,json,html,csv")
    p_report.add_argument("--level", "-l", choices=["summary", "standard", "detailed", "full"],
                          default="standard", help="Report detail level")
    p_report.add_argument("--no-security", action="store_true", help="Skip security analysis")
    p_report.add_argument("--no-metrics", action="store_true", help="Skip code metrics")
    p_report.add_argument("--include-files", action="store_true", help="Include file list in JSON")
    p_report.set_defaults(func=cmd_report)

    # Search command
    p_search = sub.add_parser("search", help="Search within a repository")
    p_search.add_argument("repo", help="Repository (owner/name or URL)")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--update", "-u", action="store_true", help="Update before search")
    p_search.add_argument("--max-results", "-n", type=int, default=30, help="Maximum results")
    p_search.add_argument("--fuzzy", action="store_true", help="Enable fuzzy matching")
    p_search.set_defaults(func=cmd_search)

    # Scan command
    p_scan = sub.add_parser("scan", help="Scan repository structure")
    p_scan.add_argument("repo", help="Repository (owner/name or URL)")
    p_scan.add_argument("--update", "-u", action="store_true", help="Update before scan")
    p_scan.add_argument("--hashes", action="store_true", help="Compute file hashes")
    p_scan.add_argument("--json", action="store_true", help="Output as JSON")
    p_scan.set_defaults(func=cmd_scan)

    # Security command
    p_security = sub.add_parser("security", help="Run security analysis")
    p_security.add_argument("repo", help="Repository (owner/name or URL)")
    p_security.add_argument("--update", "-u", action="store_true", help="Update before scan")
    p_security.add_argument("--severity", "-s", choices=["critical", "high", "medium", "low", "info"],
                            default="low", help="Minimum severity threshold")
    p_security.add_argument("--max-findings", type=int, default=500, help="Maximum findings")
    p_security.add_argument("--json", action="store_true", help="Output as JSON")
    p_security.add_argument("--out", "-o", help="Output file for JSON")
    p_security.set_defaults(func=cmd_security)

    # History command
    p_history = sub.add_parser("history", help="Analyze git history")
    p_history.add_argument("repo", help="Repository (owner/name or URL)")
    p_history.add_argument("--update", "-u", action="store_true", help="Update before analysis")
    p_history.add_argument("--max-commits", type=int, default=1000, help="Maximum commits to analyze")
    p_history.add_argument("--json", action="store_true", help="Output as JSON")
    p_history.set_defaults(func=cmd_history)

    # Dependencies command
    p_deps = sub.add_parser("deps", help="Analyze dependencies")
    p_deps.add_argument("repo", help="Repository (owner/name or URL)")
    p_deps.add_argument("--update", "-u", action="store_true", help="Update before analysis")
    p_deps.add_argument("--json", action="store_true", help="Output as JSON")
    p_deps.set_defaults(func=cmd_deps)

    # Config command
    p_config = sub.add_parser("config", help="Manage configuration")
    p_config.add_argument("action", choices=["show", "init"], help="Config action")
    p_config.add_argument("--path", help="Config file path")
    p_config.set_defaults(func=cmd_config)

    # Parse arguments
    args = p.parse_args(argv)

    # Handle version flag
    if args.version:
        return cmd_version(args)

    # Require a command
    if not args.cmd:
        p.print_help()
        return 0

    # Execute command
    return args.func(args)
