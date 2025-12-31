"""
Cross-Reference and Citation Management

Advanced cross-referencing system for linking between documents,
citing bibliography entries, and managing glossary terms.
"""

from __future__ import annotations

import re
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from enum import Enum
import logging

import yaml

logger = logging.getLogger(__name__)


# ============================================================================
# Reference Types and Models
# ============================================================================

class ReferenceType(str, Enum):
    """Types of cross-references."""
    SECTION = "section"
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    CODE = "code"
    FOOTNOTE = "footnote"
    CITATION = "citation"
    GLOSSARY = "glossary"
    DOCUMENT = "document"
    EXTERNAL = "external"


@dataclass
class Reference:
    """A cross-reference target."""
    id: str
    type: ReferenceType
    title: Optional[str] = None
    number: Optional[str] = None
    source_file: Optional[str] = None
    anchor: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Reference):
            return self.id == other.id
        return False


@dataclass
class Citation:
    """A bibliography citation."""
    key: str
    type: str  # article, book, inproceedings, etc.
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_bibtex(cls, entry: Dict[str, Any]) -> "Citation":
        """Create citation from BibTeX entry."""
        return cls(
            key=entry.get('ID', entry.get('key', '')),
            type=entry.get('ENTRYTYPE', 'misc'),
            title=entry.get('title', 'Untitled'),
            authors=cls._parse_authors(entry.get('author', '')),
            year=int(entry['year']) if entry.get('year') else None,
            journal=entry.get('journal'),
            volume=entry.get('volume'),
            pages=entry.get('pages'),
            publisher=entry.get('publisher'),
            doi=entry.get('doi'),
            url=entry.get('url'),
            abstract=entry.get('abstract'),
        )
    
    @staticmethod
    def _parse_authors(author_str: str) -> List[str]:
        """Parse BibTeX author string."""
        if not author_str:
            return []
        # Split on ' and '
        return [a.strip() for a in author_str.split(' and ')]
    
    def format_apa(self) -> str:
        """Format citation in APA style."""
        authors = ', '.join(self.authors[:3])
        if len(self.authors) > 3:
            authors += ' et al.'
        
        year = f"({self.year})" if self.year else "(n.d.)"
        
        if self.type == 'article' and self.journal:
            return f"{authors} {year}. {self.title}. *{self.journal}*, {self.volume or ''}, {self.pages or ''}."
        elif self.type == 'book' and self.publisher:
            return f"{authors} {year}. *{self.title}*. {self.publisher}."
        else:
            return f"{authors} {year}. {self.title}."
    
    def format_chicago(self) -> str:
        """Format citation in Chicago style."""
        authors = ', '.join(self.authors)
        year = str(self.year) if self.year else "n.d."
        
        return f'{authors}. "{self.title}." {year}.'


@dataclass
class GlossaryTerm:
    """A glossary term definition."""
    term: str
    definition: str
    abbreviation: Optional[str] = None
    see_also: List[str] = field(default_factory=list)
    source_file: Optional[str] = None


# ============================================================================
# Reference Manager
# ============================================================================

