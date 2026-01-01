"""Advanced repository analysis with code quality metrics.

This module provides comprehensive code analysis capabilities including:
- Code quality metrics (complexity, maintainability, technical debt)
- Dependency extraction and analysis
- Security vulnerability scanning
- Pattern detection and anti-pattern identification
- Architecture analysis and coupling metrics
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    Union,
)

from .scanner import FileInfo, RepoScan, read_text


# ============================================================================
# Enums and Constants
# ============================================================================

class Severity(Enum):
    """Severity levels for security findings and code issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DependencyType(Enum):
    """Types of project dependencies."""
    RUNTIME = "runtime"
    DEV = "dev"
    BUILD = "build"
    OPTIONAL = "optional"
    PEER = "peer"


# Security patterns to detect
SECURITY_PATTERNS: Dict[str, Tuple[Pattern, Severity, str]] = {
    "hardcoded_secret": (
        re.compile(r'(?i)(password|secret|api[_-]?key|token|private[_-]?key)\s*[=:]\s*["\'][^"\']{8,}["\']'),
        Severity.HIGH,
        "Potential hardcoded secret or credential detected",
    ),
    "sql_injection": (
        re.compile(r'(?i)(execute|cursor\.execute|raw|rawquery)\s*\(\s*["\'][^"\']*%s'),
        Severity.HIGH,
        "Potential SQL injection vulnerability",
    ),
    "shell_injection": (
        re.compile(r'(?i)(subprocess\.call|os\.system|os\.popen|shell=True)'),
        Severity.MEDIUM,
        "Potential shell injection vulnerability",
    ),
    "eval_usage": (
        re.compile(r'\beval\s*\('),
        Severity.MEDIUM,
        "Use of eval() can be dangerous",
    ),
    "pickle_usage": (
        re.compile(r'(?i)pickle\.(load|loads)\s*\('),
        Severity.MEDIUM,
        "Pickle deserialization can be unsafe",
    ),
    "yaml_unsafe": (
        re.compile(r'yaml\.(load|unsafe_load)\s*\([^)]*Loader\s*=\s*None'),
        Severity.MEDIUM,
        "Unsafe YAML loading detected",
    ),
    "debug_enabled": (
        re.compile(r'(?i)(debug\s*[=:]\s*true|DEBUG\s*=\s*True)'),
        Severity.LOW,
        "Debug mode may be enabled",
    ),
    "http_without_https": (
        re.compile(r'http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)'),
        Severity.LOW,
        "Non-HTTPS URL detected",
    ),
    "weak_crypto": (
        re.compile(r'(?i)(md5|sha1)\s*\('),
        Severity.LOW,
        "Weak cryptographic hash function",
    ),
    "temp_file_usage": (
        re.compile(r'(?i)/tmp/|tempfile\.mk(?:s)?temp\('),
        Severity.INFO,
        "Temporary file usage detected",
    ),
}

# Common anti-patterns
ANTIPATTERN_RULES: Dict[str, Tuple[Pattern, str, str]] = {
    "god_class": (
        re.compile(r'class\s+\w+.*?(?=class|\Z)', re.DOTALL),
        "Class with too many methods",
        "Consider breaking into smaller classes",
    ),
    "long_function": (
        re.compile(r'def\s+\w+\s*\([^)]*\)\s*:.*?(?=\ndef|\nclass|\Z)', re.DOTALL),
        "Function exceeds recommended length",
        "Consider breaking into smaller functions",
    ),
    "magic_numbers": (
        re.compile(r'(?<!["\'\w])\d{4,}(?!["\'\w])'),
        "Magic number detected",
        "Consider using named constants",
    ),
    "todo_fixme": (
        re.compile(r'(?i)#\s*(todo|fixme|hack|xxx|bug)\b'),
        "TODO/FIXME comment found",
        "Address or create issue for tracking",
    ),
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass(frozen=True)
class SecurityFinding:
    """A security finding in the codebase."""
    rule_id: str
    severity: Severity
    file_path: str
    line_number: int
    message: str
    code_snippet: str = ""
    recommendation: str = ""
    cwe_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "message": self.message,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
            "cwe_id": self.cwe_id,
        }


