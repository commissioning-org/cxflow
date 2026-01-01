"""Advanced reporting with multiple output formats.

This module provides comprehensive reporting capabilities including:
- Multiple output formats (Markdown, JSON, HTML, CSV)
- Interactive HTML reports with charts
- Customizable templates
- Summary and detailed report modes
- Export utilities
"""

from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .analysis import CodeMetrics, DependencyInfo, RepoSummary, SecurityFinding, Severity
from .scanner import RepoScan


# ============================================================================
# Enums and Constants
# ============================================================================

class ReportFormat(Enum):
    """Output format for reports."""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    CSV = "csv"
    TEXT = "text"


class ReportLevel(Enum):
    """Level of detail for reports."""
    SUMMARY = "summary"
    STANDARD = "standard"
    DETAILED = "detailed"
    FULL = "full"


# Color schemes for HTML reports
SEVERITY_COLORS = {
    Severity.CRITICAL: "#dc3545",
    Severity.HIGH: "#fd7e14",
    Severity.MEDIUM: "#ffc107",
    Severity.LOW: "#17a2b8",
    Severity.INFO: "#6c757d",
}

GRADE_COLORS = {
    "A": "#28a745",
    "B": "#5cb85c",
    "C": "#ffc107",
    "D": "#fd7e14",
    "F": "#dc3545",
}


# ============================================================================
# Utility Functions
# ============================================================================

def _fmt_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    v = float(n)
    for u in units:
        if v < 1024.0 or u == units[-1]:
            return f"{v:.1f} {u}" if u != "B" else f"{int(v)} {u}"
        v /= 1024.0
    return f"{n} B"


def _fmt_number(n: int) -> str:
    """Format number with thousands separator."""
    return f"{n:,}"


def _fmt_percentage(n: float) -> str:
    """Format percentage."""
    return f"{n:.1f}%"


def _fmt_date(dt: Optional[datetime]) -> str:
    """Format datetime to ISO string."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _escape_md(text: str) -> str:
    """Escape special markdown characters."""
    for char in ["\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!"]:
        text = text.replace(char, "\\" + char)
    return text


def _to_serializable(obj: Any) -> Any:
    """Convert object to JSON-serializable format."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(i) for i in obj]
    return str(obj)


# ============================================================================
# Report Data Classes
# ============================================================================

@dataclass
class ReportSection:
    """A section of the report."""
    title: str
    content: str
    subsections: List['ReportSection'] = None
    level: int = 2

    def __post_init__(self):
        if self.subsections is None:
            self.subsections = []


@dataclass
class ReportContext:
    """Context for report generation."""
    summary: RepoSummary
    scan: RepoScan
    title: Optional[str] = None
    description: Optional[str] = None
    generated_at: datetime = None
    level: ReportLevel = ReportLevel.STANDARD
    include_toc: bool = True
    include_charts: bool = True
    custom_sections: List[ReportSection] = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now(timezone.utc)
        if self.custom_sections is None:
            self.custom_sections = []


# ============================================================================
# Markdown Report Generation
# ============================================================================

def _generate_toc(sections: List[ReportSection]) -> str:
    """Generate table of contents."""
    lines = ["## Table of Contents\n"]
    for i, section in enumerate(sections, 1):
        anchor = section.title.lower().replace(" ", "-").replace("/", "")
        lines.append(f"{i}. [{section.title}](#{anchor})")
        for j, subsection in enumerate(section.subsections, 1):
            sub_anchor = subsection.title.lower().replace(" ", "-").replace("/", "")
            lines.append(f"   {i}.{j}. [{subsection.title}](#{sub_anchor})")
    return "\n".join(lines) + "\n"


def _section_snapshot(scan: RepoScan) -> ReportSection:
    """Generate repository snapshot section."""
    lines = [
        f"- **Root**: `{scan.root}`",
        f"- **Files indexed**: {_fmt_number(len(scan.files))}",
        f"- **Total size**: {_fmt_bytes(scan.total_bytes)}",
        f"- **Scan duration**: {scan.scan_duration_ms}ms",
    ]

    if scan.primary_language:
        lines.append(f"- **Primary language**: {scan.primary_language}")

    if scan.git_metadata:
        gm = scan.git_metadata
        lines.append(f"- **Current branch**: `{gm.current_branch}`")
        lines.append(f"- **Commits**: {_fmt_number(gm.commit_count)}")
        if gm.remote_url:
            lines.append(f"- **Remote**: `{gm.remote_url}`")

    return ReportSection(title="Repository Snapshot", content="\n".join(lines))


