from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


DEFAULT_IGNORE_DIRS = {
    ".git",
    "target",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
}


@dataclass(frozen=True)
class FileInfo:
    path: str
    size_bytes: int


@dataclass(frozen=True)
class RepoScan:
    root: str
    files: List[FileInfo]
    total_bytes: int
    by_extension: Dict[str, int]


def iter_files(
    root: Path,
    *,
    ignore_dirs: Optional[Sequence[str]] = None,
    max_file_size_bytes: int = 1_000_000,
) -> Iterator[Path]:
    ignore = set(ignore_dirs or DEFAULT_IGNORE_DIRS)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size <= 0 or st.st_size > max_file_size_bytes:
                continue
            yield p


def scan_repo(
    root: Path,
    *,
    ignore_dirs: Optional[Sequence[str]] = None,
    max_file_size_bytes: int = 1_000_000,
) -> RepoScan:
    files: List[FileInfo] = []
    total = 0
    by_ext: Dict[str, int] = {}

    for p in iter_files(root, ignore_dirs=ignore_dirs, max_file_size_bytes=max_file_size_bytes):
        try:
            st = p.stat()
        except OSError:
            continue
        rel = str(p.relative_to(root))
        files.append(FileInfo(path=rel, size_bytes=st.st_size))
        total += st.st_size
        ext = p.suffix.lower().lstrip(".") or "(noext)"
        by_ext[ext] = by_ext.get(ext, 0) + 1

    # stable-ish ordering
    files.sort(key=lambda f: (f.path.count("/"), f.path))

    return RepoScan(root=str(root), files=files, total_bytes=total, by_extension=dict(sorted(by_ext.items())))


def read_text(root: Path, rel_path: str, *, max_chars: int = 200_000) -> str:
    p = root / rel_path
    data = p.read_bytes()
    text = data.decode("utf-8", errors="ignore")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[...truncated...]\n"
    return text