@dataclass(frozen=True)
class DependencyInfo:
    """Information about a project dependency."""
    name: str
    version: Optional[str] = None
    dep_type: DependencyType = DependencyType.RUNTIME
    source_file: Optional[str] = None
    is_dev: bool = False
    is_optional: bool = False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.dep_type.value,
            "source_file": self.source_file,
            "is_dev": self.is_dev,
        }


@dataclass
class CodeMetrics:
    """Code quality metrics for a file or repository."""
    cyclomatic_complexity: float = 0.0
    cognitive_complexity: float = 0.0
    maintainability_index: float = 100.0
    lines_of_code: int = 0
    logical_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    comment_ratio: float = 0.0
    function_count: int = 0
    class_count: int = 0
    avg_function_length: float = 0.0
    max_function_length: int = 0
    avg_complexity_per_function: float = 0.0
    duplication_ratio: float = 0.0
    technical_debt_minutes: int = 0

    @property
    def grade(self) -> str:
        """Calculate letter grade based on maintainability index."""
        if self.maintainability_index >= 80:
            return "A"
        elif self.maintainability_index >= 60:
            return "B"
        elif self.maintainability_index >= 40:
            return "C"
        elif self.maintainability_index >= 20:
            return "D"
        return "F"

    def to_dict(self) -> Dict:
        return {
            "cyclomatic_complexity": round(self.cyclomatic_complexity, 2),
            "cognitive_complexity": round(self.cognitive_complexity, 2),
            "maintainability_index": round(self.maintainability_index, 2),
            "grade": self.grade,
            "lines_of_code": self.lines_of_code,
            "logical_lines": self.logical_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "comment_ratio": round(self.comment_ratio, 2),
            "function_count": self.function_count,
            "class_count": self.class_count,
            "avg_function_length": round(self.avg_function_length, 2),
            "max_function_length": self.max_function_length,
            "avg_complexity_per_function": round(self.avg_complexity_per_function, 2),
            "duplication_ratio": round(self.duplication_ratio, 2),
            "technical_debt_minutes": self.technical_debt_minutes,
        }


@dataclass
class ArchitectureAnalysis:
    """Architecture-level analysis of the repository."""
    layer_structure: Dict[str, List[str]] = field(default_factory=dict)
    module_coupling: Dict[str, List[str]] = field(default_factory=dict)
    circular_dependencies: List[Tuple[str, str]] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    api_endpoints: List[Dict[str, str]] = field(default_factory=list)
    database_models: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "layer_structure": self.layer_structure,
            "module_coupling": self.module_coupling,
            "circular_dependencies": [list(c) for c in self.circular_dependencies],
            "entry_points": self.entry_points,
            "api_endpoint_count": len(self.api_endpoints),
            "database_model_count": len(self.database_models),
        }


@dataclass
class RepoSummary:
    """Comprehensive summary of a repository."""
    repo_root: str
    readme_path: Optional[str]
    readme_excerpt: Optional[str]
    cargo_workspace_members: List[str]
    notable_crates: List[str]
    env_vars: List[str]
    # Enhanced fields
    primary_language: Optional[str] = None
    frameworks_detected: List[str] = field(default_factory=list)
    build_systems: List[str] = field(default_factory=list)
    dependencies: List[DependencyInfo] = field(default_factory=list)
    security_findings: List[SecurityFinding] = field(default_factory=list)
    code_metrics: Optional[CodeMetrics] = None
    architecture: Optional[ArchitectureAnalysis] = None
    license_type: Optional[str] = None
    ci_cd_detected: List[str] = field(default_factory=list)
    documentation_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "repo_root": self.repo_root,
            "readme_path": self.readme_path,
            "primary_language": self.primary_language,
            "frameworks_detected": self.frameworks_detected,
            "build_systems": self.build_systems,
            "cargo_workspace_members": self.cargo_workspace_members,
            "notable_crates": self.notable_crates,
            "env_var_count": len(self.env_vars),
            "dependency_count": len(self.dependencies),
            "security_finding_count": len(self.security_findings),
            "code_metrics": self.code_metrics.to_dict() if self.code_metrics else None,
            "architecture": self.architecture.to_dict() if self.architecture else None,
            "license_type": self.license_type,
            "ci_cd_detected": self.ci_cd_detected,
            "documentation_score": round(self.documentation_score, 2),
        }


