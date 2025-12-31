from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


class RepoOperationError(RuntimeError):
    pass


def _run(argv: Iterable[str], cwd: Optional[Path] = None) -> CommandResult:
    argv_list = list(argv)
    proc = subprocess.run(
        argv_list,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(
        argv=argv_list,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def default_clone_root() -> Path:
    return Path(".repos")


def repo_dir_name(repo: str) -> str:
    # owner/name -> owner__name to keep it single-directory
    return repo.replace("/", "__")


def ensure_cloned(repo: str, clone_root: Optional[Path] = None, *, force_git: bool = False) -> Path:
    """Ensure a GitHub repo is cloned locally.

    Primary strategy: `gh repo clone <repo>`.
    Fallback: `git clone https://github.com/<repo>.git`.

    Returns the path to the cloned repo.
    """

    root = (clone_root or default_clone_root()).resolve()
    root.mkdir(parents=True, exist_ok=True)

    dest = root / repo_dir_name(repo)
    if (dest / ".git").exists():
        return dest

    if dest.exists() and not (dest / ".git").exists():
        raise RepoOperationError(
            f"Destination exists but is not a git repo: {dest}. Delete it or choose another clone_root."
        )

    if not force_git and _has_cmd("gh"):
        res = _run(["gh", "repo", "clone", repo, str(dest)])
        if res.returncode == 0:
            return dest

    # fallback to git
    if not _has_cmd("git"):
        raise RepoOperationError("Neither `gh` nor `git` is available on PATH.")

    url = f"https://github.com/{repo}.git"
    res = _run(["git", "clone", "--depth", "1", url, str(dest)])
    if res.returncode != 0:
        raise RepoOperationError(
            "Failed to clone repository.\n"
            f"Command: {' '.join(res.argv)}\n"
            f"stdout: {res.stdout}\n"
            f"stderr: {res.stderr}"
        )
    return dest


def update_repo(repo_path: Path) -> CommandResult:
    """Fast-forward update a repo (best effort)."""
    if not (repo_path / ".git").exists():
        raise RepoOperationError(f"Not a git repository: {repo_path}")
    if not _has_cmd("git"):
        raise RepoOperationError("`git` is not available on PATH")

    # If the repo was cloned with --depth 1, pull may need to unshallow.
    res_fetch = _run(["git", "-C", str(repo_path), "fetch", "--all", "--prune"])
    res_pull = _run(["git", "-C", str(repo_path), "pull", "--ff-only"])

    # return the pull result but include fetch info in stderr if it failed
    if res_pull.returncode != 0 and res_fetch.returncode != 0:
        return CommandResult(
            argv=res_pull.argv,
            returncode=res_pull.returncode,
            stdout=res_pull.stdout,
            stderr=(res_fetch.stderr + "\n" + res_pull.stderr).strip(),
        )

    return res_pull
