"""Gitignore-like filtering (stdlib-only).

This module intentionally implements a pragmatic subset of gitignore behavior
suitable for repository scanning:

- supports comments (#) and blank lines
- supports negation with leading '!'
- supports directory patterns with trailing '/'
- supports anchored patterns with leading '/'
- supports glob wildcards via fnmatch

It is not a full gitignore implementation (e.g. "**" edge cases, escaped
spaces, character ranges, and precedence nuances). The goal is predictable and
useful filtering without extra dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool


def _parse_ignore_lines(lines: Iterable[str]) -> List[IgnoreRule]:
    rules: List[IgnoreRule] = []

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#'):
            continue

        negated = line.startswith('!')
        if negated:
            line = line[1:].strip()
            if not line:
                continue

        anchored = line.startswith('/')
        if anchored:
            line = line[1:]

        directory_only = line.endswith('/')
        if directory_only:
            line = line[:-1]

        if not line:
            continue

        rules.append(IgnoreRule(
            pattern=line,
            negated=negated,
            directory_only=directory_only,
            anchored=anchored,
        ))

    return rules


def load_ignore_rules(root: Path, filenames: Sequence[str]) -> List[IgnoreRule]:
    """Load ignore rules from a set of files under root (best-effort)."""
    rules: List[IgnoreRule] = []

    for name in filenames:
        p = root / name
        try:
            if p.exists() and p.is_file():
                rules.extend(_parse_ignore_lines(p.read_text(errors='ignore').splitlines()))
        except OSError:
            continue

    return rules


class IgnoreSpec:
    """Ordered ignore rules with last-match-wins semantics."""

    def __init__(
        self,
        *,
        root: Path,
        rules: Sequence[IgnoreRule] = (),
        extra_patterns: Sequence[str] = (),
    ) -> None:
        self.root = root
        self.rules: Tuple[IgnoreRule, ...] = tuple(rules) + tuple(
            _parse_ignore_lines(extra_patterns)
        )

    def is_ignored(self, path: Path, *, is_dir: Optional[bool] = None) -> bool:
        """Return True if `path` should be ignored.

        Args:
            path: absolute or root-relative path
            is_dir: provide for performance; if None will stat if needed
        """
        p = path
        if not p.is_absolute():
            p = (self.root / p)

        rel = p
        try:
            rel = p.relative_to(self.root)
        except ValueError:
            # Not under root; never ignore.
            return False

        rel_posix = rel.as_posix()
        name = rel.name

        if is_dir is None:
            try:
                is_dir = p.is_dir()
            except OSError:
                is_dir = False

        ignored = False

        for rule in self.rules:
            if rule.directory_only and not is_dir:
                # Directory-only pattern doesn't apply to files.
                continue

            if rule.anchored:
                # Match from repository root.
                if '/' in rule.pattern:
                    matched = fnmatch(rel_posix, rule.pattern)
                else:
                    matched = fnmatch(rel_posix, rule.pattern) or fnmatch(name, rule.pattern)
            else:
                # Unanchored: match anywhere.
                if '/' in rule.pattern:
                    matched = fnmatch(rel_posix, f"*/{rule.pattern}") or fnmatch(rel_posix, rule.pattern)
                else:
                    matched = fnmatch(name, rule.pattern)

            # For directory-only rules, also treat matching directory prefixes as matches.
            if rule.directory_only and not matched:
                if rel_posix == rule.pattern or rel_posix.startswith(rule.pattern + '/'):
                    matched = True

            if matched:
                ignored = not rule.negated

        return ignored