# ============================================================================
# Code Metrics Calculation
# ============================================================================

def _count_complexity_python(content: str) -> Tuple[int, int, int, int]:
    """Calculate cyclomatic complexity for Python code."""
    complexity = 1  # Base complexity
    cognitive = 0
    function_count = 0
    class_count = 0
    nesting_depth = 0

    # Patterns that increase cyclomatic complexity
    branch_patterns = [
        r'\bif\b', r'\belif\b', r'\bwhile\b', r'\bfor\b',
        r'\band\b', r'\bor\b', r'\bexcept\b', r'\bwith\b',
        r'\bcase\b', r'\?\s*:', r'\blambda\b',
    ]

    for pattern in branch_patterns:
        complexity += len(re.findall(pattern, content))

    # Count functions and classes
    function_count = len(re.findall(r'\bdef\s+\w+', content))
    class_count = len(re.findall(r'\bclass\s+\w+', content))

    # Cognitive complexity (simplified)
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(('if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except', 'with ')):
            cognitive += 1 + nesting_depth
            if stripped.endswith(':'):
                nesting_depth += 1
        elif stripped == '' or stripped.startswith('#'):
            pass
        elif not stripped.startswith(('def ', 'class ', 'return', 'pass', 'break', 'continue')):
            if nesting_depth > 0 and len(stripped) < len(line):
                nesting_depth = max(0, nesting_depth - 1)

    return complexity, cognitive, function_count, class_count


def _calculate_maintainability_index(
    loc: int, complexity: float, halstead_volume: float = 0
) -> float:
    """Calculate maintainability index (0-100 scale)."""
    if loc == 0:
        return 100.0

    # Microsoft's maintainability index formula (simplified)
    # MI = 171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(LOC)
    # Using simplified version without Halstead volume

    try:
        mi = 171 - 0.23 * complexity - 16.2 * math.log(loc + 1)
        if halstead_volume > 0:
            mi -= 5.2 * math.log(halstead_volume + 1)

        # Normalize to 0-100
        mi = max(0, min(100, (mi * 100) / 171))
        return mi
    except (ValueError, ZeroDivisionError):
        return 50.0


