from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from .scanner import RepoScan, read_text


_WORD_RE = re.compile(r"[A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class Match:
    path: str
    line_no: int
    line: str


@dataclass
class InvertedIndex:
    # token -> list of matches (kept small)
    token_to_matches: Dict[str, List[Match]]

    def search(self, query: str, *, max_results: int = 50) -> List[Match]:
        tokens = [t.lower() for t in _WORD_RE.findall(query)]
        if not tokens:
            return []

        # naive AND semantics: intersect by (path,line_no,line)
        sets: List[Dict[Tuple[str, int, str], Match]] = []
        for tok in tokens:
            hits = self.token_to_matches.get(tok, [])
            sets.append({(m.path, m.line_no, m.line): m for m in hits})

        if not sets:
            return []

        common = set(sets[0].keys())
        for s in sets[1:]:
            common &= set(s.keys())

        results = [sets[0][k] for k in common]
        results.sort(key=lambda m: (m.path, m.line_no))
        return results[:max_results]


def build_index(repo_root: Path, scan: RepoScan, *, max_matches_per_token: int = 200) -> InvertedIndex:
    token_to_matches: Dict[str, List[Match]] = {}

    for fi in scan.files:
        # focus on "likely text" file extensions; still safe since read_text ignores decode errors
        if fi.path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.gz', '.tar', '.ico')):
            continue

        try:
            text = read_text(repo_root, fi.path)
        except OSError:
            continue

        for idx, line in enumerate(text.splitlines(), start=1):
            # skip enormous lines
            if len(line) > 2000:
                continue
            for tok in _WORD_RE.findall(line):
                t = tok.lower()
                bucket = token_to_matches.setdefault(t, [])
                if len(bucket) >= max_matches_per_token:
                    continue
                bucket.append(Match(path=fi.path, line_no=idx, line=line.strip()))

    return InvertedIndex(token_to_matches=token_to_matches)
