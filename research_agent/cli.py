from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .analysis import summarize_repo
from .indexer import build_index
from .repo_ops import ensure_cloned, update_repo
from .reporting import render_report, write_report
from .scanner import scan_repo


def _default_out(repo: str) -> Path:
    return Path("reports") / (repo.replace("/", "__") + ".md")


def cmd_clone(args: argparse.Namespace) -> int:
    repo_path = ensure_cloned(args.repo, clone_root=Path(args.clone_root) if args.clone_root else None)
    if args.update:
        update_repo(repo_path)
    print(str(repo_path))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    repo_path = ensure_cloned(args.repo, clone_root=Path(args.clone_root) if args.clone_root else None)
    if args.update:
        update_repo(repo_path)

    scan = scan_repo(repo_path)
    summary = summarize_repo(repo_path, scan)

    out = Path(args.out) if args.out else _default_out(args.repo)
    content = render_report(summary, scan, title=args.title)
    write_report(out, content)

    if args.json_summary:
        js = {
            "repo_root": summary.repo_root,
            "readme_path": summary.readme_path,
            "cargo_workspace_members": summary.cargo_workspace_members,
            "notable_crates": summary.notable_crates,
            "env_vars": summary.env_vars,
            "file_count": len(scan.files),
            "total_bytes": scan.total_bytes,
            "by_extension": scan.by_extension,
        }
        Path(args.json_summary).write_text(json.dumps(js, indent=2), encoding="utf-8")

    print(str(out))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    repo_path = ensure_cloned(args.repo, clone_root=Path(args.clone_root) if args.clone_root else None)
    if args.update:
        update_repo(repo_path)

    scan = scan_repo(repo_path)
    index = build_index(repo_path, scan)

    hits = index.search(args.query, max_results=args.max_results)
    for h in hits:
        print(f"{h.path}:{h.line_no}: {h.line}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="research-agent",
        description="Automated research agent that clones and analyzes GitHub repositories.",
    )
    p.add_argument("--clone-root", default=None, help="Where to clone repos (default: ./.repos)")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_clone = sub.add_parser("clone", help="Clone a repo using gh (fallback to git)")
    p_clone.add_argument("repo", help="owner/name")
    p_clone.add_argument("--update", action="store_true", help="git pull after clone")
    p_clone.set_defaults(func=cmd_clone)

    p_report = sub.add_parser("report", help="Generate a markdown report")
    p_report.add_argument("repo", help="owner/name")
    p_report.add_argument("--update", action="store_true", help="git pull before analysis")
    p_report.add_argument("--out", default=None, help="Output markdown file path")
    p_report.add_argument("--title", default=None, help="Report title")
    p_report.add_argument("--json-summary", default=None, help="Also write a machine-readable JSON summary")
    p_report.set_defaults(func=cmd_report)

    p_search = sub.add_parser("search", help="Search tokens across the repo")
    p_search.add_argument("repo", help="owner/name")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--update", action="store_true", help="git pull before search")
    p_search.add_argument("--max-results", type=int, default=30)
    p_search.set_defaults(func=cmd_search)

    args = p.parse_args(argv)
    return int(args.func(args))
