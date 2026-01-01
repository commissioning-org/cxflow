"""
CXFlow Jupyter Book Search Engine

Full-text search capabilities for built documentation sites.
Supports fuzzy matching, highlighting, and faceted search.
"""

from __future__ import annotations

import re
import json
import math
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Text Processing
# ============================================================================

# Common English stop words
STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
    'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that',
    'the', 'to', 'was', 'were', 'will', 'with', 'this', 'but', 'they',
    'have', 'had', 'what', 'when', 'where', 'who', 'which', 'why', 'how',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
    'than', 'too', 'very', 'just', 'can', 'should', 'now',
}

# Porter stemmer suffix rules (simplified)
SUFFIX_RULES = [
    ('ational', 'ate'), ('tional', 'tion'), ('enci', 'ence'),
    ('anci', 'ance'), ('izer', 'ize'), ('isation', 'ize'),
    ('ization', 'ize'), ('ation', 'ate'), ('ator', 'ate'),
    ('alism', 'al'), ('iveness', 'ive'), ('fulness', 'ful'),
    ('ousness', 'ous'), ('aliti', 'al'), ('iviti', 'ive'),
    ('biliti', 'ble'), ('alli', 'al'), ('entli', 'ent'),
    ('eli', 'e'), ('ousli', 'ous'), ('logi', 'log'),
    ('ies', 'y'), ('es', 'e'), ('s', ''),
    ('eed', 'ee'), ('ed', ''), ('ing', ''),
]


class TextProcessor:
    """
    Text processing utilities for search indexing.
    """
    
    def __init__(
        self,
        stop_words: Optional[Set[str]] = None,
        min_word_length: int = 2,
        use_stemming: bool = True,
    ):
        self.stop_words = stop_words or STOP_WORDS
        self.min_word_length = min_word_length
        self.use_stemming = use_stemming
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', ' ', text)
        text = re.sub(r'`[^`]+`', ' ', text)
        
        # Remove special characters but keep alphanumeric and hyphens
        text = re.sub(r'[^\w\s\-]', ' ', text)
        
        # Split on whitespace
        words = text.lower().split()
        
        # Filter by length and stop words
        tokens = [
            w for w in words
            if len(w) >= self.min_word_length and w not in self.stop_words
        ]
        
        # Apply stemming
        if self.use_stemming:
            tokens = [self.stem(t) for t in tokens]
        
        return tokens
    
    def stem(self, word: str) -> str:
        """
        Apply simple stemming to a word.
        
        Args:
            word: Input word
            
        Returns:
            Stemmed word
        """
        for suffix, replacement in SUFFIX_RULES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                return word[:-len(suffix)] + replacement
        return word
    
    def extract_excerpt(
        self,
        text: str,
        query: str,
        max_length: int = 200,
    ) -> str:
        """
        Extract a relevant excerpt from text.
        
        Args:
            text: Full text
            query: Search query
            max_length: Maximum excerpt length
            
        Returns:
            Relevant excerpt
        """
        # Clean text
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not text:
            return ''
        
        # Find query terms in text
        query_terms = self.tokenize(query)
        if not query_terms:
            return text[:max_length] + ('...' if len(text) > max_length else '')
        
        # Find best position
        best_pos = 0
        best_score = 0
        
        words = text.lower().split()
        for i, word in enumerate(words):
            stemmed = self.stem(word)
            if stemmed in query_terms:
                # Score based on position (prefer earlier matches)
                score = len(query_terms) - (i / len(words))
                if score > best_score:
                    best_score = score
                    best_pos = i
        
        # Calculate character position
        char_pos = len(' '.join(words[:best_pos]))
        start = max(0, char_pos - max_length // 3)
        end = start + max_length
        
        # Adjust to word boundaries
        if start > 0:
            start = text.find(' ', start) + 1
        if end < len(text):
            space_pos = text.find(' ', end)
            if space_pos > 0:
                end = space_pos
        
        excerpt = text[start:end]
        
        # Add ellipsis
        if start > 0:
            excerpt = '...' + excerpt
        if end < len(text):
            excerpt = excerpt + '...'
        
        return excerpt
    
    def highlight(
        self,
        text: str,
        query: str,
        before: str = '<mark>',
        after: str = '</mark>',
    ) -> str:
        """
        Highlight query terms in text.
        
        Args:
            text: Input text
            query: Search query
            before: Opening highlight tag
            after: Closing highlight tag
            
        Returns:
            Text with highlighted terms
        """
        query_terms = set(self.tokenize(query))
        if not query_terms:
            return text
        
        def replace_match(match):
            word = match.group(0)
            if self.stem(word.lower()) in query_terms:
                return f'{before}{word}{after}'
            return word
        
        # Match words
        pattern = r'\b\w+\b'
        return re.sub(pattern, replace_match, text)


# ============================================================================
# Search Index
# ============================================================================

@dataclass
class SearchDocument:
    """A searchable document."""
    id: str
    url: str
    title: str
    content: str
    section: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'section': self.section,
            'tags': self.tags,
            'headings': self.headings,
            'metadata': self.metadata,
        }