def analyze_code_quality(
    repo_root: Path,
    scan: RepoScan,
    *,
    languages: Optional[Set[str]] = None,
    max_files: int = 500,
) -> CodeMetrics:
    """Analyze code quality metrics for the repository."""
    total_loc = 0
    total_logical = 0
    total_comments = 0
    total_blank = 0
    total_complexity = 0
    total_cognitive = 0
    total_functions = 0
    total_classes = 0
    function_lengths: List[int] = []

    analyzed = 0
    for fi in scan.files:
        if analyzed >= max_files:
            break

        # Filter by language
        if languages and fi.language not in languages:
            continue

        if fi.language not in ("python", "javascript", "typescript", "rust", "go", "java"):
            continue

        try:
            content = read_text(repo_root, fi.path, max_chars=100_000)
        except OSError:
            continue

        analyzed += 1
        lines = content.splitlines()
        loc = len(lines)
        total_loc += loc

        # Count different line types
        for line in lines:
            stripped = line.strip()
            if not stripped:
                total_blank += 1
            elif stripped.startswith(('#', '//', '/*', '*', '"""', "'''")):
                total_comments += 1
            else:
                total_logical += 1

        # Calculate complexity (Python-specific for now)
        if fi.language == "python":
            cc, cog, funcs, classes = _count_complexity_python(content)
            total_complexity += cc
            total_cognitive += cog
            total_functions += funcs
            total_classes += classes

            # Extract function lengths
            func_matches = re.findall(
                r'def\s+\w+\s*\([^)]*\)\s*:.*?(?=\ndef|\nclass|\Z)',
                content,
                re.DOTALL,
            )
            for match in func_matches:
                func_lines = len(match.splitlines())
                function_lengths.append(func_lines)

    # Calculate aggregate metrics
    comment_ratio = (total_comments / total_loc * 100) if total_loc > 0 else 0
    avg_func_length = sum(function_lengths) / len(function_lengths) if function_lengths else 0
    max_func_length = max(function_lengths) if function_lengths else 0
    avg_complexity = total_complexity / total_functions if total_functions > 0 else 0

    maintainability = _calculate_maintainability_index(total_loc, total_complexity)

    # Estimate technical debt (simplified: 10 min per complexity point over threshold)
    tech_debt = max(0, (total_complexity - analyzed * 10)) * 10

    return CodeMetrics(
        cyclomatic_complexity=total_complexity,
        cognitive_complexity=total_cognitive,
        maintainability_index=maintainability,
        lines_of_code=total_loc,
        logical_lines=total_logical,
        comment_lines=total_comments,
        blank_lines=total_blank,
        comment_ratio=comment_ratio,
        function_count=total_functions,
        class_count=total_classes,
        avg_function_length=avg_func_length,
        max_function_length=max_func_length,
        avg_complexity_per_function=avg_complexity,
        technical_debt_minutes=tech_debt,
    )


# ============================================================================
# Security Scanning
# ============================================================================

def scan_security_issues(
    repo_root: Path,
    scan: RepoScan,
    *,
    severity_threshold: Severity = Severity.LOW,
    max_files: int = 1000,
    max_findings: int = 500,
) -> List[SecurityFinding]:
    """Scan repository for security vulnerabilities."""
    findings: List[SecurityFinding] = []
    severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    threshold_idx = severity_order.index(severity_threshold)

    scanned = 0
    for fi in scan.files:
        if scanned >= max_files or len(findings) >= max_findings:
            break

        # Skip binary files
        if fi.is_binary:
            continue

        # Focus on source and config files
        if fi.language not in (
            "python", "javascript", "typescript", "rust", "go", "java",
            "ruby", "php", "shell", "yaml", "json", "toml",
        ):
            continue

        try:
            content = read_text(repo_root, fi.path, max_chars=100_000)
        except OSError:
            continue

        scanned += 1
        lines = content.splitlines()

        for rule_id, (pattern, severity, message) in SECURITY_PATTERNS.items():
            if severity_order.index(severity) > threshold_idx:
                continue

            for line_no, line in enumerate(lines, 1):
                if pattern.search(line):
                    snippet = line.strip()[:200]
                    findings.append(SecurityFinding(
                        rule_id=rule_id,
                        severity=severity,
                        file_path=fi.path,
                        line_number=line_no,
                        message=message,
                        code_snippet=snippet,
                    ))

                    if len(findings) >= max_findings:
                        break

            if len(findings) >= max_findings:
                break

    # Sort by severity
    findings.sort(key=lambda f: severity_order.index(f.severity))
    return findings


# ============================================================================
# Dependency Extraction
# ============================================================================

def _parse_requirements_txt(content: str, source_file: str) -> List[DependencyInfo]:
    """Parse Python requirements.txt file."""
    deps: List[DependencyInfo] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue

        # Handle version specifiers
        match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[.*\])?(?:([<>=!~]+.*))?$', line)
        if match:
            name = match.group(1)
            version = match.group(2).strip() if match.group(2) else None
            deps.append(DependencyInfo(name=name, version=version, source_file=source_file))

    return deps