def _section_languages(scan: RepoScan) -> ReportSection:
    """Generate language breakdown section."""
    if not scan.by_language:
        return ReportSection(title="Language Breakdown", content="No language data available.")

    lines = ["| Language | Files | Lines | Percentage |", "|----------|-------|-------|------------|"]
    for lang, stats in list(scan.by_language.items())[:15]:
        lines.append(
            f"| {lang.capitalize()} | {_fmt_number(stats.file_count)} | "
            f"{_fmt_number(stats.total_lines)} | {_fmt_percentage(stats.percentage)} |"
        )

    return ReportSection(title="Language Breakdown", content="\n".join(lines))


def _section_extensions(scan: RepoScan) -> ReportSection:
    """Generate file extensions section."""
    top_ext = list(scan.by_extension.items())[:20]
    lines = ["| Extension | Count |", "|-----------|-------|"]
    for ext, count in top_ext:
        lines.append(f"| `.{ext}` | {_fmt_number(count)} |")

    return ReportSection(title="File Extensions", content="\n".join(lines))


def _section_frameworks(summary: RepoSummary) -> ReportSection:
    """Generate frameworks section."""
    lines = []

    if summary.frameworks_detected:
        lines.append("**Frameworks/Libraries:**")
        for fw in summary.frameworks_detected:
            lines.append(f"- {fw}")
        lines.append("")

    if summary.build_systems:
        lines.append("**Build Systems:**")
        for bs in summary.build_systems:
            lines.append(f"- {bs}")
        lines.append("")

    if summary.ci_cd_detected:
        lines.append("**CI/CD:**")
        for ci in summary.ci_cd_detected:
            lines.append(f"- {ci}")

    if not lines:
        return ReportSection(title="Technology Stack", content="No framework information available.")

    return ReportSection(title="Technology Stack", content="\n".join(lines))


def _section_code_quality(summary: RepoSummary) -> ReportSection:
    """Generate code quality section."""
    if not summary.code_metrics:
        return ReportSection(title="Code Quality", content="No code quality metrics available.")

    m = summary.code_metrics
    lines = [
        f"### Overall Grade: **{m.grade}** ({m.maintainability_index:.1f}/100)\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Lines of Code | {_fmt_number(m.lines_of_code)} |",
        f"| Logical Lines | {_fmt_number(m.logical_lines)} |",
        f"| Comment Lines | {_fmt_number(m.comment_lines)} |",
        f"| Comment Ratio | {_fmt_percentage(m.comment_ratio)} |",
        f"| Functions | {_fmt_number(m.function_count)} |",
        f"| Classes | {_fmt_number(m.class_count)} |",
        f"| Cyclomatic Complexity | {m.cyclomatic_complexity:.0f} |",
        f"| Cognitive Complexity | {m.cognitive_complexity:.0f} |",
        f"| Avg Function Length | {m.avg_function_length:.1f} lines |",
        f"| Max Function Length | {m.max_function_length} lines |",
        f"| Technical Debt | ~{m.technical_debt_minutes} minutes |",
    ]

    return ReportSection(title="Code Quality", content="\n".join(lines))


def _section_security(summary: RepoSummary) -> ReportSection:
    """Generate security findings section."""
    if not summary.security_findings:
        return ReportSection(title="Security Analysis", content="✅ No security issues detected.")

    findings_by_severity: Dict[Severity, List[SecurityFinding]] = {}
    for finding in summary.security_findings:
        if finding.severity not in findings_by_severity:
            findings_by_severity[finding.severity] = []
        findings_by_severity[finding.severity].append(finding)

    lines = [f"**Total findings:** {len(summary.security_findings)}\n"]

    severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    for severity in severity_order:
        findings = findings_by_severity.get(severity, [])
        if findings:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(severity.value, "")
            lines.append(f"### {emoji} {severity.value.upper()} ({len(findings)})\n")

            for f in findings[:10]:  # Limit per severity
                lines.append(f"- **{f.rule_id}**: `{f.file_path}:{f.line_number}`")
                lines.append(f"  - {f.message}")
            if len(findings) > 10:
                lines.append(f"  - _...and {len(findings) - 10} more_\n")
            lines.append("")

    return ReportSection(title="Security Analysis", content="\n".join(lines))


