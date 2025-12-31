from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .analysis import RepoSummary
from .scanner import RepoScan


def _fmt_bytes(n: int) -> str:
    # simple human formatter
    units = ["B", "KiB", "MiB", "GiB"]
    v = float(n)
    for u in units:
        if v < 1024.0 or u == units[-1]:
            return f"{v:.1f} {u}" if u != "B" else f"{int(v)} {u}"
        v /= 1024.0
    return f"{n} B"


def render_report(summary: RepoSummary, scan: RepoScan, *, title: Optional[str] = None) -> str:
    now = datetime.now(timezone.utc).isoformat()
    title = title or f"Repository research report: {Path(summary.repo_root).name}"

    top_ext = list(scan.by_extension.items())[:20]

    lines: list[str] = []
    lines.append(f"# {title}\n")
    lines.append(f"Generated: {now}\n")

    lines.append("## Snapshot\n")
    lines.append(f"- Root: `{scan.root}`")
    lines.append(f"- Files indexed: {len(scan.files)}")
    lines.append(f"- Total bytes indexed: {_fmt_bytes(scan.total_bytes)}\n")

    lines.append("## Top file extensions\n")
    for ext, count in top_ext:
        lines.append(f"- `{ext}`: {count}")
    lines.append("")

    if summary.notable_crates:
        lines.append("## Notable crates / modules (heuristic)\n")
        for c in summary.notable_crates:
            lines.append(f"- `{c}`")
        lines.append("")

    if summary.cargo_workspace_members:
        lines.append("## Cargo workspace members (parsed)\n")
        for m in summary.cargo_workspace_members:
            lines.append(f"- `{m}`")
        lines.append("")

    if summary.env_vars:
        lines.append("## Environment variables discovered\n")
        for v in summary.env_vars[:200]:
            lines.append(f"- `{v}`")
        if len(summary.env_vars) > 200:
            lines.append(f"\n(Truncated; total {len(summary.env_vars)} vars.)")
        lines.append("")

    if summary.readme_path and summary.readme_excerpt:
        lines.append("## README excerpt\n")
        lines.append(f"Source: `{summary.readme_path}`\n")
        excerpt = summary.readme_excerpt.strip()
        # indent as a blockquote without using a code fence
        for ln in excerpt.splitlines()[:120]:
            lines.append("> " + ln)
        if len(excerpt.splitlines()) > 120:
            lines.append("> [...truncated...]\n")
        lines.append("")

    lines.append("## Next questions to explore\n")
    lines.append("- Where are HTTP routes defined and wired to handlers?")
    lines.append("- Which crate is the indexing/search engine core, and what are its key data structures?")
    lines.append("- How does the task scheduler persist state and manage batches?")

    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