def _parse_package_json(content: str, source_file: str) -> List[DependencyInfo]:
    """Parse Node.js package.json file."""
    import json as json_module
    deps: List[DependencyInfo] = []

    try:
        data = json_module.loads(content)
    except json_module.JSONDecodeError:
        return deps

    for dep_type, is_dev in [("dependencies", False), ("devDependencies", True), ("peerDependencies", False)]:
        for name, version in data.get(dep_type, {}).items():
            deps.append(DependencyInfo(
                name=name,
                version=version,
                dep_type=DependencyType.DEV if is_dev else DependencyType.RUNTIME,
                source_file=source_file,
                is_dev=is_dev,
            ))

    return deps


def _parse_cargo_toml(content: str, source_file: str) -> List[DependencyInfo]:
    """Parse Rust Cargo.toml file."""
    deps: List[DependencyInfo] = []

    # Simple pattern matching for dependencies
    in_deps_section = False
    is_dev = False

    for line in content.splitlines():
        line = line.strip()

        if line.startswith('['):
            in_deps_section = 'dependencies' in line.lower()
            is_dev = 'dev-dependencies' in line.lower() or 'dev_dependencies' in line.lower()
            continue

        if in_deps_section and '=' in line:
            parts = line.split('=', 1)
            name = parts[0].strip()
            version_str = parts[1].strip().strip('"\'')

            # Handle inline table
            if version_str.startswith('{'):
                version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', version_str)
                version = version_match.group(1) if version_match else None
            else:
                version = version_str

            deps.append(DependencyInfo(
                name=name,
                version=version,
                dep_type=DependencyType.DEV if is_dev else DependencyType.RUNTIME,
                source_file=source_file,
                is_dev=is_dev,
            ))

    return deps


def _parse_pyproject_toml(content: str, source_file: str) -> List[DependencyInfo]:
    """Parse Python pyproject.toml file."""
    deps: List[DependencyInfo] = []

    # Extract from [project.dependencies]
    deps_match = re.search(r'\[project\]\s*.*?dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if deps_match:
        for line in deps_match.group(1).splitlines():
            line = line.strip().strip(',').strip('"\'')
            if line:
                match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[.*\])?(.*)$', line)
                if match:
                    deps.append(DependencyInfo(
                        name=match.group(1),
                        version=match.group(2).strip() or None,
                        source_file=source_file,
                    ))

    return deps


def extract_dependencies(repo_root: Path, scan: RepoScan) -> List[DependencyInfo]:
    """Extract all dependencies from the repository."""
    all_deps: List[DependencyInfo] = []

    dependency_files = {
        "requirements.txt": _parse_requirements_txt,
        "requirements-dev.txt": _parse_requirements_txt,
        "requirements_dev.txt": _parse_requirements_txt,
        "package.json": _parse_package_json,
        "Cargo.toml": _parse_cargo_toml,
        "pyproject.toml": _parse_pyproject_toml,
    }

    for fi in scan.files:
        filename = Path(fi.path).name
        if filename in dependency_files:
            try:
                content = read_text(repo_root, fi.path)
                parser = dependency_files[filename]
                deps = parser(content, fi.path)
                all_deps.extend(deps)
            except OSError:
                continue

    # Also look for requirements files in subdirectories
    for fi in scan.files:
        if fi.path.endswith("requirements.txt") and fi.path not in [f.source_file for f in all_deps]:
            try:
                content = read_text(repo_root, fi.path)
                deps = _parse_requirements_txt(content, fi.path)
                all_deps.extend(deps)
            except OSError:
                continue

    return all_deps


# ============================================================================
# Framework and Build System Detection
# ============================================================================

