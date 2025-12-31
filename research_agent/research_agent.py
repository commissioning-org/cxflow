"""High-level convenience wrapper.

This module exposes a tiny API for embedding the research agent into other tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .analysis import RepoSummary, summarize_repo
from .indexer import InvertedIndex, build_index
from .repo_ops import ensure_cloned, update_repo
from .scanner import RepoScan, scan_repo


@dataclass(frozen=True)
class ResearchArtifact:
    repo_path: Path
    scan: RepoScan
    summary: RepoSummary
    index: InvertedIndex


def research_repo(repo: str, *, clone_root: Optional[Path] = None, update: bool = False) -> ResearchArtifact:
    repo_path = ensure_cloned(repo, clone_root=clone_root)
    if update:
        update_repo(repo_path)

    scan = scan_repo(repo_path)
    summary = summarize_repo(repo_path, scan)
    index = build_index(repo_path, scan)

    return ResearchArtifact(repo_path=repo_path, scan=scan, summary=summary, index=index)