def _section_dependencies(summary: RepoSummary) -> ReportSection:
    """Generate dependencies section."""
    if not summary.dependencies:
        return ReportSection(title="Dependencies", content="No dependencies detected.")

    deps_by_type: Dict[str, List[DependencyInfo]] = {}
    for dep in summary.dependencies:
        key = dep.dep_type.value
        if key not in deps_by_type:
            deps_by_type[key] = []
        deps_by_type[key].append(dep)

    lines = [f"**Total dependencies:** {len(summary.dependencies)}\n"]

    for dep_type, deps in deps_by_type.items():
        lines.append(f"### {dep_type.capitalize()} ({len(deps)})\n")
        for dep in deps[:20]:
            version = f" `{dep.version}`" if dep.version else ""
            lines.append(f"- {dep.name}{version}")
        if len(deps) > 20:
            lines.append(f"- _...and {len(deps) - 20} more_")
        lines.append("")

    return ReportSection(title="Dependencies", content="\n".join(lines))


def _section_readme(summary: RepoSummary) -> ReportSection:
    """Generate README excerpt section."""
    if not summary.readme_path or not summary.readme_excerpt:
        return ReportSection(title="README", content="No README found.")

    excerpt = summary.readme_excerpt.strip()
    lines = [f"_Source: `{summary.readme_path}`_\n"]

    # Truncate and quote
    excerpt_lines = excerpt.splitlines()[:100]
    for ln in excerpt_lines:
        lines.append("> " + ln)

    if len(excerpt.splitlines()) > 100:
        lines.append("> [...]")

    return ReportSection(title="README Excerpt", content="\n".join(lines))


def _section_env_vars(summary: RepoSummary) -> ReportSection:
    """Generate environment variables section."""
    if not summary.env_vars:
        return ReportSection(title="Environment Variables", content="No environment variables detected.")

    lines = []
    for var in summary.env_vars[:100]:
        lines.append(f"- `{var}`")

    if len(summary.env_vars) > 100:
        lines.append(f"\n_...and {len(summary.env_vars) - 100} more variables_")

    return ReportSection(title="Environment Variables", content="\n".join(lines))


def _section_cargo(summary: RepoSummary) -> Optional[ReportSection]:
    """Generate Cargo workspace section (if applicable)."""
    if not summary.cargo_workspace_members:
        return None

    lines = []
    for member in summary.cargo_workspace_members:
        lines.append(f"- `{member}`")

    return ReportSection(title="Cargo Workspace", content="\n".join(lines))


def _section_questions(summary: RepoSummary) -> ReportSection:
    """Generate next questions section."""
    questions = [
        "- Where are the main entry points and how is the application bootstrapped?",
        "- What is the overall architecture pattern (monolith, microservices, etc.)?",
        "- How is data persistence handled and what databases are used?",
        "- What authentication/authorization mechanisms are in place?",
        "- How is configuration managed across different environments?",
        "- What testing strategies are employed (unit, integration, e2e)?",
        "- How are errors handled and logged throughout the application?",
    ]
    return ReportSection(title="Next Questions to Explore", content="\n".join(questions))


def render_report(
    summary: RepoSummary,
    scan: RepoScan,
    *,
    title: Optional[str] = None,
    level: ReportLevel = ReportLevel.STANDARD,
    include_toc: bool = True,
) -> str:
    """Render a Markdown report.

    Args:
        summary: Repository summary
        scan: Repository scan results
        title: Optional custom title
        level: Level of detail
        include_toc: Whether to include table of contents

    Returns:
        Markdown content as string
    """
    now = datetime.now(timezone.utc).isoformat()
    title = title or f"Repository Research Report: {Path(summary.repo_root).name}"

    # Build sections
    sections: List[ReportSection] = [
        _section_snapshot(scan),
        _section_languages(scan),
        _section_frameworks(summary),
    ]

    if level in (ReportLevel.STANDARD, ReportLevel.DETAILED, ReportLevel.FULL):
        sections.append(_section_code_quality(summary))
        sections.append(_section_security(summary))
        sections.append(_section_dependencies(summary))

    if level in (ReportLevel.DETAILED, ReportLevel.FULL):
        sections.append(_section_extensions(scan))
        sections.append(_section_env_vars(summary))

        cargo_section = _section_cargo(summary)
        if cargo_section:
            sections.append(cargo_section)

    if level == ReportLevel.FULL:
        sections.append(_section_readme(summary))

    sections.append(_section_questions(summary))

    # Build report
    lines = [
        f"# {title}\n",
        f"_Generated: {now}_\n",
    ]

    if summary.license_type:
        lines.append(f"**License:** {summary.license_type}\n")

    lines.append(f"**Documentation Score:** {summary.documentation_score:.0f}/100\n")

    if include_toc:
        lines.append(_generate_toc(sections))

    for section in sections:
        lines.append(f"\n## {section.title}\n")
        lines.append(section.content)
        lines.append("")

        for subsection in section.subsections:
            lines.append(f"\n### {subsection.title}\n")
            lines.append(subsection.content)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ============================================================================
