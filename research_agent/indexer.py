"""Advanced full-text indexing with TF-IDF scoring and fuzzy matching.

This module provides comprehensive text indexing capabilities including:
- Inverted index with TF-IDF scoring
- N-gram indexing for fuzzy matching
- Symbol extraction for code navigation
- Caching and persistence
- Semantic search preparation
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from .scanner import RepoScan, read_text


# ============================================================================
# Constants
# ============================================================================

# Token extraction patterns
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,50}")
_CAMEL_CASE_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SYMBOL_RE = re.compile(r"\b(?:class|def|function|const|let|var|fn|struct|enum|interface|type)\s+(\w+)")

# Stop words to exclude from indexing
STOP_WORDS: FrozenSet[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "self", "none",
    "true", "false", "null", "undefined", "return", "import", "from",
    "if", "else", "elif", "then", "end", "def", "class", "function",
})

# File extensions to skip in indexing
SKIP_EXTENSIONS: FrozenSet[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tar",
    ".ico", ".woff", ".woff2", ".ttf", ".eot", ".svg", ".mp3", ".mp4",
    ".avi", ".mov", ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo",
    ".class", ".jar", ".war", ".lock", ".wasm",
})


# ============================================================================
# Data Classes
# ============================================================================

class MatchType(Enum):
    """Type of search match."""
    EXACT = "exact"
    PREFIX = "prefix"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"


@dataclass(frozen=True)
class Match:
    """A single search match."""
    path: str
    line_no: int
    line: str
    column: int = 0
    match_type: MatchType = MatchType.EXACT

    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "line_no": self.line_no,
            "line": self.line,
            "column": self.column,
            "match_type": self.match_type.value,
        }


@dataclass
class SearchResult:
    """A search result with scoring information."""
    match: Match
    score: float
    tf_idf_score: float = 0.0
    term_frequency: int = 1
    matched_terms: List[str] = field(default_factory=list)
    highlights: List[Tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "match": self.match.to_dict(),
            "score": round(self.score, 4),
            "tf_idf_score": round(self.tf_idf_score, 4),
            "term_frequency": self.term_frequency,
            "matched_terms": self.matched_terms,
        }


@dataclass(frozen=True)
class SymbolInfo:
    """Information about a code symbol."""
    name: str
    kind: str  # class, function, variable, etc.
    path: str
    line_no: int
    signature: Optional[str] = None
    docstring: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "path": self.path,
            "line_no": self.line_no,
            "signature": self.signature,
        }


# ============================================================================
# TF-IDF Scorer
# ============================================================================

class TFIDFScorer:
    """TF-IDF (Term Frequency-Inverse Document Frequency) scorer."""

    def __init__(self):
        self.doc_count = 0
        self.term_doc_freq: Dict[str, int] = Counter()  # How many docs contain each term
        self.term_freq: Dict[str, Dict[str, int]] = defaultdict(Counter)  # term -> doc -> count
        self.doc_lengths: Dict[str, int] = {}  # doc -> total terms

    def add_document(self, doc_id: str, terms: List[str]) -> None:
        """Add a document to the scorer."""
        self.doc_count += 1
        self.doc_lengths[doc_id] = len(terms)

        seen_terms: Set[str] = set()
        for term in terms:
            self.term_freq[term][doc_id] += 1
            if term not in seen_terms:
                self.term_doc_freq[term] += 1
                seen_terms.add(term)

    def idf(self, term: str) -> float:
        """Calculate Inverse Document Frequency for a term."""
        if self.doc_count == 0:
            return 0.0
        doc_freq = self.term_doc_freq.get(term, 0)
        if doc_freq == 0:
            return 0.0
        return math.log((self.doc_count + 1) / (doc_freq + 1)) + 1

    def tf(self, term: str, doc_id: str) -> float:
        """Calculate Term Frequency (normalized)."""
        doc_length = self.doc_lengths.get(doc_id, 1)
        count = self.term_freq.get(term, {}).get(doc_id, 0)
        return count / doc_length if doc_length > 0 else 0.0

    def tf_idf(self, term: str, doc_id: str) -> float:
        """Calculate TF-IDF score for a term in a document."""
        return self.tf(term, doc_id) * self.idf(term)

    def score_query(self, terms: List[str], doc_id: str) -> float:
        """Score a multi-term query against a document."""
        return sum(self.tf_idf(term, doc_id) for term in terms)


# ============================================================================
# N-Gram Index
# ============================================================================

class NGramIndex:
    """N-gram index for fuzzy matching."""

    def __init__(self, n: int = 3):
        self.n = n
        self.ngram_to_tokens: Dict[str, Set[str]] = defaultdict(set)
        self.token_to_ngrams: Dict[str, Set[str]] = {}

    def _get_ngrams(self, token: str) -> List[str]:
        """Extract n-grams from a token."""
        padded = f"$${token}$$"  # Padding for edge n-grams
        return [padded[i:i + self.n] for i in range(len(padded) - self.n + 1)]

    def add_token(self, token: str) -> None:
        """Add a token to the n-gram index."""
        token_lower = token.lower()
        ngrams = set(self._get_ngrams(token_lower))
        self.token_to_ngrams[token_lower] = ngrams
        for ngram in ngrams:
            self.ngram_to_tokens[ngram].add(token_lower)

    def find_similar(self, query: str, threshold: float = 0.3, max_results: int = 20) -> List[Tuple[str, float]]:
        """Find tokens similar to query using Jaccard similarity."""
        query_lower = query.lower()
        query_ngrams = set(self._get_ngrams(query_lower))

        if not query_ngrams:
            return []

        # Find candidate tokens
        candidates: Set[str] = set()
        for ngram in query_ngrams:
            candidates.update(self.ngram_to_tokens.get(ngram, set()))

        # Calculate similarity scores
        results: List[Tuple[str, float]] = []
        for token in candidates:
            token_ngrams = self.token_to_ngrams.get(token, set())
            if not token_ngrams:
                continue

            # Jaccard similarity
            intersection = len(query_ngrams & token_ngrams)
            union = len(query_ngrams | token_ngrams)
            similarity = intersection / union if union > 0 else 0.0

            if similarity >= threshold:
                results.append((token, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: -x[1])
        return results[:max_results]


# ============================================================================
# Inverted Index
# ============================================================================

@dataclass
class InvertedIndex:
    """Full-text inverted index with advanced search capabilities."""
    token_to_matches: Dict[str, List[Match]]
    tfidf_scorer: TFIDFScorer = field(default_factory=TFIDFScorer)
    ngram_index: NGramIndex = field(default_factory=NGramIndex)
    symbols: List[SymbolInfo] = field(default_factory=list)
    file_token_counts: Dict[str, int] = field(default_factory=dict)
    total_tokens: int = 0
    total_documents: int = 0

    def search(
        self,
        query: str,
        *,
        max_results: int = 50,
        file_filter: Optional[Callable[[str], bool]] = None,
        use_fuzzy: bool = False,
        fuzzy_threshold: float = 0.5,
    ) -> List[SearchResult]:
        """Search the index with TF-IDF ranking.

        Args:
            query: Search query string
            max_results: Maximum results to return
            file_filter: Optional filter function for file paths
            use_fuzzy: Whether to use fuzzy matching
            fuzzy_threshold: Minimum similarity for fuzzy matches

        Returns:
            List of SearchResult objects sorted by relevance
        """
        tokens = [t.lower() for t in _WORD_RE.findall(query) if t.lower() not in STOP_WORDS]
        if not tokens:
            return []

        # Expand tokens with fuzzy matches if enabled
        expanded_tokens = list(tokens)
        if use_fuzzy:
            for token in tokens:
                similar = self.ngram_index.find_similar(token, threshold=fuzzy_threshold, max_results=5)
                for sim_token, score in similar:
                    if sim_token not in expanded_tokens:
                        expanded_tokens.append(sim_token)

        # Collect matches with AND semantics for original tokens
        sets: List[Dict[Tuple[str, int], Match]] = []
        for tok in tokens:
            hits = self.token_to_matches.get(tok, [])
            if file_filter:
                hits = [m for m in hits if file_filter(m.path)]
            sets.append({(m.path, m.line_no): m for m in hits})

        if not sets:
            return []

        # Find common matches (AND semantics)
        common_keys = set(sets[0].keys())
        for s in sets[1:]:
            common_keys &= set(s.keys())

        # Score results
        results: List[SearchResult] = []
        for key in common_keys:
            match = sets[0][key]
            doc_id = match.path

            # Calculate TF-IDF score
            tfidf_score = self.tfidf_scorer.score_query(expanded_tokens, doc_id)

            # Calculate term frequency in this specific line
            line_lower = match.line.lower()
            term_freq = sum(1 for t in expanded_tokens if t in line_lower)

            # Combined score
            score = tfidf_score + (term_freq * 0.1)

            results.append(SearchResult(
                match=match,
                score=score,
                tf_idf_score=tfidf_score,
                term_frequency=term_freq,
                matched_terms=tokens,
            ))

        # Sort by score descending
        results.sort(key=lambda r: -r.score)
        return results[:max_results]

    def search_prefix(self, prefix: str, *, max_results: int = 30) -> List[Match]:
        """Search for tokens starting with prefix."""
        prefix_lower = prefix.lower()
        matches: List[Match] = []

        for token, token_matches in self.token_to_matches.items():
            if token.startswith(prefix_lower):
                matches.extend(token_matches[:5])  # Limit per token
                if len(matches) >= max_results * 2:
                    break

        # Deduplicate
        seen: Set[Tuple[str, int]] = set()
        unique: List[Match] = []
        for m in matches:
            key = (m.path, m.line_no)
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return unique[:max_results]

    def search_symbols(
        self,
        query: str,
        *,
        kind: Optional[str] = None,
        max_results: int = 30,
    ) -> List[SymbolInfo]:
        """Search for code symbols."""
        query_lower = query.lower()
        results: List[SymbolInfo] = []

        for symbol in self.symbols:
            if kind and symbol.kind != kind:
                continue

            if query_lower in symbol.name.lower():
                results.append(symbol)
                if len(results) >= max_results:
                    break

        return results

    def get_file_terms(self, file_path: str) -> List[str]:
        """Get all indexed terms for a file."""
        terms: List[str] = []
        for token, matches in self.token_to_matches.items():
            if any(m.path == file_path for m in matches):
                terms.append(token)
        return terms

    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_tokens": len(self.token_to_matches),
            "total_matches": sum(len(m) for m in self.token_to_matches.values()),
            "total_documents": self.total_documents,
            "total_symbols": len(self.symbols),
            "avg_matches_per_token": (
                sum(len(m) for m in self.token_to_matches.values()) / len(self.token_to_matches)
                if self.token_to_matches else 0
            ),
        }

    def to_dict(self) -> Dict:
        """Serialize index to dictionary (for caching)."""
        return {
            "token_to_matches": {
                k: [m.to_dict() for m in v]
                for k, v in self.token_to_matches.items()
            },
            "symbols": [s.to_dict() for s in self.symbols],
            "file_token_counts": self.file_token_counts,
            "total_tokens": self.total_tokens,
            "total_documents": self.total_documents,
        }


# ============================================================================
# Token Extraction
# ============================================================================

def _split_camel_case(token: str) -> List[str]:
    """Split camelCase and PascalCase tokens."""
    return _CAMEL_CASE_RE.split(token)


def _extract_tokens(line: str, *, split_camel: bool = True) -> List[str]:
    """Extract tokens from a line of text."""
    tokens: List[str] = []

    for match in _WORD_RE.findall(line):
        token = match.lower()
        if token not in STOP_WORDS and len(token) >= 2:
            tokens.append(token)

            # Also index camelCase parts
            if split_camel and any(c.isupper() for c in match[1:]):
                for part in _split_camel_case(match):
                    part_lower = part.lower()
                    if len(part_lower) >= 2 and part_lower not in STOP_WORDS:
                        tokens.append(part_lower)

    return tokens


def _extract_symbols(content: str, file_path: str) -> List[SymbolInfo]:
    """Extract code symbols from content."""
    symbols: List[SymbolInfo] = []
    lines = content.splitlines()

    # Python patterns
    py_patterns = [
        (r"^\s*class\s+(\w+)", "class"),
        (r"^\s*def\s+(\w+)", "function"),
        (r"^\s*async\s+def\s+(\w+)", "function"),
        (r"^(\w+)\s*=\s*", "variable"),
    ]

    # JavaScript/TypeScript patterns
    js_patterns = [
        (r"^\s*class\s+(\w+)", "class"),
        (r"^\s*(?:async\s+)?function\s+(\w+)", "function"),
        (r"^\s*(?:export\s+)?const\s+(\w+)", "constant"),
        (r"^\s*(?:export\s+)?let\s+(\w+)", "variable"),
        (r"^\s*(?:export\s+)?interface\s+(\w+)", "interface"),
        (r"^\s*(?:export\s+)?type\s+(\w+)", "type"),
    ]

    # Rust patterns
    rs_patterns = [
        (r"^\s*(?:pub\s+)?struct\s+(\w+)", "struct"),
        (r"^\s*(?:pub\s+)?enum\s+(\w+)", "enum"),
        (r"^\s*(?:pub\s+)?fn\s+(\w+)", "function"),
        (r"^\s*(?:pub\s+)?trait\s+(\w+)", "trait"),
        (r"^\s*(?:pub\s+)?type\s+(\w+)", "type"),
        (r"^\s*impl(?:\s+\w+)?\s+(?:for\s+)?(\w+)", "impl"),
    ]

    # Select patterns based on file extension
    ext = Path(file_path).suffix.lower()
    patterns = []
    if ext in (".py", ".pyi"):
        patterns = py_patterns
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        patterns = js_patterns
    elif ext == ".rs":
        patterns = rs_patterns

    for line_no, line in enumerate(lines, 1):
        for pattern, kind in patterns:
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                # Skip private/internal
                if name.startswith("_") and kind not in ("function", "class"):
                    continue

                symbols.append(SymbolInfo(
                    name=name,
                    kind=kind,
                    path=file_path,
                    line_no=line_no,
                    signature=line.strip()[:100],
                ))
                break

    return symbols


# ============================================================================
# Index Building
# ============================================================================

def build_index(
    repo_root: Path,
    scan: RepoScan,
    *,
    max_matches_per_token: int = 300,
    max_file_size: int = 500_000,
    include_symbols: bool = True,
    include_ngrams: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> InvertedIndex:
    """Build a comprehensive full-text index of the repository.

    Args:
        repo_root: Repository root path
        scan: Previous scan results
        max_matches_per_token: Maximum matches to store per token
        max_file_size: Maximum file size to index
        include_symbols: Whether to extract code symbols
        include_ngrams: Whether to build n-gram index
        progress_callback: Optional progress callback(current, total)

    Returns:
        InvertedIndex with search capabilities
    """
    token_to_matches: Dict[str, List[Match]] = defaultdict(list)
    tfidf_scorer = TFIDFScorer()
    ngram_index = NGramIndex() if include_ngrams else NGramIndex()
    symbols: List[SymbolInfo] = []
    file_token_counts: Dict[str, int] = {}
    total_tokens = 0
    indexed_files = 0

    total_files = len(scan.files)

    for idx, fi in enumerate(scan.files):
        if progress_callback and idx % 50 == 0:
            progress_callback(idx, total_files)

        # Skip binary and large files
        ext = Path(fi.path).suffix.lower()
        if ext in SKIP_EXTENSIONS:
            continue
        if fi.size_bytes > max_file_size:
            continue

        try:
            text = read_text(repo_root, fi.path, max_chars=max_file_size)
        except OSError:
            continue

        indexed_files += 1
        doc_tokens: List[str] = []

        for line_no, line in enumerate(text.splitlines(), start=1):
            # Skip very long lines
            if len(line) > 2000:
                continue

            tokens = _extract_tokens(line)
            doc_tokens.extend(tokens)

            for tok in tokens:
                bucket = token_to_matches[tok]
                if len(bucket) < max_matches_per_token:
                    # Find column of first occurrence
                    col = line.lower().find(tok)
                    bucket.append(Match(
                        path=fi.path,
                        line_no=line_no,
                        line=line.strip(),
                        column=col if col >= 0 else 0,
                    ))

        # Update TF-IDF scorer
        tfidf_scorer.add_document(fi.path, doc_tokens)
        file_token_counts[fi.path] = len(doc_tokens)
        total_tokens += len(doc_tokens)

        # Update n-gram index
        if include_ngrams:
            for tok in set(doc_tokens):
                ngram_index.add_token(tok)

        # Extract symbols
        if include_symbols and fi.language in ("python", "javascript", "typescript", "rust"):
            file_symbols = _extract_symbols(text, fi.path)
            symbols.extend(file_symbols)

    return InvertedIndex(
        token_to_matches=dict(token_to_matches),
        tfidf_scorer=tfidf_scorer,
        ngram_index=ngram_index,
        symbols=symbols,
        file_token_counts=file_token_counts,
        total_tokens=total_tokens,
        total_documents=indexed_files,
    )


# ============================================================================
# Index Caching
# ============================================================================

def get_cache_key(repo_root: Path, scan: RepoScan) -> str:
    """Generate a cache key for the index."""
    # Combine file paths and sizes for a simple content hash
    content = f"{repo_root}:{scan.total_bytes}:{len(scan.files)}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def save_index_cache(index: InvertedIndex, cache_path: Path) -> None:
    """Save index to cache file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = index.to_dict()
    cache_path.write_text(json.dumps(data), encoding="utf-8")


def load_index_cache(cache_path: Path) -> Optional[Dict]:
    """Load index from cache file."""
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