@dataclass
class SearchResult:
    """A search result."""
    document: SearchDocument
    score: float
    excerpt: str = ''
    highlights: Dict[str, str] = field(default_factory=dict)
    matched_terms: List[str] = field(default_factory=list)


class SearchIndex:
    """
    Inverted index for full-text search.
    """
    
    def __init__(self, processor: Optional[TextProcessor] = None):
        self.processor = processor or TextProcessor()
        
        # Inverted index: term -> {doc_id: [positions]}
        self._index: Dict[str, Dict[str, List[int]]] = defaultdict(dict)
        
        # Document storage
        self._documents: Dict[str, SearchDocument] = {}
        
        # Document term frequencies
        self._term_freqs: Dict[str, Dict[str, int]] = defaultdict(dict)
        
        # Document lengths (for normalization)
        self._doc_lengths: Dict[str, int] = {}
        
        # Average document length
        self._avg_doc_length: float = 0
        
        # Field weights for scoring
        self._field_weights = {
            'title': 5.0,
            'headings': 3.0,
            'content': 1.0,
            'tags': 2.0,
        }
    
    @property
    def document_count(self) -> int:
        """Get number of indexed documents."""
        return len(self._documents)
    
    def add_document(self, doc: SearchDocument):
        """
        Add a document to the index.
        
        Args:
            doc: Document to index
        """
        self._documents[doc.id] = doc
        
        # Index each field with weights
        all_terms = []
        
        # Index title
        title_terms = self.processor.tokenize(doc.title)
        for pos, term in enumerate(title_terms):
            if doc.id not in self._index[term]:
                self._index[term][doc.id] = []
            self._index[term][doc.id].append(pos)
        all_terms.extend(title_terms)
        
        # Index headings
        offset = len(title_terms)
        for heading in doc.headings:
            heading_terms = self.processor.tokenize(heading)
            for pos, term in enumerate(heading_terms):
                if doc.id not in self._index[term]:
                    self._index[term][doc.id] = []
                self._index[term][doc.id].append(offset + pos)
            all_terms.extend(heading_terms)
            offset += len(heading_terms)
        
        # Index content
        content_terms = self.processor.tokenize(doc.content)
        for pos, term in enumerate(content_terms):
            if doc.id not in self._index[term]:
                self._index[term][doc.id] = []
            self._index[term][doc.id].append(offset + pos)
        all_terms.extend(content_terms)
        
        # Index tags
        offset += len(content_terms)
        for tag in doc.tags:
            tag_terms = self.processor.tokenize(tag)
            for pos, term in enumerate(tag_terms):
                if doc.id not in self._index[term]:
                    self._index[term][doc.id] = []
                self._index[term][doc.id].append(offset + pos)
            all_terms.extend(tag_terms)
        
        # Calculate term frequencies
        for term in all_terms:
            if term not in self._term_freqs[doc.id]:
                self._term_freqs[doc.id][term] = 0
            self._term_freqs[doc.id][term] += 1
        
        # Store document length
        self._doc_lengths[doc.id] = len(all_terms)
        
        # Update average document length
        total_length = sum(self._doc_lengths.values())
        self._avg_doc_length = total_length / len(self._doc_lengths)
    
    def remove_document(self, doc_id: str):
        """Remove a document from the index."""
        if doc_id not in self._documents:
            return
        
        # Remove from inverted index
        for term in self._term_freqs.get(doc_id, {}).keys():
            if term in self._index and doc_id in self._index[term]:
                del self._index[term][doc_id]
                if not self._index[term]:
                    del self._index[term]
        
        # Remove document data
        del self._documents[doc_id]
        if doc_id in self._term_freqs:
            del self._term_freqs[doc_id]
        if doc_id in self._doc_lengths:
            del self._doc_lengths[doc_id]
        
        # Update average
        if self._doc_lengths:
            total = sum(self._doc_lengths.values())
            self._avg_doc_length = total / len(self._doc_lengths)
    
    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> Tuple[List[SearchResult], int]:
        """
        Search the index.
        
        Args:
            query: Search query
            limit: Maximum results
            offset: Results offset for pagination
            filters: Field filters (e.g., {'tags': ['python']})
            min_score: Minimum score threshold
            
        Returns:
            Tuple of (results, total_count)
        """
        query_terms = self.processor.tokenize(query)
        
        if not query_terms:
            return [], 0
        
        # Find matching documents
        doc_scores: Dict[str, float] = defaultdict(float)
        matched_terms: Dict[str, Set[str]] = defaultdict(set)
        
        for term in query_terms:
            if term not in self._index:
                continue
            
            # Calculate IDF
            df = len(self._index[term])  # Document frequency
            idf = math.log((self.document_count + 1) / (df + 1)) + 1
            
            for doc_id, positions in self._index[term].items():
                # Calculate TF (with log normalization)
                tf = 1 + math.log(len(positions))
                
                # BM25-like length normalization
                doc_length = self._doc_lengths.get(doc_id, 1)
                k1 = 1.5
                b = 0.75
                length_norm = (1 - b + b * doc_length / self._avg_doc_length)
                
                # Calculate score
                score = (tf * idf) / (tf + k1 * length_norm)
                
                # Apply field boost (simplified - assumes title terms appear first)
                if positions and positions[0] < 10:  # Likely in title
                    score *= self._field_weights['title']
                
                doc_scores[doc_id] += score
                matched_terms[doc_id].add(term)
        
        # Apply filters
        if filters:
            doc_scores = self._apply_filters(doc_scores, filters)
        
        # Filter by minimum score
        doc_scores = {
            doc_id: score
            for doc_id, score in doc_scores.items()
            if score >= min_score
        }
        
        # Sort by score
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        total_count = len(sorted_docs)
        
        # Apply pagination
        paginated = sorted_docs[offset:offset + limit]
        
        # Build results
        results = []
        for doc_id, score in paginated:
            doc = self._documents[doc_id]
            
            # Generate excerpt
            excerpt = self.processor.extract_excerpt(doc.content, query)
            
            # Highlight
            highlighted_title = self.processor.highlight(doc.title, query)
            highlighted_excerpt = self.processor.highlight(excerpt, query)
            
            results.append(SearchResult(
                document=doc,
                score=score,
                excerpt=excerpt,
                highlights={
                    'title': highlighted_title,
                    'excerpt': highlighted_excerpt,
                },
                matched_terms=list(matched_terms[doc_id]),
            ))
        
        return results, total_count
    
    def _apply_filters(
        self,
        doc_scores: Dict[str, float],
        filters: Dict[str, Any],
    ) -> Dict[str, float]:
        """Apply filters to search results."""
        filtered = {}
        
        for doc_id, score in doc_scores.items():
            doc = self._documents[doc_id]
            match = True
            
            for field, value in filters.items():
                if field == 'tags':
                    if isinstance(value, list):
                        if not any(tag in doc.tags for tag in value):
                            match = False
                    elif value not in doc.tags:
                        match = False
                
                elif field == 'section':
                    if doc.section != value:
                        match = False
                
                elif field in doc.metadata:
                    if doc.metadata[field] != value:
                        match = False
            
            if match:
                filtered[doc_id] = score
        
        return filtered
    
    def suggest(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Get search suggestions based on prefix.
        
        Args:
            prefix: Search prefix
            limit: Maximum suggestions
            
        Returns:
            List of suggested terms
        """
        prefix = prefix.lower()
        suggestions = []
        
        for term in self._index.keys():
            if term.startswith(prefix):
                # Score by document frequency
                df = len(self._index[term])
                suggestions.append((term, df))
        
        # Sort by frequency and take top results
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in suggestions[:limit]]
    
    def get_facets(self, field: str) -> Dict[str, int]:
        """
        Get facet counts for a field.
        
        Args:
            field: Field name (e.g., 'tags', 'section')
            
        Returns:
            Dict mapping values to counts
        """
        facets: Dict[str, int] = defaultdict(int)
        
        for doc in self._documents.values():
            if field == 'tags':
                for tag in doc.tags:
                    facets[tag] += 1
            elif field == 'section' and doc.section:
                facets[doc.section] += 1
            elif field in doc.metadata:
                value = doc.metadata[field]
                if isinstance(value, list):
                    for v in value:
                        facets[str(v)] += 1
                else:
                    facets[str(value)] += 1
        
        return dict(facets)


# ============================================================================
# Search Index Builder
# ============================================================================

class SearchIndexBuilder:
    """
    Builds search index from book content.
    """
    
    def __init__(self):
        self.index = SearchIndex()
        self._processed_files: Set[str] = set()
    
    def index_markdown(
        self,
        content: str,
        url: str,
        title: Optional[str] = None,
        source_file: Optional[str] = None,
        section: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Index Markdown content.
        
        Args:
            content: Markdown content
            url: Page URL
            title: Page title
            source_file: Source file path
            section: Section/chapter name
            tags: Content tags
        """
        # Generate document ID
        doc_id = hashlib.md5(url.encode()).hexdigest()[:12]
        
        # Extract title from content if not provided
        if not title:
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else Path(url).stem
        
        # Extract headings
        headings = re.findall(r'^#{1,6}\s+(.+)$', content, re.MULTILINE)
        
        # Extract tags from frontmatter if not provided
        if not tags:
            tags = []
            fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if fm_match:
                import yaml
                try:
                    fm = yaml.safe_load(fm_match.group(1))
                    tags = fm.get('tags', []) or fm.get('keywords', []) or []
                except Exception:
                    pass
        
        # Clean content (remove code blocks, frontmatter, etc.)
        clean_content = self._clean_markdown(content)
        
        # Create document
        doc = SearchDocument(
            id=doc_id,
            url=url,
            title=title,
            content=clean_content,
            section=section,
            tags=tags,
            headings=headings,
            metadata={'source_file': source_file} if source_file else {},
        )
        
        self.index.add_document(doc)
        self._processed_files.add(source_file or url)
    
    def index_notebook(
        self,
        notebook: Dict[str, Any],
        url: str,
        source_file: Optional[str] = None,
    ):
        """
        Index Jupyter notebook.
        
        Args:
            notebook: Notebook dictionary (parsed JSON)
            url: Page URL
            source_file: Source file path
        """
        # Extract markdown content from cells
        content_parts = []
        headings = []
        title = None
        
        for cell in notebook.get('cells', []):
            if cell['cell_type'] == 'markdown':
                source = ''.join(cell.get('source', []))
                content_parts.append(source)
                
                # Extract headings
                cell_headings = re.findall(r'^#{1,6}\s+(.+)$', source, re.MULTILINE)
                headings.extend(cell_headings)
                
                # Get title from first h1
                if not title:
                    title_match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
                    if title_match:
                        title = title_match.group(1)
            
            elif cell['cell_type'] == 'code':
                # Index code comments
                source = ''.join(cell.get('source', []))
                comments = re.findall(r'#\s*(.+)$', source, re.MULTILINE)
                content_parts.extend(comments)
        
        content = '\n\n'.join(content_parts)
        
        self.index_markdown(
            content=content,
            url=url,
            title=title,
            source_file=source_file,
            tags=['notebook'],
        )
    
    def index_directory(
        self,
        content_dir: Path,
        base_url: str = '/',
        section_map: Optional[Dict[str, str]] = None,
    ):
        """
        Index all content in a directory.
        
        Args:
            content_dir: Content directory path
            base_url: Base URL for generated links
            section_map: Optional mapping of paths to sections
        """
        content_dir = Path(content_dir)
        section_map = section_map or {}
        
        # Index Markdown files
        for md_file in content_dir.rglob('*.md'):
            if md_file.name.startswith('_'):
                continue
            
            rel_path = md_file.relative_to(content_dir)
            url = base_url + str(rel_path).replace('.md', '.html')
            
            # Determine section
            section = None
            for pattern, sec_name in section_map.items():
                if pattern in str(rel_path):
                    section = sec_name
                    break
            
            content = md_file.read_text(encoding='utf-8')
            self.index_markdown(
                content=content,
                url=url,
                source_file=str(md_file),
                section=section,
            )
        
        # Index notebooks
        for nb_file in content_dir.rglob('*.ipynb'):
            if nb_file.name.startswith('_'):
                continue
            
            rel_path = nb_file.relative_to(content_dir)
            url = base_url + str(rel_path).replace('.ipynb', '.html')
            
            try:
                notebook = json.loads(nb_file.read_text(encoding='utf-8'))
                self.index_notebook(
                    notebook=notebook,
                    url=url,
                    source_file=str(nb_file),
                )
            except Exception as e:
                logger.warning(f"Failed to index notebook {nb_file}: {e}")
    
    def _clean_markdown(self, content: str) -> str:
        """Clean Markdown for indexing."""
        # Remove frontmatter
        content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        
        # Remove code blocks
        content = re.sub(r'```[\s\S]*?```', ' ', content)
        content = re.sub(r'`[^`]+`', ' ', content)
        
        # Remove directives
        content = re.sub(r'\{[a-z]+\}`.+?`', ' ', content)
        
        # Remove HTML
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Remove links but keep text
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
        
        # Remove images
        content = re.sub(r'!\[[^\]]*\]\([^)]+\)', ' ', content)
        
        # Remove reference-style links
        content = re.sub(r'^\[[^\]]+\]:\s*.+$', '', content, flags=re.MULTILINE)
        
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
    
    def build(self) -> SearchIndex:
        """
        Finalize and return the search index.
        
        Returns:
            Completed SearchIndex
        """
        logger.info(f"Built search index with {self.index.document_count} documents")
        return self.index
    
    def export_json(self, output_path: Path):
        """
        Export search index to JSON.
        
        Args:
            output_path: Output file path
        """
        # Export document data for client-side search
        data = []
        
        for doc in self.index._documents.values():
            excerpt = doc.content[:300] + '...' if len(doc.content) > 300 else doc.content
            
            data.append({
                'id': doc.id,
                'url': doc.url,
                'title': doc.title,
                'content': doc.content[:1000],  # Limit content for file size
                'excerpt': excerpt,
                'section': doc.section,
                'tags': doc.tags,
                'headings': doc.headings[:5],  # Limit headings
            })
        
        output_path = Path(output_path)
        output_path.write_text(json.dumps(data, indent=2))
        
        logger.info(f"Exported search index to {output_path}")


# ============================================================================
# Fuzzy Search
# ============================================================================

class FuzzyMatcher:
    """
    Fuzzy string matching for typo-tolerant search.
    """
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate Levenshtein edit distance.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @classmethod
    def similarity(cls, s1: str, s2: str) -> float:
        """
        Calculate string similarity (0-1).
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity score (1 = identical)
        """
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        
        distance = cls.levenshtein_distance(s1.lower(), s2.lower())
        return 1 - (distance / max_len)
    
    @classmethod
    def find_matches(
        cls,
        query: str,
        candidates: List[str],
        threshold: float = 0.7,
    ) -> List[Tuple[str, float]]:
        """
        Find fuzzy matches above threshold.
        
        Args:
            query: Query string
            candidates: List of candidate strings
            threshold: Minimum similarity threshold
            
        Returns:
            List of (match, score) tuples sorted by score
        """
        matches = []
        
        for candidate in candidates:
            score = cls.similarity(query, candidate)
            if score >= threshold:
                matches.append((candidate, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches


# ============================================================================
# Search API
# ============================================================================

class SearchService:
    """
    High-level search service API.
    """
    
    def __init__(self, index: SearchIndex):
        self.index = index
        self.fuzzy = FuzzyMatcher()
    
    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        fuzzy: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform a search with JSON-serializable response.
        
        Args:
            query: Search query
            limit: Maximum results
            offset: Results offset
            filters: Field filters
            fuzzy: Enable fuzzy matching
            
        Returns:
            Search response dict
        """
        results, total = self.index.search(query, limit, offset, filters)
        
        # Convert to JSON-serializable format
        items = []
        for r in results:
            items.append({
                'id': r.document.id,
                'url': r.document.url,
                'title': r.document.title,
                'section': r.document.section,
                'score': round(r.score, 3),
                'excerpt': r.excerpt,
                'highlights': r.highlights,
                'matched_terms': r.matched_terms,
            })
        
        response = {
            'query': query,
            'total': total,
            'offset': offset,
            'limit': limit,
            'results': items,
        }
        
        # Add suggestions if no results
        if not items and fuzzy:
            terms = self.index.processor.tokenize(query)
            suggestions = []
            for term in terms:
                term_suggestions = self.index.suggest(term[:3], limit=5)
                suggestions.extend(term_suggestions)
            response['suggestions'] = list(set(suggestions))[:10]
        
        return response
    
    def get_facets(self, fields: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Get facets for multiple fields.
        
        Args:
            fields: List of field names
            
        Returns:
            Dict mapping fields to facet counts
        """
        return {
            field: self.index.get_facets(field)
            for field in fields
        }
    
    def suggest(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Get autocomplete suggestions.
        
        Args:
            prefix: Search prefix
            limit: Maximum suggestions
            
        Returns:
            List of suggestions
        """
        return self.index.suggest(prefix, limit)