# JSON Export
# ============================================================================

def export_json(
    summary: RepoSummary,
    scan: RepoScan,
    *,
    indent: int = 2,
    include_files: bool = False,
) -> str:
    """Export report as JSON.

    Args:
        summary: Repository summary
        scan: Repository scan results
        indent: JSON indentation
        include_files: Whether to include file list

    Returns:
        JSON string
    """
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "root": summary.repo_root,
            "primary_language": summary.primary_language,
            "license": summary.license_type,
            "documentation_score": summary.documentation_score,
        },
        "scan": {
            "file_count": len(scan.files),
            "total_bytes": scan.total_bytes,
            "scan_duration_ms": scan.scan_duration_ms,
            "by_extension": scan.by_extension,
            "by_language": {k: _to_serializable(v) for k, v in scan.by_language.items()},
            "by_category": scan.by_category,
        },
        "technology": {
            "frameworks": summary.frameworks_detected,
            "build_systems": summary.build_systems,
            "ci_cd": summary.ci_cd_detected,
        },
        "dependencies": [_to_serializable(d) for d in summary.dependencies],
        "security": {
            "finding_count": len(summary.security_findings),
            "findings": [_to_serializable(f) for f in summary.security_findings[:100]],
        },
        "code_metrics": _to_serializable(summary.code_metrics) if summary.code_metrics else None,
        "environment_variables": summary.env_vars[:100],
    }

    if include_files:
        data["files"] = [{"path": f.path, "size": f.size_bytes, "language": f.language} for f in scan.files]

    if scan.git_metadata:
        data["git"] = _to_serializable(scan.git_metadata)

    return json.dumps(data, indent=indent, default=str)


