"""Repository operations with advanced git features.

This module provides comprehensive git repository operations including:
- Clone and update operations with multiple strategies
- Git history and commit analysis
- Contributor statistics
- Branch management
- Diff generation and analysis
- Async-ready architecture
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)


# ============================================================================
# Enums and Constants
# ============================================================================

class CloneStrategy(Enum):
    """Strategy for cloning repositories."""
    GH_CLI = "gh"  # Use GitHub CLI
    GIT_HTTPS = "git-https"  # Use git with HTTPS
    GIT_SSH = "git-ssh"  # Use git with SSH
    SHALLOW = "shallow"  # Shallow clone (--depth 1)
    FULL = "full"  # Full clone with history


class MergeStrategy(Enum):
    """Strategy for updating repositories."""
    FAST_FORWARD = "ff-only"
    MERGE = "merge"
    REBASE = "rebase"
    RESET = "reset"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution."""
    argv: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int = 0

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> Dict:
        return {
            "command": " ".join(self.argv),
            "returncode": self.returncode,
            "stdout": self.stdout[:1000],
            "stderr": self.stderr[:1000],
            "success": self.success,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class CommitInfo:
    """Information about a git commit."""
    sha: str
    short_sha: str
    author_name: str
    author_email: str
    date: datetime
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0

    def to_dict(self) -> Dict:
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "date": self.date.isoformat(),
            "message": self.message[:200],
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
        }


@dataclass
class ContributorStats:
    """Statistics for a contributor."""
    name: str
    email: str
    commit_count: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    files_touched: Set[str] = field(default_factory=set)
    first_commit: Optional[datetime] = None
    last_commit: Optional[datetime] = None
    commits_by_month: Dict[str, int] = field(default_factory=Counter)

    @property
    def file_count(self) -> int:
        return len(self.files_touched)

    @property
    def active_months(self) -> int:
        return len(self.commits_by_month)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "email": self.email,
            "commit_count": self.commit_count,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "file_count": self.file_count,
            "first_commit": self.first_commit.isoformat() if self.first_commit else None,
            "last_commit": self.last_commit.isoformat() if self.last_commit else None,
            "active_months": self.active_months,
        }


@dataclass
class GitHistory:
    """Git history analysis results."""
    commits: List[CommitInfo]
    contributors: Dict[str, ContributorStats]
    total_commits: int = 0
    total_insertions: int = 0
    total_deletions: int = 0
    commits_by_day: Dict[str, int] = field(default_factory=Counter)
    commits_by_hour: Dict[int, int] = field(default_factory=Counter)
    commits_by_weekday: Dict[int, int] = field(default_factory=Counter)
    most_active_files: List[Tuple[str, int]] = field(default_factory=list)
    first_commit_date: Optional[datetime] = None
    last_commit_date: Optional[datetime] = None

    @property
    def contributor_count(self) -> int:
        return len(self.contributors)

    @property
    def duration_days(self) -> int:
        if self.first_commit_date and self.last_commit_date:
            return (self.last_commit_date - self.first_commit_date).days
        return 0

    @property
    def commits_per_day(self) -> float:
        if self.duration_days > 0:
            return self.total_commits / self.duration_days
        return 0.0

    def to_dict(self) -> Dict:
        return {
            "total_commits": self.total_commits,
            "contributor_count": self.contributor_count,
            "total_insertions": self.total_insertions,
            "total_deletions": self.total_deletions,
            "first_commit_date": self.first_commit_date.isoformat() if self.first_commit_date else None,
            "last_commit_date": self.last_commit_date.isoformat() if self.last_commit_date else None,
            "duration_days": self.duration_days,
            "commits_per_day": round(self.commits_per_day, 2),
            "most_active_files": self.most_active_files[:20],
            "commits_by_weekday": dict(self.commits_by_weekday),
        }


@dataclass(frozen=True)
class BranchInfo:
    """Information about a git branch."""
    name: str
    is_current: bool = False
    is_remote: bool = False
    tracking: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    last_commit_sha: Optional[str] = None
    last_commit_date: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "is_current": self.is_current,
            "is_remote": self.is_remote,
            "tracking": self.tracking,
            "ahead": self.ahead,
            "behind": self.behind,
        }


