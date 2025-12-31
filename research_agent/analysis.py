from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .scanner import RepoScan, read_text


@dataclass(frozen=True)
class RepoSummary:
    repo_root: str
    readme_path: Optional[str]
    readme_excerpt: Optional[str]
    cargo_workspace_members: List[str]
    notable_crates: List[str]
    env_vars: List[str]


def _find_readme(scan: RepoScan) -> Optional[str]:
    for candidate in ("README.md", "readme.md", "README.MD"):
        if any(f.path == candidate for f in scan.files):
            return candidate
    return None


def _parse_workspace_members(cargo_toml: str) -> List[str]:
    # A minimal parser that works for common patterns.
    # Looks for: members = ["crates/foo", "crates/bar", ...]
    m = re.search(r"(?s)\[workspace\].*?members\s*=\s*\[(.*?)\]", cargo_toml)
    if not m:
        return []
    body = m.group(1)
    return [s.strip().strip('"\'') for s in re.findall(r"['\"]([^'\"]+)['\"]", body)]


def _extract_env_vars(scan: RepoScan, repo_root: Path, *, prefix: str = "MEILI_") -> List[str]:
    seen = set()
    rx = re.compile(r"\b" + re.escape(prefix) + r"[A-Z0-9_]+\b")
    for fi in scan.files:
        if not (fi.path.endswith(".rs") or fi.path.endswith(".toml") or fi.path.endswith(".md")):
            continue
        try:
            text = read_text(repo_root, fi.path, max_chars=200_000)
        except OSError:
            continue
        for v in rx.findall(text):
            seen.add(v)
    return sorted(seen)


def summarize_repo(repo_root: Path, scan: RepoScan) -> RepoSummary:
    readme_path = _find_readme(scan)
    readme_excerpt = None
    if readme_path:
        try:
            readme_excerpt = read_text(repo_root, readme_path, max_chars=20_000)
        except OSError:
            readme_excerpt = None

    cargo_root = "Cargo.toml"
    cargo_workspace_members: List[str] = []
    if any(f.path == cargo_root for f in scan.files):
        try:
            cargo = read_text(repo_root, cargo_root, max_chars=200_000)
            cargo_workspace_members = _parse_workspace_members(cargo)
        except OSError:
            cargo_workspace_members = []

    # A heuristic for Meilisearch-like monorepos
    notable = []
    for n in ("crates/meilisearch", "crates/milli", "crates/index-scheduler", "crates/meilitool", "crates/openapi-generator", "crates/xtask"):
        if any(f.path.startswith(n + "/") for f in scan.files):
            notable.append(n)

    env_vars = _extract_env_vars(scan, repo_root)

    return RepoSummary(
        repo_root=str(repo_root),
        readme_path=readme_path,
        readme_excerpt=readme_excerpt,
        cargo_workspace_members=cargo_workspace_members,
        notable_crates=notable,
        env_vars=env_vars,
    )