class ReferenceManager:
    """
    Manages cross-references across a book project.
    
    Collects references from all files and resolves links
    during the build process.
    """
    
    def __init__(self, project_dir: Path):
        """
        Initialize reference manager.
        
        Args:
            project_dir: Project root directory
        """
        self.project_dir = Path(project_dir)
        self.references: Dict[str, Reference] = {}
        self.citations: Dict[str, Citation] = {}
        self.glossary: Dict[str, GlossaryTerm] = {}
        self.unresolved: Set[str] = set()
        
        # Numbering counters per file
        self._counters: Dict[str, Dict[str, int]] = {}
    
    def register(self, ref: Reference):
        """Register a reference target."""
        if ref.id in self.references:
            existing = self.references[ref.id]
            if existing.source_file != ref.source_file:
                logger.warning(
                    f"Duplicate reference '{ref.id}' in {ref.source_file}, "
                    f"previously defined in {existing.source_file}"
                )
        
        self.references[ref.id] = ref
        logger.debug(f"Registered reference: {ref.id} ({ref.type})")
    
    def resolve(self, ref_id: str) -> Optional[Reference]:
        """
        Resolve a reference by ID.
        
        Args:
            ref_id: Reference identifier
            
        Returns:
            Reference if found, None otherwise
        """
        # Check direct match
        if ref_id in self.references:
            return self.references[ref_id]
        
        # Check with common prefixes
        for prefix in ['fig:', 'table:', 'eq:', 'sec:', 'code:']:
            full_id = prefix + ref_id
            if full_id in self.references:
                return self.references[full_id]
        
        # Check case-insensitive
        ref_lower = ref_id.lower()
        for key, ref in self.references.items():
            if key.lower() == ref_lower:
                return ref
        
        # Mark as unresolved
        self.unresolved.add(ref_id)
        logger.warning(f"Unresolved reference: {ref_id}")
        return None
    
    def get_citation(self, key: str) -> Optional[Citation]:
        """Get a citation by key."""
        return self.citations.get(key)
    
    def get_term(self, term: str) -> Optional[GlossaryTerm]:
        """Get a glossary term."""
        return self.glossary.get(term.lower())
    
    def add_citation(self, citation: Citation):
        """Add a citation to the bibliography."""
        self.citations[citation.key] = citation
    
    def add_term(self, term: GlossaryTerm):
        """Add a glossary term."""
        self.glossary[term.term.lower()] = term
    
    def load_bibliography(self, bib_file: Path):
        """
        Load bibliography from BibTeX or YAML file.
        
        Args:
            bib_file: Path to bibliography file
        """
        bib_file = Path(bib_file)
        
        if bib_file.suffix == '.bib':
            self._load_bibtex(bib_file)
        elif bib_file.suffix in ('.yaml', '.yml'):
            self._load_yaml_bib(bib_file)
        elif bib_file.suffix == '.json':
            self._load_json_bib(bib_file)
        else:
            logger.warning(f"Unsupported bibliography format: {bib_file}")
    
    def _load_bibtex(self, bib_file: Path):
        """Load BibTeX bibliography."""
        try:
            import bibtexparser
            
            with open(bib_file, 'r') as f:
                bib_db = bibtexparser.load(f)
            
            for entry in bib_db.entries:
                citation = Citation.from_bibtex(entry)
                self.add_citation(citation)
                
        except ImportError:
            # Fallback: simple BibTeX parsing
            self._parse_bibtex_simple(bib_file)
    
    def _parse_bibtex_simple(self, bib_file: Path):
        """Simple BibTeX parser without bibtexparser."""
        content = bib_file.read_text()
        
        # Match entries
        entry_pattern = re.compile(
            r'@(\w+)\s*\{\s*([^,]+)\s*,([^@]+)\}',
            re.DOTALL
        )
        
        for match in entry_pattern.finditer(content):
            entry_type = match.group(1)
            entry_key = match.group(2).strip()
            entry_body = match.group(3)
            
            # Parse fields
            fields = {}
            field_pattern = re.compile(r'(\w+)\s*=\s*[{\"]([^}\"]+)[}\"]')
            
            for field_match in field_pattern.finditer(entry_body):
                fields[field_match.group(1).lower()] = field_match.group(2)
            
            citation = Citation(
                key=entry_key,
                type=entry_type.lower(),
                title=fields.get('title', 'Untitled'),
                authors=Citation._parse_authors(fields.get('author', '')),
                year=int(fields['year']) if fields.get('year') else None,
                journal=fields.get('journal'),
                doi=fields.get('doi'),
                url=fields.get('url'),
            )
            
            self.add_citation(citation)
    
    def _load_yaml_bib(self, bib_file: Path):
        """Load YAML bibliography."""
        with open(bib_file, 'r') as f:
            data = yaml.safe_load(f)
        
        for key, entry in data.items():
            citation = Citation(
                key=key,
                type=entry.get('type', 'misc'),
                title=entry.get('title', 'Untitled'),
                authors=entry.get('authors', []),
                year=entry.get('year'),
                journal=entry.get('journal'),
                doi=entry.get('doi'),
                url=entry.get('url'),
            )
            self.add_citation(citation)
    
    def _load_json_bib(self, bib_file: Path):
        """Load JSON bibliography (CSL-JSON format)."""
        with open(bib_file, 'r') as f:
            data = json.load(f)
        
        entries = data if isinstance(data, list) else [data]
        
        for entry in entries:
            authors = []
            for author in entry.get('author', []):
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if name:
                    authors.append(name)
            
            year = None
            if 'issued' in entry:
                date_parts = entry['issued'].get('date-parts', [[]])
                if date_parts and date_parts[0]:
                    year = date_parts[0][0]
            
            citation = Citation(
                key=entry.get('id', entry.get('citation-key', '')),
                type=entry.get('type', 'misc'),
                title=entry.get('title', 'Untitled'),
                authors=authors,
                year=year,
                journal=entry.get('container-title'),
                doi=entry.get('DOI'),
                url=entry.get('URL'),
            )
            self.add_citation(citation)
    
    def load_glossary(self, glossary_file: Path):
        """Load glossary from YAML file."""
        with open(glossary_file, 'r') as f:
            data = yaml.safe_load(f)
        
        for term, definition in data.items():
            if isinstance(definition, str):
                self.add_term(GlossaryTerm(term=term, definition=definition))
            elif isinstance(definition, dict):
                self.add_term(GlossaryTerm(
                    term=term,
                    definition=definition.get('definition', ''),
                    abbreviation=definition.get('abbreviation'),
                    see_also=definition.get('see_also', []),
                ))
    
    def extract_from_content(
        self,
        content: str,
        source_file: str,
    ):
        """
        Extract reference targets from content.
        
        Args:
            content: Markdown content
            source_file: Source file path
        """
        # Initialize counters for this file
        if source_file not in self._counters:
            self._counters[source_file] = {
                'figure': 0,
                'table': 0,
                'equation': 0,
                'code': 0,
            }
        
        counters = self._counters[source_file]
        
        # Extract labeled sections
        # (section-label)=
        # ## Section Title
        section_pattern = re.compile(
            r'\(([a-z0-9_-]+)\)=\s*\n+#{1,6}\s+(.+)$',
            re.MULTILINE | re.IGNORECASE
        )
        
        for match in section_pattern.finditer(content):
            label = match.group(1)
            title = match.group(2).strip()
            
            self.register(Reference(
                id=label,
                type=ReferenceType.SECTION,
                title=title,
                source_file=source_file,
                anchor=label,
            ))
        
        # Extract figures
        # ```{figure} path
        # :name: fig-label
        figure_pattern = re.compile(
            r'```\{figure\}\s*(\S+).*?:name:\s*(\S+)',
            re.DOTALL
        )
        
        for match in figure_pattern.finditer(content):
            counters['figure'] += 1
            label = match.group(2)
            
            self.register(Reference(
                id=label,
                type=ReferenceType.FIGURE,
                number=str(counters['figure']),
                source_file=source_file,
                anchor=label,
            ))
        
        # Extract equations
        # $$
        # equation
        # $$ (eq-label)
        equation_pattern = re.compile(
            r'\$\$\s*\n(.+?)\n\s*\$\$\s*\(([a-z0-9_-]+)\)',
            re.DOTALL | re.IGNORECASE
        )
        
        for match in equation_pattern.finditer(content):
            counters['equation'] += 1
            label = match.group(2)
            
            self.register(Reference(
                id=label,
                type=ReferenceType.EQUATION,
                number=str(counters['equation']),
                source_file=source_file,
                anchor=label,
            ))
        
        # Extract code blocks with names
        code_pattern = re.compile(
            r'```\{code-(?:block|cell)\}.*?:name:\s*(\S+)',
            re.DOTALL
        )
        
        for match in code_pattern.finditer(content):
            counters['code'] += 1
            label = match.group(1)
            
            self.register(Reference(
                id=label,
                type=ReferenceType.CODE,
                number=str(counters['code']),
                source_file=source_file,
                anchor=label,
            ))
    
    def build_xref_json(self) -> Dict[str, Any]:
        """
        Build xref.json for cross-project references.
        
        Returns:
            Dict representing myst.xref.json format
        """
        xref = {
            'version': 1,
            'references': [],
        }
        
        for ref_id, ref in self.references.items():
            xref['references'].append({
                'identifier': ref_id,
                'kind': ref.type.value,
                'data': {
                    'title': ref.title,
                    'number': ref.number,
                    'url': ref.url or f"#{ref.anchor}",
                },
            })
        
        return xref
    
    def save_xref_json(self, output_dir: Path):
        """Save xref.json to output directory."""
        xref = self.build_xref_json()
        output_file = output_dir / "myst.xref.json"
        
        with open(output_file, 'w') as f:
            json.dump(xref, f, indent=2)
        
        logger.info(f"Saved xref.json to {output_file}")
    
    def load_remote_xref(self, url: str):
        """
        Load remote xref.json for cross-project references.
        
        Args:
            url: URL to remote myst.xref.json
        """
        try:
            import urllib.request
            
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read())
            
            for ref_data in data.get('references', []):
                ref = Reference(
                    id=ref_data['identifier'],
                    type=ReferenceType(ref_data.get('kind', 'document')),
                    title=ref_data.get('data', {}).get('title'),
                    url=ref_data.get('data', {}).get('url'),
                )
                ref.metadata['remote'] = True
                ref.metadata['source_url'] = url
                
                self.register(ref)
            
            logger.info(f"Loaded {len(data.get('references', []))} references from {url}")
            
        except Exception as e:
            logger.warning(f"Failed to load remote xref: {e}")
    
    def get_statistics(self) -> Dict[str, int]:
        """Get reference statistics."""
        stats = {
            'total_references': len(self.references),
            'citations': len(self.citations),
            'glossary_terms': len(self.glossary),
            'unresolved': len(self.unresolved),
        }
        
        # Count by type
        for ref_type in ReferenceType:
            count = sum(1 for r in self.references.values() if r.type == ref_type)
            stats[f'{ref_type.value}_refs'] = count
        
        return stats