@dataclass(frozen=True)
class FileDiff:
    """Diff information for a single file."""
    path: str
    status: str  # A=added, M=modified, D=deleted, R=renamed
    old_path: Optional[str] = None
    insertions: int = 0
    deletions: int = 0
    binary: bool = False

    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "status": self.status,
            "old_path": self.old_path,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "binary": self.binary,
        }


# ============================================================================
# Exceptions
# ============================================================================

class RepoOperationError(RuntimeError):
    """Error during repository operation."""

    def __init__(self, message: str, result: Optional[CommandResult] = None):
        super().__init__(message)
        self.result = result


class GitNotFoundError(RepoOperationError):
    """Git is not available on PATH."""
    pass


class CloneError(RepoOperationError):
    """Error during clone operation."""
    pass


class UpdateError(RepoOperationError):
    """Error during update operation."""
    pass


# ============================================================================
# Command Execution
# ============================================================================

def _run(
    argv: List[str],
    cwd: Optional[Path] = None,
    *,
    timeout: int = 300,
    env: Optional[Dict[str, str]] = None,
) -> CommandResult:
    """Run a command and return the result."""
    import time
    start = time.time()

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=merged_env,
        )
        duration = int((time.time() - start) * 1000)
        return CommandResult(
            argv=argv,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_ms=duration,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            argv=argv,
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
            duration_ms=timeout * 1000,
        )
    except OSError as e:
        return CommandResult(
            argv=argv,
            returncode=-1,
            stdout="",
            stderr=str(e),
            duration_ms=0,
        )


def _has_cmd(name: str) -> bool:
    """Check if a command is available on PATH."""
    return shutil.which(name) is not None


def _git_cmd(args: List[str], cwd: Path, *, timeout: int = 120) -> CommandResult:
    """Run a git command."""
    return _run(["git"] + args, cwd, timeout=timeout)


# ============================================================================
# Path Utilities
# ============================================================================

def default_clone_root() -> Path:
    """Get default clone root directory."""
    return Path(".repos")


def repo_dir_name(repo: str) -> str:
    """Convert owner/name to directory name."""
    return repo.replace("/", "__")