def detect_frameworks(repo_root: Path, scan: RepoScan) -> List[str]:
    """Detect frameworks and libraries used in the repository."""
    frameworks: Set[str] = set()

    framework_indicators = {
        # Python
        "django": ["django", "settings.py", "manage.py", "urls.py"],
        "flask": ["flask", "app.py", "application.py"],
        "fastapi": ["fastapi", "main.py"],
        "pytest": ["pytest", "conftest.py"],
        "tensorflow": ["tensorflow", "keras"],
        "pytorch": ["torch", "pytorch"],
        "pandas": ["pandas", "dataframe"],
        "numpy": ["numpy", "np."],
        # JavaScript/TypeScript
        "react": ["react", "jsx", "useState", "useEffect"],
        "vue": ["vue", ".vue", "createApp"],
        "angular": ["angular", "@angular", "NgModule"],
        "next.js": ["next", "next.config", "getServerSideProps"],
        "express": ["express", "app.listen", "router."],
        "nest.js": ["nestjs", "@nestjs", "@Controller"],
        # Rust
        "actix-web": ["actix-web", "HttpServer"],
        "tokio": ["tokio", "#[tokio::main]"],
        "axum": ["axum", "Router::new"],
        # Go
        "gin": ["gin-gonic", "gin.Default"],
        "echo": ["labstack/echo"],
        # General
        "graphql": ["graphql", "gql", "Query", "Mutation"],
        "grpc": ["grpc", "protobuf", ".proto"],
        "docker": ["Dockerfile", "docker-compose"],
        "kubernetes": ["kubernetes", "k8s", ".yaml"],
    }

    for fi in scan.files:
        filename = Path(fi.path).name.lower()
        for framework, indicators in framework_indicators.items():
            if any(ind.lower() in filename for ind in indicators):
                frameworks.add(framework)
                continue

        # Check file content for larger files
        if fi.size_bytes > 100 and fi.language in ("python", "javascript", "typescript", "rust", "go"):
            try:
                content = read_text(repo_root, fi.path, max_chars=10_000).lower()
                for framework, indicators in framework_indicators.items():
                    if framework not in frameworks:
                        if any(ind.lower() in content for ind in indicators):
                            frameworks.add(framework)
            except OSError:
                continue

    return sorted(frameworks)


def detect_build_systems(scan: RepoScan) -> List[str]:
    """Detect build systems used in the repository."""
    build_systems: Set[str] = set()

    build_indicators = {
        "cargo": ["Cargo.toml", "Cargo.lock"],
        "npm": ["package.json", "package-lock.json"],
        "yarn": ["yarn.lock"],
        "pnpm": ["pnpm-lock.yaml"],
        "pip": ["requirements.txt", "setup.py", "setup.cfg"],
        "poetry": ["pyproject.toml", "poetry.lock"],
        "pipenv": ["Pipfile", "Pipfile.lock"],
        "gradle": ["build.gradle", "build.gradle.kts", "settings.gradle"],
        "maven": ["pom.xml"],
        "cmake": ["CMakeLists.txt"],
        "make": ["Makefile", "makefile"],
        "bazel": ["BUILD", "WORKSPACE", ".bazelrc"],
        "meson": ["meson.build"],
        "sbt": ["build.sbt"],
        "go-mod": ["go.mod", "go.sum"],
    }

    file_names = {Path(f.path).name for f in scan.files}

    for build_sys, indicators in build_indicators.items():
        if any(ind in file_names for ind in indicators):
            build_systems.add(build_sys)

    return sorted(build_systems)


def detect_ci_cd(scan: RepoScan) -> List[str]:
    """Detect CI/CD systems configured in the repository."""
    ci_cd: Set[str] = set()

    ci_indicators = {
        "github-actions": [".github/workflows/"],
        "gitlab-ci": [".gitlab-ci.yml"],
        "travis-ci": [".travis.yml"],
        "circleci": [".circleci/config.yml", ".circleci/"],
        "jenkins": ["Jenkinsfile"],
        "azure-pipelines": ["azure-pipelines.yml"],
        "bitbucket-pipelines": ["bitbucket-pipelines.yml"],
        "drone": [".drone.yml"],
        "appveyor": ["appveyor.yml", ".appveyor.yml"],
    }

    for fi in scan.files:
        for ci_name, patterns in ci_indicators.items():
            if any(pat in fi.path for pat in patterns):
                ci_cd.add(ci_name)

    return sorted(ci_cd)