# ============================================================================
# HTML Export
# ============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #1e1e1e;
            --text-color: #e0e0e0;
            --card-bg: #2d2d2d;
            --border-color: #444;
            --accent-color: #007acc;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: var(--accent-color); border-bottom: 2px solid var(--accent-color); padding-bottom: 10px; }}
        h2 {{ color: #ccc; margin-top: 30px; }}
        .card {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            border: 1px solid var(--border-color);
        }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
        .stat {{ text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: var(--accent-color); }}
        .stat-label {{ color: #888; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid var(--border-color); }}
        th {{ background: rgba(0,122,204,0.2); }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            margin: 2px;
        }}
        .grade {{ font-size: 3em; font-weight: bold; }}
        .severity-critical {{ background: #dc3545; color: white; }}
        .severity-high {{ background: #fd7e14; color: white; }}
        .severity-medium {{ background: #ffc107; color: black; }}
        .severity-low {{ background: #17a2b8; color: white; }}
        .severity-info {{ background: #6c757d; color: white; }}
        .progress {{ background: #444; border-radius: 4px; height: 8px; overflow: hidden; }}
        .progress-bar {{ height: 100%; background: var(--accent-color); }}
        code {{ background: #3d3d3d; padding: 2px 6px; border-radius: 3px; }}
        .meta {{ color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p class="meta">Generated: {generated_at}</p>

        <div class="grid">
            <div class="card stat">
                <div class="stat-value">{file_count}</div>
                <div class="stat-label">Files</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{total_size}</div>
                <div class="stat-label">Total Size</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{primary_language}</div>
                <div class="stat-label">Primary Language</div>
            </div>
            <div class="card stat">
                <div class="stat-value" style="color: {grade_color}">{grade}</div>
                <div class="stat-label">Code Quality</div>
            </div>
        </div>

        {sections}
    </div>
</body>
</html>"""


def export_html(
    summary: RepoSummary,
    scan: RepoScan,
    *,
    title: Optional[str] = None,
) -> str:
    """Export report as HTML.

    Args:
        summary: Repository summary
        scan: Repository scan results
        title: Optional custom title

    Returns:
        HTML string
    """
    title = title or f"Repository Report: {Path(summary.repo_root).name}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    grade = summary.code_metrics.grade if summary.code_metrics else "N/A"
    grade_color = GRADE_COLORS.get(grade, "#888")

    sections_html = []

    # Technology Stack
    if summary.frameworks_detected or summary.build_systems:
        tech_items = []
        for fw in summary.frameworks_detected:
            tech_items.append(f'<span class="badge" style="background: var(--accent-color)">{html.escape(fw)}</span>')
        for bs in summary.build_systems:
            tech_items.append(f'<span class="badge" style="background: #28a745">{html.escape(bs)}</span>')
        sections_html.append(f'''
        <h2>Technology Stack</h2>
        <div class="card">{"".join(tech_items)}</div>
        ''')

    # Language breakdown
    if scan.by_language:
        rows = []
        for lang, stats in list(scan.by_language.items())[:10]:
            rows.append(f'''
            <tr>
                <td>{html.escape(lang.capitalize())}</td>
                <td>{stats.file_count}</td>
                <td>{_fmt_number(stats.total_lines)}</td>
                <td>
                    <div class="progress">
                        <div class="progress-bar" style="width: {stats.percentage}%"></div>
                    </div>
                    {stats.percentage:.1f}%
                </td>
            </tr>
            ''')
        sections_html.append(f'''
        <h2>Languages</h2>
        <div class="card">
            <table>
                <tr><th>Language</th><th>Files</th><th>Lines</th><th>Share</th></tr>
                {"".join(rows)}
            </table>
        </div>
        ''')

    # Security findings
    if summary.security_findings:
        severity_counts = {}
        for f in summary.security_findings:
            severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1

        badges = []
        for sev in ["critical", "high", "medium", "low", "info"]:
            if sev in severity_counts:
                badges.append(f'<span class="badge severity-{sev}">{sev.upper()}: {severity_counts[sev]}</span>')

        sections_html.append(f'''
        <h2>Security Findings</h2>
        <div class="card">{"".join(badges)}</div>
        ''')

    # Dependencies summary
    if summary.dependencies:
        sections_html.append(f'''
        <h2>Dependencies</h2>
        <div class="card">
            <p><strong>{len(summary.dependencies)}</strong> dependencies detected</p>
        </div>
        ''')

    return HTML_TEMPLATE.format(
        title=html.escape(title),
        generated_at=generated_at,
        file_count=_fmt_number(len(scan.files)),
        total_size=_fmt_bytes(scan.total_bytes),
        primary_language=html.escape(summary.primary_language or "N/A"),
        grade=grade,
        grade_color=grade_color,
        sections="".join(sections_html),
    )


# ============================================================================
# CSV Export
# ============================================================================

def export_csv(
    scan: RepoScan,
    *,
    include_all_fields: bool = False,
) -> str:
    """Export file list as CSV.

    Args:
        scan: Repository scan results
        include_all_fields: Whether to include all file fields

    Returns:
        CSV string
    """
    output = io.StringIO()

    if include_all_fields:
        fieldnames = ["path", "size_bytes", "language", "category", "is_binary", "line_count"]
    else:
        fieldnames = ["path", "size_bytes", "language"]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for f in scan.files:
        row = {
            "path": f.path,
            "size_bytes": f.size_bytes,
            "language": f.language or "",
        }
        if include_all_fields:
            row.update({
                "category": f.category or "",
                "is_binary": f.is_binary,
                "line_count": f.line_count or "",
            })
        writer.writerow(row)

    return output.getvalue()


# ============================================================================
# File Writing
# ============================================================================

def write_report(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write report to file.

    Args:
        path: Output file path
        content: Report content
        encoding: File encoding
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)


def write_multi_format(
    summary: RepoSummary,
    scan: RepoScan,
    base_path: Path,
    *,
    formats: Optional[List[ReportFormat]] = None,
    title: Optional[str] = None,
) -> Dict[ReportFormat, Path]:
    """Write reports in multiple formats.

    Args:
        summary: Repository summary
        scan: Repository scan results
        base_path: Base path without extension
        formats: List of formats to generate
        title: Optional custom title

    Returns:
        Dict mapping format to output path
    """
    if formats is None:
        formats = [ReportFormat.MARKDOWN, ReportFormat.JSON]

    outputs: Dict[ReportFormat, Path] = {}

    for fmt in formats:
        if fmt == ReportFormat.MARKDOWN:
            content = render_report(summary, scan, title=title)
            path = base_path.with_suffix(".md")
        elif fmt == ReportFormat.JSON:
            content = export_json(summary, scan)
            path = base_path.with_suffix(".json")
        elif fmt == ReportFormat.HTML:
            content = export_html(summary, scan, title=title)
            path = base_path.with_suffix(".html")
        elif fmt == ReportFormat.CSV:
            content = export_csv(scan)
            path = base_path.with_suffix(".csv")
        else:
            continue

        write_report(path, content)
        outputs[fmt] = path

    return outputs