# ============================================================================
# Link Resolver
# ============================================================================

class LinkResolver:
    """
    Resolves and transforms links in content.
    
    Handles:
    - Internal cross-references
    - Citation links
    - Glossary term links
    - External URL validation
    """
    
    # Patterns
    MYST_REF_PATTERN = re.compile(r'\{ref\}`([^`]+)`')
    MYST_NUMREF_PATTERN = re.compile(r'\{numref\}`([^`]+)`')
    MYST_DOC_PATTERN = re.compile(r'\{doc\}`([^`]+)`')
    MYST_CITE_PATTERN = re.compile(r'\{cite(?::t|:p)?\}`([^`]+)`')
    MYST_TERM_PATTERN = re.compile(r'\{term\}`([^`]+)`')
    MD_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    def __init__(self, ref_manager: ReferenceManager):
        """
        Initialize link resolver.
        
        Args:
            ref_manager: Reference manager instance
        """
        self.ref_manager = ref_manager
        self._resolved_count = 0
        self._broken_links: List[Tuple[str, str]] = []
    
    def resolve_content(
        self,
        content: str,
        source_file: str,
        output_format: str = "html",
    ) -> str:
        """
        Resolve all links in content.
        
        Args:
            content: Markdown content
            source_file: Source file path
            output_format: Target output format
            
        Returns:
            Content with resolved links
        """
        # Resolve MyST roles
        content = self._resolve_ref(content, source_file, output_format)
        content = self._resolve_numref(content, source_file, output_format)
        content = self._resolve_doc(content, source_file, output_format)
        content = self._resolve_cite(content, output_format)
        content = self._resolve_term(content, output_format)
        
        # Resolve markdown links
        content = self._resolve_md_links(content, source_file, output_format)
        
        return content
    
    def _resolve_ref(self, content: str, source_file: str, fmt: str) -> str:
        """Resolve {ref} roles."""
        def replace(match):
            ref_text = match.group(1)
            
            # Check for custom text: {ref}`custom text <target>`
            custom_match = re.match(r'([^<]+)<([^>]+)>', ref_text)
            if custom_match:
                display_text = custom_match.group(1).strip()
                target = custom_match.group(2).strip()
            else:
                target = ref_text
                display_text = None
            
            ref = self.ref_manager.resolve(target)
            
            if ref:
                self._resolved_count += 1
                text = display_text or ref.title or target
                url = ref.url or f"#{ref.anchor}"
                
                if fmt == "html":
                    return f'<a href="{url}">{text}</a>'
                else:
                    return f'[{text}]({url})'
            else:
                self._broken_links.append((source_file, target))
                return f'[{display_text or target}](#{target})'
        
        return self.MYST_REF_PATTERN.sub(replace, content)
    
    def _resolve_numref(self, content: str, source_file: str, fmt: str) -> str:
        """Resolve {numref} roles (numbered references)."""
        def replace(match):
            ref_text = match.group(1)
            
            # Check for format string: {numref}`Figure %s <target>`
            format_match = re.match(r'([^<]+)<([^>]+)>', ref_text)
            if format_match:
                format_str = format_match.group(1).strip()
                target = format_match.group(2).strip()
            else:
                target = ref_text
                format_str = "%s"
            
            ref = self.ref_manager.resolve(target)
            
            if ref and ref.number:
                self._resolved_count += 1
                text = format_str.replace('%s', ref.number)
                url = ref.url or f"#{ref.anchor}"
                
                if fmt == "html":
                    return f'<a href="{url}" class="numref">{text}</a>'
                else:
                    return f'[{text}]({url})'
            else:
                self._broken_links.append((source_file, target))
                return f'[{target}](#{target})'
        
        return self.MYST_NUMREF_PATTERN.sub(replace, content)
    
    def _resolve_doc(self, content: str, source_file: str, fmt: str) -> str:
        """Resolve {doc} roles (document links)."""
        def replace(match):
            doc_path = match.group(1)
            
            # Convert to URL
            if doc_path.endswith('.md'):
                url = doc_path.replace('.md', '.html')
            elif doc_path.endswith('.ipynb'):
                url = doc_path.replace('.ipynb', '.html')
            else:
                url = doc_path + '.html'
            
            # Get title from parsed files
            ref = self.ref_manager.resolve(doc_path)
            title = ref.title if ref else Path(doc_path).stem
            
            if fmt == "html":
                return f'<a href="{url}">{title}</a>'
            else:
                return f'[{title}]({url})'
        
        return self.MYST_DOC_PATTERN.sub(replace, content)
    
    def _resolve_cite(self, content: str, fmt: str) -> str:
        """Resolve {cite} roles."""
        def replace(match):
            cite_key = match.group(1).strip()
            
            # Handle multiple citations: {cite}`key1,key2`
            keys = [k.strip() for k in cite_key.split(',')]
            
            citations = []
            for key in keys:
                citation = self.ref_manager.get_citation(key)
                if citation:
                    self._resolved_count += 1
                    
                    if fmt == "html":
                        authors = citation.authors[0].split()[-1] if citation.authors else 'Unknown'
                        if len(citation.authors) > 1:
                            authors += ' et al.'
                        year = citation.year or 'n.d.'
                        citations.append(
                            f'<a href="#bib-{key}" class="citation">({authors}, {year})</a>'
                        )
                    else:
                        citations.append(f'[@{key}]')
                else:
                    citations.append(f'[{key}]')
                    self._broken_links.append(('bibliography', key))
            
            return '; '.join(citations)
        
        return self.MYST_CITE_PATTERN.sub(replace, content)
    
    def _resolve_term(self, content: str, fmt: str) -> str:
        """Resolve {term} roles (glossary terms)."""
        def replace(match):
            term_text = match.group(1)
            
            # Check for display text: {term}`display <term>`
            custom_match = re.match(r'([^<]+)<([^>]+)>', term_text)
            if custom_match:
                display = custom_match.group(1).strip()
                term = custom_match.group(2).strip()
            else:
                term = term_text
                display = term
            
            term_obj = self.ref_manager.get_term(term)
            
            if term_obj:
                self._resolved_count += 1
                
                if fmt == "html":
                    return (
                        f'<dfn title="{term_obj.definition}">'
                        f'<a href="#glossary-{term.lower()}">{display}</a></dfn>'
                    )
                else:
                    return f'[{display}](#glossary-{term.lower()})'
            else:
                return f'*{display}*'
        
        return self.MYST_TERM_PATTERN.sub(replace, content)
    
    def _resolve_md_links(self, content: str, source_file: str, fmt: str) -> str:
        """Resolve standard Markdown links."""
        def replace(match):
            text = match.group(1)
            url = match.group(2)
            
            # External URLs - keep as is
            if url.startswith(('http://', 'https://', 'mailto:', '//')):
                return match.group(0)
            
            # Anchor links
            if url.startswith('#'):
                return match.group(0)
            
            # Internal file links
            if url.endswith('.md'):
                new_url = url.replace('.md', '.html')
                return f'[{text}]({new_url})'
            elif url.endswith('.ipynb'):
                new_url = url.replace('.ipynb', '.html')
                return f'[{text}]({new_url})'
            
            return match.group(0)
        
        return self.MD_LINK_PATTERN.sub(replace, content)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get resolution statistics."""
        return {
            'resolved_count': self._resolved_count,
            'broken_links': len(self._broken_links),
            'broken_link_details': self._broken_links,
        }


# ============================================================================
# Bibliography Generator
# ============================================================================

class BibliographyGenerator:
    """
    Generates formatted bibliography from citations.
    """
    
    STYLES = ['apa', 'chicago', 'mla', 'ieee', 'harvard']
    
    def __init__(
        self,
        ref_manager: ReferenceManager,
        style: str = 'apa',
    ):
        """
        Initialize bibliography generator.
        
        Args:
            ref_manager: Reference manager with citations
            style: Citation style
        """
        self.ref_manager = ref_manager
        self.style = style
    
    def generate_html(self, cited_only: bool = True) -> str:
        """
        Generate HTML bibliography.
        
        Args:
            cited_only: Only include cited references
            
        Returns:
            HTML string
        """
        citations = list(self.ref_manager.citations.values())
        
        if not citations:
            return ''
        
        # Sort by author, year
        citations.sort(key=lambda c: (c.authors[0] if c.authors else '', c.year or 0))
        
        html = '<section class="bibliography">\n'
        html += '<h2>References</h2>\n'
        html += '<ol class="bibliography-list">\n'
        
        for citation in citations:
            html += f'<li id="bib-{citation.key}">\n'
            html += f'  {self._format_citation(citation)}\n'
            
            if citation.doi:
                html += f'  <a href="https://doi.org/{citation.doi}" class="doi">[DOI]</a>\n'
            if citation.url:
                html += f'  <a href="{citation.url}" class="url">[URL]</a>\n'
            
            html += '</li>\n'
        
        html += '</ol>\n'
        html += '</section>\n'
        
        return html
    
    def generate_markdown(self) -> str:
        """Generate Markdown bibliography."""
        citations = list(self.ref_manager.citations.values())
        citations.sort(key=lambda c: (c.authors[0] if c.authors else '', c.year or 0))
        
        md = '## References\n\n'
        
        for i, citation in enumerate(citations, 1):
            md += f'{i}. {self._format_citation(citation)}'
            
            if citation.doi:
                md += f' [DOI](https://doi.org/{citation.doi})'
            if citation.url:
                md += f' [URL]({citation.url})'
            
            md += '\n'
        
        return md
    
    def _format_citation(self, citation: Citation) -> str:
        """Format citation in selected style."""
        if self.style == 'apa':
            return citation.format_apa()
        elif self.style == 'chicago':
            return citation.format_chicago()
        else:
            return citation.format_apa()


# ============================================================================
# Glossary Generator
# ============================================================================

class GlossaryGenerator:
    """
    Generates formatted glossary from terms.
    """
    
    def __init__(self, ref_manager: ReferenceManager):
        """
        Initialize glossary generator.
        
        Args:
            ref_manager: Reference manager with glossary
        """
        self.ref_manager = ref_manager
    
    def generate_html(self) -> str:
        """Generate HTML glossary."""
        terms = list(self.ref_manager.glossary.values())
        
        if not terms:
            return ''
        
        # Sort alphabetically
        terms.sort(key=lambda t: t.term.lower())
        
        html = '<section class="glossary">\n'
        html += '<h2>Glossary</h2>\n'
        html += '<dl class="glossary-list">\n'
        
        for term in terms:
            html += f'<dt id="glossary-{term.term.lower()}">{term.term}'
            if term.abbreviation:
                html += f' ({term.abbreviation})'
            html += '</dt>\n'
            html += f'<dd>{term.definition}'
            
            if term.see_also:
                html += '<br><em>See also:</em> '
                links = [f'<a href="#glossary-{t.lower()}">{t}</a>' for t in term.see_also]
                html += ', '.join(links)
            
            html += '</dd>\n'
        
        html += '</dl>\n'
        html += '</section>\n'
        
        return html
    
    def generate_markdown(self) -> str:
        """Generate Markdown glossary."""
        terms = list(self.ref_manager.glossary.values())
        terms.sort(key=lambda t: t.term.lower())
        
        md = '## Glossary\n\n'
        
        for term in terms:
            md += f'**{term.term}**'
            if term.abbreviation:
                md += f' ({term.abbreviation})'
            md += f'\n: {term.definition}\n'
            
            if term.see_also:
                md += f': *See also:* {", ".join(term.see_also)}\n'
            
            md += '\n'
        
        return md


# ============================================================================
# Utility Functions
# ============================================================================

def generate_anchor(text: str) -> str:
    """
    Generate URL-safe anchor from text.
    
    Args:
        text: Section title or label
        
    Returns:
        URL-safe anchor string
    """
    # Remove special characters
    anchor = re.sub(r'[^\w\s-]', '', text.lower())
    # Replace spaces with hyphens
    anchor = re.sub(r'[\s_]+', '-', anchor)
    # Remove leading/trailing hyphens
    anchor = anchor.strip('-')
    
    return anchor


def extract_frontmatter_refs(content: str) -> Dict[str, str]:
    """
    Extract reference aliases from frontmatter.
    
    Args:
        content: Markdown content with YAML frontmatter
        
    Returns:
        Dict of aliases to targets
    """
    refs = {}
    
    # Extract frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1))
            
            # Check for substitutions
            if 'substitutions' in frontmatter:
                for key, value in frontmatter['substitutions'].items():
                    refs[key] = value
            
            # Check for labels
            if 'label' in frontmatter:
                refs['_self'] = frontmatter['label']
                
        except yaml.YAMLError:
            pass
    
    return refs