def detect_license(repo_root: Path, scan: RepoScan) -> Optional[str]:
    """Detect the license type of the repository."""
    license_patterns = {
        "MIT": re.compile(r'MIT License|Permission is hereby granted.*MIT', re.IGNORECASE),
        "Apache-2.0": re.compile(r'Apache License.*Version 2\.0|apache-2\.0', re.IGNORECASE),
        "GPL-3.0": re.compile(r'GNU GENERAL PUBLIC LICENSE.*Version 3|GPL-3\.0', re.IGNORECASE),
        "GPL-2.0": re.compile(r'GNU GENERAL PUBLIC LICENSE.*Version 2|GPL-2\.0', re.IGNORECASE),
        "BSD-3-Clause": re.compile(r'BSD 3-Clause|Redistribution and use.*three conditions', re.IGNORECASE),
        "BSD-2-Clause": re.compile(r'BSD 2-Clause|Simplified BSD', re.IGNORECASE),
        "ISC": re.compile(r'ISC License|ISC LICENSE', re.IGNORECASE),
        "MPL-2.0": re.compile(r'Mozilla Public License.*2\.0', re.IGNORECASE),
        "LGPL-3.0": re.compile(r'GNU LESSER GENERAL PUBLIC LICENSE.*Version 3', re.IGNORECASE),
        "Unlicense": re.compile(r'This is free and unencumbered software|UNLICENSE', re.IGNORECASE),
    }

    for fi in scan.files:
        filename = Path(fi.path).name.upper()
        if filename in ("LICENSE", "LICENSE.TXT", "LICENSE.MD", "COPYING"):
            try:
                content = read_text(repo_root, fi.path, max_chars=5000)
                for license_name, pattern in license_patterns.items():
                    if pattern.search(content):
                        return license_name
            except OSError:
                continue

    return None


# ============================================================================
# Original Functions (Enhanced)
# ============================================================================

def _find_readme(scan: RepoScan) -> Optional[str]:
    """Find README file in repository."""
    candidates = ["README.md", "readme.md", "README.MD", "README", "README.rst", "README.txt"]
    for candidate in candidates:
        if any(f.path == candidate for f in scan.files):
            return candidate
    return None


def _parse_workspace_members(cargo_toml: str) -> List[str]:
    """Parse workspace members from Cargo.toml."""
    m = re.search(r"(?s)\[workspace\].*?members\s*=\s*\[(.*?)\]", cargo_toml)
    if not m:
        return []
    body = m.group(1)
    return [s.strip().strip('"\'') for s in re.findall(r"['\"]([^'\"]+)['\"]", body)]


def _extract_env_vars(scan: RepoScan, repo_root: Path, *, prefix: str = "") -> List[str]:
    """Extract environment variables from repository files."""
    seen: Set[str] = set()
    # Match common env var patterns
    patterns = [
        re.compile(r'\b([A-Z][A-Z0-9_]{2,})\b'),  # General uppercase with underscores
    ]
    if prefix:
        patterns.insert(0, re.compile(r'\b(' + re.escape(prefix) + r'[A-Z0-9_]+)\b'))

    for fi in scan.files:
        if fi.is_binary:
            continue
        if fi.language not in ("python", "rust", "javascript", "typescript", "shell", "yaml", "toml", "markdown"):
            continue

        try:
            text = read_text(repo_root, fi.path, max_chars=200_000)
        except OSError:
            continue

        for rx in patterns:
            for v in rx.findall(text):
                # Filter out common false positives
                if v not in ("TRUE", "FALSE", "NULL", "NONE", "TODO", "FIXME", "NOTE"):
                    seen.add(v)

    return sorted(seen)[:500]  # Limit to 500 vars