def parse_repo_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse owner and repo name from URL or shorthand."""
    # Handle owner/repo shorthand
    if "/" in url and not url.startswith(("http", "git@")):
        parts = url.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]

    # Handle HTTPS URLs
    https_match = re.match(r"https?://[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    # Handle SSH URLs
    ssh_match = re.match(r"git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    return None, None


# ============================================================================
# Clone Operations
# ============================================================================

def ensure_cloned(
    repo: str,
    clone_root: Optional[Path] = None,
    *,
    strategy: CloneStrategy = CloneStrategy.SHALLOW,
    force_git: bool = False,
    branch: Optional[str] = None,
) -> Path:
    """Ensure a GitHub repo is cloned locally.

    Args:
        repo: Repository in owner/name format or full URL
        clone_root: Directory to clone into
        strategy: Clone strategy to use
        force_git: Force use of git instead of gh
        branch: Specific branch to clone

    Returns:
        Path to the cloned repository
    """
    root = (clone_root or default_clone_root()).resolve()
    root.mkdir(parents=True, exist_ok=True)

    # Parse repo identifier
    owner, name = parse_repo_url(repo)
    if owner and name:
        dir_name = f"{owner}__{name}"
    else:
        dir_name = repo_dir_name(repo)

    dest = root / dir_name

    # Check if already cloned
    if (dest / ".git").exists():
        return dest

    if dest.exists() and not (dest / ".git").exists():
        raise CloneError(
            f"Destination exists but is not a git repo: {dest}. "
            "Delete it or choose another clone_root."
        )

    # Try GitHub CLI first
    if not force_git and _has_cmd("gh"):
        args = ["gh", "repo", "clone", repo, str(dest)]
        if branch:
            args.extend(["--", "-b", branch])
        res = _run(args)
        if res.success:
            return dest

    # Fallback to git
    if not _has_cmd("git"):
        raise GitNotFoundError("Neither `gh` nor `git` is available on PATH.")

    # Construct URL
    if repo.startswith(("http://", "https://", "git@")):
        url = repo
    else:
        url = f"https://github.com/{repo}.git"

    # Build clone command
    args = ["git", "clone"]
    if strategy == CloneStrategy.SHALLOW:
        args.extend(["--depth", "1"])
    if branch:
        args.extend(["-b", branch])
    args.extend([url, str(dest)])

    res = _run(args, timeout=600)
    if not res.success:
        raise CloneError(
            f"Failed to clone repository.\n"
            f"Command: {' '.join(res.argv)}\n"
            f"stderr: {res.stderr}",
            result=res,
        )

    return dest


def clone_or_update(
    repo: str,
    clone_root: Optional[Path] = None,
    *,
    update_strategy: MergeStrategy = MergeStrategy.FAST_FORWARD,
) -> Tuple[Path, bool]:
    """Clone a repo or update if it exists.

    Returns:
        Tuple of (repo_path, was_updated)
    """
    repo_path = ensure_cloned(repo, clone_root)

    # Check if we need to update
    res = _git_cmd(["rev-parse", "HEAD"], repo_path)
    old_sha = res.stdout.strip() if res.success else ""

    update_repo(repo_path, strategy=update_strategy)

    res = _git_cmd(["rev-parse", "HEAD"], repo_path)
    new_sha = res.stdout.strip() if res.success else ""

    return repo_path, old_sha != new_sha


# ============================================================================
# Update Operations
# ============================================================================

def update_repo(
    repo_path: Path,
    *,
    strategy: MergeStrategy = MergeStrategy.FAST_FORWARD,
) -> CommandResult:
    """Update a repository to latest.

    Args:
        repo_path: Path to the repository
        strategy: Update strategy

    Returns:
        CommandResult of the update operation
    """
    if not (repo_path / ".git").exists():
        raise UpdateError(f"Not a git repository: {repo_path}")
    if not _has_cmd("git"):
        raise GitNotFoundError("`git` is not available on PATH")

    # Fetch all remotes
    _git_cmd(["fetch", "--all", "--prune"], repo_path)

    # Apply update strategy
    if strategy == MergeStrategy.FAST_FORWARD:
        res = _git_cmd(["pull", "--ff-only"], repo_path)
    elif strategy == MergeStrategy.MERGE:
        res = _git_cmd(["pull", "--no-rebase"], repo_path)
    elif strategy == MergeStrategy.REBASE:
        res = _git_cmd(["pull", "--rebase"], repo_path)
    elif strategy == MergeStrategy.RESET:
        # Get the tracking branch
        branch_res = _git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
        if branch_res.success:
            branch = branch_res.stdout.strip()
            res = _git_cmd(["reset", "--hard", f"origin/{branch}"], repo_path)
        else:
            res = branch_res
    else:
        res = _git_cmd(["pull", "--ff-only"], repo_path)

    return res


def fetch_all(repo_path: Path) -> CommandResult:
    """Fetch all remotes and prune."""
    return _git_cmd(["fetch", "--all", "--prune"], repo_path)


# ============================================================================
# Git History Analysis
# ============================================================================

def get_commits(
    repo_path: Path,
    *,
    max_count: int = 1000,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    author: Optional[str] = None,
    path: Optional[str] = None,
) -> List[CommitInfo]:
    """Get commit history.

    Args:
        repo_path: Path to the repository
        max_count: Maximum commits to retrieve
        since: Only commits after this date
        until: Only commits before this date
        author: Filter by author
        path: Filter by file path

    Returns:
        List of CommitInfo objects
    """
    # Format: hash|short_hash|author_name|author_email|date|message
    fmt = "%H|%h|%an|%ae|%aI|%s"
    args = ["log", f"--format={fmt}", f"-n{max_count}"]

    if since:
        args.append(f"--since={since.isoformat()}")
    if until:
        args.append(f"--until={until.isoformat()}")
    if author:
        args.append(f"--author={author}")
    if path:
        args.extend(["--", path])

    res = _git_cmd(args, repo_path)
    if not res.success:
        return []

    commits: List[CommitInfo] = []
    for line in res.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("|", 5)
        if len(parts) < 6:
            continue

        try:
            date = datetime.fromisoformat(parts[4].replace("Z", "+00:00"))
        except ValueError:
            date = datetime.now()

        commits.append(CommitInfo(
            sha=parts[0],
            short_sha=parts[1],
            author_name=parts[2],
            author_email=parts[3],
            date=date,
            message=parts[5],
        ))

    return commits


def get_git_history(
    repo_path: Path,
    *,
    max_commits: int = 1000,
    include_stats: bool = True,
) -> GitHistory:
    """Analyze git history of the repository.

    Args:
        repo_path: Path to the repository
        max_commits: Maximum commits to analyze
        include_stats: Whether to include detailed statistics

    Returns:
        GitHistory with analysis results
    """
    commits = get_commits(repo_path, max_count=max_commits)

    contributors: Dict[str, ContributorStats] = {}
    file_changes: Counter = Counter()
    commits_by_day: Counter = Counter()
    commits_by_hour: Counter = Counter()
    commits_by_weekday: Counter = Counter()
    total_insertions = 0
    total_deletions = 0

    for commit in commits:
        # Track contributor
        email = commit.author_email.lower()
        if email not in contributors:
            contributors[email] = ContributorStats(
                name=commit.author_name,
                email=email,
            )

        contrib = contributors[email]
        contrib.commit_count += 1

        if contrib.first_commit is None or commit.date < contrib.first_commit:
            object.__setattr__(contrib, 'first_commit', commit.date)
        if contrib.last_commit is None or commit.date > contrib.last_commit:
            object.__setattr__(contrib, 'last_commit', commit.date)

        month_key = commit.date.strftime("%Y-%m")
        contrib.commits_by_month[month_key] += 1

        # Time-based stats
        day_key = commit.date.strftime("%Y-%m-%d")
        commits_by_day[day_key] += 1
        commits_by_hour[commit.date.hour] += 1
        commits_by_weekday[commit.date.weekday()] += 1

    # Get file change statistics if requested
    if include_stats and commits:
        # Get numstat for recent commits
        args = ["log", "--numstat", "--format=", f"-n{min(500, max_commits)}"]
        res = _git_cmd(args, repo_path)
        if res.success:
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    try:
                        insertions = int(parts[0]) if parts[0] != "-" else 0
                        deletions = int(parts[1]) if parts[1] != "-" else 0
                        file_path = parts[2]
                        total_insertions += insertions
                        total_deletions += deletions
                        file_changes[file_path] += 1
                    except ValueError:
                        continue

    first_date = commits[-1].date if commits else None
    last_date = commits[0].date if commits else None

    return GitHistory(
        commits=commits[:100],  # Keep only recent for memory
        contributors=contributors,
        total_commits=len(commits),
        total_insertions=total_insertions,
        total_deletions=total_deletions,
        commits_by_day=commits_by_day,
        commits_by_hour=commits_by_hour,
        commits_by_weekday=commits_by_weekday,
        most_active_files=file_changes.most_common(50),
        first_commit_date=first_date,
        last_commit_date=last_date,
    )


def get_contributors(
    repo_path: Path,
    *,
    max_commits: int = 5000,
) -> List[ContributorStats]:
    """Get contributor statistics.

    Args:
        repo_path: Path to the repository
        max_commits: Maximum commits to analyze

    Returns:
        List of ContributorStats sorted by commit count
    """
    history = get_git_history(repo_path, max_commits=max_commits, include_stats=False)
    return sorted(
        history.contributors.values(),
        key=lambda c: -c.commit_count,
    )


# ============================================================================
# Branch Operations
# ============================================================================

def get_branches(
    repo_path: Path,
    *,
    include_remote: bool = True,
) -> List[BranchInfo]:
    """Get all branches in the repository.

    Args:
        repo_path: Path to the repository
        include_remote: Whether to include remote branches

    Returns:
        List of BranchInfo objects
    """
    branches: List[BranchInfo] = []

    # Get local branches
    args = ["branch", "-v", "--format=%(HEAD)|%(refname:short)|%(objectname:short)|%(upstream:short)"]
    res = _git_cmd(args, repo_path)
    if res.success:
        for line in res.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                branches.append(BranchInfo(
                    name=parts[1],
                    is_current=parts[0] == "*",
                    is_remote=False,
                    tracking=parts[3] if len(parts) > 3 and parts[3] else None,
                    last_commit_sha=parts[2],
                ))

    # Get remote branches
    if include_remote:
        args = ["branch", "-r", "-v", "--format=%(refname:short)|%(objectname:short)"]
        res = _git_cmd(args, repo_path)
        if res.success:
            for line in res.stdout.strip().splitlines():
                if not line or "HEAD" in line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    branches.append(BranchInfo(
                        name=parts[0],
                        is_current=False,
                        is_remote=True,
                        last_commit_sha=parts[1],
                    ))

    return branches


def get_current_branch(repo_path: Path) -> Optional[str]:
    """Get the current branch name."""
    res = _git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    if res.success:
        return res.stdout.strip()
    return None


def checkout_branch(repo_path: Path, branch: str, *, create: bool = False) -> CommandResult:
    """Checkout a branch.

    Args:
        repo_path: Path to the repository
        branch: Branch name
        create: Whether to create the branch if it doesn't exist

    Returns:
        CommandResult of the operation
    """
    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)
    return _git_cmd(args, repo_path)


# ============================================================================
# Diff Operations
# ============================================================================

def get_diff_files(
    repo_path: Path,
    *,
    from_ref: str = "HEAD~1",
    to_ref: str = "HEAD",
) -> List[FileDiff]:
    """Get files changed between two refs.

    Args:
        repo_path: Path to the repository
        from_ref: Starting reference
        to_ref: Ending reference

    Returns:
        List of FileDiff objects
    """
    args = ["diff", "--numstat", "--name-status", from_ref, to_ref]
    res = _git_cmd(args, repo_path)
    if not res.success:
        return []

    files: List[FileDiff] = []
    lines = res.stdout.strip().splitlines()

    # Parse numstat output
    for line in lines:
        if not line:
            continue
        parts = line.split("\t")

        if len(parts) >= 3 and parts[0].isdigit():
            # numstat format: insertions deletions file
            try:
                insertions = int(parts[0]) if parts[0] != "-" else 0
                deletions = int(parts[1]) if parts[1] != "-" else 0
                path = parts[2]
                binary = parts[0] == "-"

                files.append(FileDiff(
                    path=path,
                    status="M",
                    insertions=insertions,
                    deletions=deletions,
                    binary=binary,
                ))
            except ValueError:
                continue
        elif len(parts) >= 2:
            # name-status format: status file
            status = parts[0][0]
            path = parts[1] if len(parts) > 1 else parts[0][1:].strip()
            old_path = parts[2] if len(parts) > 2 and status == "R" else None

            # Find existing entry and update status
            found = False
            for f in files:
                if f.path == path:
                    files.remove(f)
                    files.append(FileDiff(
                        path=path,
                        status=status,
                        old_path=old_path,
                        insertions=f.insertions,
                        deletions=f.deletions,
                        binary=f.binary,
                    ))
                    found = True
                    break

            if not found:
                files.append(FileDiff(path=path, status=status, old_path=old_path))

    return files


def get_uncommitted_changes(repo_path: Path) -> List[FileDiff]:
    """Get uncommitted changes in the working tree."""
    return get_diff_files(repo_path, from_ref="HEAD", to_ref="")


# ============================================================================
# Status and Info
# ============================================================================

def get_status(repo_path: Path) -> Dict[str, List[str]]:
    """Get repository status.

    Returns:
        Dict with keys: staged, modified, untracked, conflicts
    """
    res = _git_cmd(["status", "--porcelain"], repo_path)
    if not res.success:
        return {"staged": [], "modified": [], "untracked": [], "conflicts": []}

    status: Dict[str, List[str]] = {
        "staged": [],
        "modified": [],
        "untracked": [],
        "conflicts": [],
    }

    for line in res.stdout.splitlines():
        if len(line) < 3:
            continue

        index_status = line[0]
        work_status = line[1]
        path = line[3:]

        if index_status == "U" or work_status == "U":
            status["conflicts"].append(path)
        elif index_status == "?":
            status["untracked"].append(path)
        elif index_status != " ":
            status["staged"].append(path)
        elif work_status != " ":
            status["modified"].append(path)

    return status


def is_dirty(repo_path: Path) -> bool:
    """Check if repository has uncommitted changes."""
    res = _git_cmd(["status", "--porcelain"], repo_path)
    return bool(res.stdout.strip())


def get_remote_url(repo_path: Path, remote: str = "origin") -> Optional[str]:
    """Get URL of a remote."""
    res = _git_cmd(["remote", "get-url", remote], repo_path)
    if res.success:
        return res.stdout.strip()
    return None


def get_current_sha(repo_path: Path, *, short: bool = False) -> Optional[str]:
    """Get current commit SHA."""
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    res = _git_cmd(args, repo_path)
    if res.success:
        return res.stdout.strip()
    return None