def calculate_documentation_score(repo_root: Path, scan: RepoScan) -> float:
    """Calculate a documentation quality score (0-100)."""
    score = 0.0
    max_score = 100.0

    # Check for README
    if _find_readme(scan):
        score += 20

    # Check for docs directory
    has_docs = any("docs/" in f.path or "documentation/" in f.path for f in scan.files)
    if has_docs:
        score += 15

    # Check for code comments (sample)
    comment_files = 0
    files_checked = 0
    for fi in scan.files:
        if fi.language in ("python", "javascript", "typescript", "rust", "go", "java"):
            files_checked += 1
            if files_checked > 50:
                break
            try:
                content = read_text(repo_root, fi.path, max_chars=10_000)
                if re.search(r'(#|//|/\*|\"\"\"|\'\'\')', content):
                    comment_files += 1
            except OSError:
                continue

    if files_checked > 0:
        comment_ratio = comment_files / files_checked
        score += comment_ratio * 25

    # Check for CHANGELOG
    if any(Path(f.path).name.upper() in ("CHANGELOG.MD", "CHANGELOG", "CHANGES.MD", "HISTORY.MD") for f in scan.files):
        score += 10

    # Check for CONTRIBUTING
    if any("CONTRIBUTING" in Path(f.path).name.upper() for f in scan.files):
        score += 10

    # Check for API documentation or docstrings
    if any("api" in f.path.lower() and f.language == "markdown" for f in scan.files):
        score += 10

    # Check for examples directory
    if any("examples/" in f.path or "example/" in f.path for f in scan.files):
        score += 10

    return min(score, max_score)


def summarize_repo(
    repo_root: Path,
    scan: RepoScan,
    *,
    include_security: bool = True,
    include_metrics: bool = True,
    env_var_prefix: str = "",
) -> RepoSummary:
    """Create a comprehensive summary of the repository."""
    readme_path = _find_readme(scan)
    readme_excerpt = None
    if readme_path:
        try:
            readme_excerpt = read_text(repo_root, readme_path, max_chars=20_000)
        except OSError:
            readme_excerpt = None

    # Parse Cargo workspace
    cargo_workspace_members: List[str] = []
    if any(f.path == "Cargo.toml" for f in scan.files):
        try:
            cargo = read_text(repo_root, "Cargo.toml", max_chars=200_000)
            cargo_workspace_members = _parse_workspace_members(cargo)
        except OSError:
            pass

    # Notable crates heuristic
    notable = []
    notable_patterns = [
        "crates/meilisearch", "crates/milli", "crates/index-scheduler",
        "crates/meilitool", "crates/openapi-generator", "crates/xtask",
        "src/lib", "src/main", "src/core", "src/api",
    ]
    for n in notable_patterns:
        if any(f.path.startswith(n + "/") or f.path == n + ".rs" for f in scan.files):
            notable.append(n)

    # Extract environment variables
    env_vars = _extract_env_vars(scan, repo_root, prefix=env_var_prefix)

    # Enhanced analysis
    primary_language = scan.primary_language
    frameworks = detect_frameworks(repo_root, scan)
    build_systems = detect_build_systems(scan)
    dependencies = extract_dependencies(repo_root, scan)
    ci_cd = detect_ci_cd(scan)
    license_type = detect_license(repo_root, scan)
    doc_score = calculate_documentation_score(repo_root, scan)

    # Security scanning
    security_findings: List[SecurityFinding] = []
    if include_security:
        security_findings = scan_security_issues(repo_root, scan, max_findings=100)

    # Code metrics
    code_metrics = None
    if include_metrics:
        code_metrics = analyze_code_quality(repo_root, scan)

    return RepoSummary(
        repo_root=str(repo_root),
        readme_path=readme_path,
        readme_excerpt=readme_excerpt,
        cargo_workspace_members=cargo_workspace_members,
        notable_crates=notable,
        env_vars=env_vars,
        primary_language=primary_language,
        frameworks_detected=frameworks,
        build_systems=build_systems,
        dependencies=dependencies,
        security_findings=security_findings,
        code_metrics=code_metrics,
        license_type=license_type,
        ci_cd_detected=ci_cd,
        documentation_score=doc_score,
    )
