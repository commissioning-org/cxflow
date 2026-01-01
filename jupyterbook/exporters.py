"""
CXFlow Jupyter Book Advanced Exporters

Export documentation to various formats including EPUB, reveal.js slides,
JATS XML (for academic publishing), and enhanced PDF generation.
"""

from __future__ import annotations

import os
import re
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging
import zipfile
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# Export Configuration
# ============================================================================

class PDFEngine(str, Enum):
    """PDF generation engines."""
    TYPST = "typst"
    PANDOC = "pandoc"
    WEASYPRINT = "weasyprint"
    PRINCE = "prince"


@dataclass
class PDFConfig:
    """PDF export configuration."""
    engine: PDFEngine = PDFEngine.TYPST
    paper_size: str = "a4"
    font_size: str = "11pt"
    margin: str = "1in"
    toc: bool = True
    toc_depth: int = 3
    numbered_sections: bool = True
    cover_page: bool = True
    header: Optional[str] = None
    footer: Optional[str] = None
    watermark: Optional[str] = None
    template: Optional[str] = None


@dataclass
class EPUBConfig:
    """EPUB export configuration."""
    version: str = "3.0"
    cover_image: Optional[str] = None
    language: str = "en"
    publisher: Optional[str] = None
    rights: Optional[str] = None
    css: Optional[str] = None
    fonts: List[str] = field(default_factory=list)
    include_toc: bool = True


@dataclass
class SlidesConfig:
    """Reveal.js slides configuration."""
    theme: str = "black"
    transition: str = "slide"
    slide_number: bool = True
    progress: bool = True
    hash: bool = True
    center: bool = True
    controls: bool = True
    width: int = 1920
    height: int = 1080
    auto_animate: bool = True
    plugins: List[str] = field(default_factory=lambda: ["highlight", "notes", "math"])


@dataclass
class JATSConfig:
    """JATS XML export configuration."""
    dtd_version: str = "1.3"
    article_type: str = "research-article"
    journal_title: Optional[str] = None
    publisher_name: Optional[str] = None
    doi: Optional[str] = None
    issn: Optional[str] = None


# ============================================================================
# Enhanced PDF Exporter
# ============================================================================

class EnhancedPDFExporter:
    """
    Advanced PDF export with multiple engine support.
    """
    
    def __init__(self, config: Optional[PDFConfig] = None):
        self.config = config or PDFConfig()
    
    def export(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Export content to PDF.
        
        Args:
            content: Parsed content dictionary
            output_path: Output file path
            metadata: Document metadata
            
        Returns:
            Path to generated PDF
        """
        output_path = Path(output_path)
        metadata = metadata or {}
        
        if self.config.engine == PDFEngine.TYPST:
            return self._export_typst(content, output_path, metadata)
        elif self.config.engine == PDFEngine.PANDOC:
            return self._export_pandoc(content, output_path, metadata)
        elif self.config.engine == PDFEngine.WEASYPRINT:
            return self._export_weasyprint(content, output_path, metadata)
        else:
            raise ValueError(f"Unsupported PDF engine: {self.config.engine}")
    
    def _export_typst(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Dict[str, Any],
    ) -> Path:
        """Export using Typst."""
        # Generate Typst document
        typst_content = self._generate_typst(content, metadata)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.typ',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(typst_content)
            typ_path = f.name
        
        try:
            # Compile with Typst
            result = subprocess.run(
                ['typst', 'compile', typ_path, str(output_path)],
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Typst compilation failed: {result.stderr}")
            
            return output_path
            
        finally:
            os.unlink(typ_path)
    
    def _generate_typst(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """Generate Typst document source."""
        title = metadata.get('title', 'Document')
        authors = metadata.get('authors', [])
        date = metadata.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Document setup
        typst = f"""
#set document(title: "{title}", author: ({', '.join(f'"{a}"' for a in authors)}))
#set page(
    paper: "{self.config.paper_size}",
    margin: {self.config.margin},
"""
        
        if self.config.header:
            typst += f'    header: [{self.config.header}],\n'
        
        if self.config.footer:
            typst += f'    footer: [#align(center)[#counter(page).display()]],\n'
        
        typst += ")\n\n"
        
        # Font settings
        typst += f"""
#set text(
    font: "Linux Libertine",
    size: {self.config.font_size},
)

#set heading(numbering: {"\"1.1\"" if self.config.numbered_sections else "none"})

#show heading.where(level: 1): it => {{
    pagebreak()
    text(size: 24pt, weight: "bold")[#it]
}}

#show heading.where(level: 2): set text(size: 18pt, weight: "bold")
#show heading.where(level: 3): set text(size: 14pt, weight: "bold")

// Code blocks
#show raw.where(block: true): it => {{
    rect(
        fill: luma(245),
        radius: 4pt,
        width: 100%,
        inset: 12pt,
    )[#it]
}}

// Admonitions
#let note(body) = {{
    rect(
        fill: rgb("#e7f2fa"),
        stroke: (left: 4pt + rgb("#6ab0de")),
        width: 100%,
        inset: 12pt,
    )[#strong[Note:] #body]
}}

#let warning(body) = {{
    rect(
        fill: rgb("#fff3cd"),
        stroke: (left: 4pt + rgb("#ffecb5")),
        width: 100%,
        inset: 12pt,
    )[#strong[Warning:] #body]
}}

"""
        
        # Cover page
        if self.config.cover_page:
            typst += f"""
#align(center + horizon)[
    #text(size: 36pt, weight: "bold")[{title}]
    
    #v(2em)
    
    #text(size: 16pt)[{', '.join(authors)}]
    
    #v(1em)
    
    #text(size: 14pt, fill: luma(100))[{date}]
]

#pagebreak()
"""
        
        # Table of contents
        if self.config.toc:
            typst += f"""
#outline(
    title: "Table of Contents",
    depth: {self.config.toc_depth},
    indent: true,
)

#pagebreak()
"""
        
        # Convert content
        if 'markdown' in content:
            typst += self._markdown_to_typst(content['markdown'])
        elif 'chapters' in content:
            for chapter in content['chapters']:
                typst += f"\n= {chapter.get('title', 'Chapter')}\n\n"
                typst += self._markdown_to_typst(chapter.get('content', ''))
        
        return typst
    
    def _markdown_to_typst(self, markdown: str) -> str:
        """Convert Markdown to Typst format."""
        typst = markdown
        
        # Headings
        typst = re.sub(r'^######\s+(.+)$', r'====== \1', typst, flags=re.MULTILINE)
        typst = re.sub(r'^#####\s+(.+)$', r'===== \1', typst, flags=re.MULTILINE)
        typst = re.sub(r'^####\s+(.+)$', r'==== \1', typst, flags=re.MULTILINE)
        typst = re.sub(r'^###\s+(.+)$', r'=== \1', typst, flags=re.MULTILINE)
        typst = re.sub(r'^##\s+(.+)$', r'== \1', typst, flags=re.MULTILINE)
        typst = re.sub(r'^#\s+(.+)$', r'= \1', typst, flags=re.MULTILINE)
        
        # Bold and italic
        typst = re.sub(r'\*\*(.+?)\*\*', r'*\1*', typst)
        typst = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'_\1_', typst)
        
        # Code
        typst = re.sub(r'`([^`]+)`', r'`\1`', typst)
        
        # Math
        typst = re.sub(r'\$\$(.+?)\$\$', r'$ \1 $', typst, flags=re.DOTALL)
        typst = re.sub(r'\$([^$]+)\$', r'$\1$', typst)
        
        # Links
        typst = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'#link("\2")[\1]', typst)
        
        # Images
        typst = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'#image("\2")', typst)
        
        # Lists
        typst = re.sub(r'^-\s+', r'- ', typst, flags=re.MULTILINE)
        typst = re.sub(r'^\d+\.\s+', r'+ ', typst, flags=re.MULTILINE)
        
        # Blockquotes
        typst = re.sub(r'^>\s+(.+)$', r'#quote[\1]', typst, flags=re.MULTILINE)
        
        return typst
    
    def _export_pandoc(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Dict[str, Any],
    ) -> Path:
        """Export using Pandoc."""
        # Build markdown with YAML frontmatter
        yaml_header = "---\n"
        yaml_header += f"title: \"{metadata.get('title', 'Document')}\"\n"
        
        if metadata.get('authors'):
            yaml_header += "author:\n"
            for author in metadata['authors']:
                yaml_header += f"  - {author}\n"
        
        yaml_header += f"date: \"{metadata.get('date', datetime.now().strftime('%Y-%m-%d'))}\"\n"
        yaml_header += f"documentclass: article\n"
        yaml_header += f"geometry: margin={self.config.margin}\n"
        yaml_header += f"fontsize: {self.config.font_size}\n"
        
        if self.config.toc:
            yaml_header += "toc: true\n"
            yaml_header += f"toc-depth: {self.config.toc_depth}\n"
        
        if self.config.numbered_sections:
            yaml_header += "numbersections: true\n"
        
        yaml_header += "---\n\n"
        
        # Get markdown content
        if 'markdown' in content:
            md_content = yaml_header + content['markdown']
        elif 'chapters' in content:
            md_content = yaml_header
            for chapter in content['chapters']:
                md_content += f"\n# {chapter.get('title', 'Chapter')}\n\n"
                md_content += chapter.get('content', '') + "\n\n"
        else:
            md_content = yaml_header
        
        # Write temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.md',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(md_content)
            md_path = f.name
        
        try:
            cmd = [
                'pandoc',
                md_path,
                '-o', str(output_path),
                '--pdf-engine=xelatex',
                '-V', f'papersize:{self.config.paper_size}',
            ]
            
            if self.config.template:
                cmd.extend(['--template', self.config.template])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"Pandoc failed: {result.stderr}")
            
            return output_path
            
        finally:
            os.unlink(md_path)
    
    def _export_weasyprint(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Dict[str, Any],
    ) -> Path:
        """Export using WeasyPrint."""
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise RuntimeError("WeasyPrint not installed. Run: pip install weasyprint")
        
        # Generate HTML
        html_content = self._generate_html(content, metadata)
        
        # Generate PDF
        html = HTML(string=html_content)
        
        # Custom CSS for print
        css = CSS(string=f"""
            @page {{
                size: {self.config.paper_size};
                margin: {self.config.margin};
            }}
            body {{
                font-family: 'Linux Libertine', Georgia, serif;
                font-size: {self.config.font_size};
                line-height: 1.6;
            }}
            h1 {{ page-break-before: always; }}
            pre {{ white-space: pre-wrap; }}
        """)
        
        html.write_pdf(output_path, stylesheets=[css])
        return output_path
    
    def _generate_html(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """Generate HTML for PDF conversion."""
        title = metadata.get('title', 'Document')
        authors = metadata.get('authors', [])
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
</head>
<body>
    <header>
        <h1>{title}</h1>
        <p class="authors">{', '.join(authors)}</p>
    </header>
    <main>
"""
        
        if 'html' in content:
            html += content['html']
        elif 'markdown' in content:
            # Simple markdown to HTML conversion
            md = content['markdown']
            md = re.sub(r'^# (.+)$', r'<h1>\1</h1>', md, flags=re.MULTILINE)
            md = re.sub(r'^## (.+)$', r'<h2>\1</h2>', md, flags=re.MULTILINE)
            md = re.sub(r'^### (.+)$', r'<h3>\1</h3>', md, flags=re.MULTILINE)
            md = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md)
            md = re.sub(r'\*(.+?)\*', r'<em>\1</em>', md)
            md = re.sub(r'`([^`]+)`', r'<code>\1</code>', md)
            md = re.sub(r'\n\n', r'</p><p>', md)
            html += f"<p>{md}</p>"
        
        html += """
    </main>
</body>
</html>
"""
        return html


# ============================================================================
# EPUB Exporter
# ============================================================================

class EPUBExporter:
    """
    Export to EPUB format.
    """
    
    def __init__(self, config: Optional[EPUBConfig] = None):
        self.config = config or EPUBConfig()
    
    def export(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Export content to EPUB.
        
        Args:
            content: Parsed content (chapters, etc.)
            output_path: Output file path
            metadata: Document metadata
            
        Returns:
            Path to generated EPUB
        """
        output_path = Path(output_path)
        metadata = metadata or {}
        
        # Create temp directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create EPUB structure
            self._create_mimetype(temp_path)
            self._create_container(temp_path)
            self._create_content(temp_path, content, metadata)
            
            # Package as ZIP
            self._package_epub(temp_path, output_path)
        
        return output_path
    
    def _create_mimetype(self, base_path: Path):
        """Create mimetype file (must be first in ZIP)."""
        mimetype_path = base_path / "mimetype"
        mimetype_path.write_text("application/epub+zip")
    
    def _create_container(self, base_path: Path):
        """Create META-INF/container.xml."""
        meta_inf = base_path / "META-INF"
        meta_inf.mkdir(exist_ok=True)
        
        container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>
"""
        (meta_inf / "container.xml").write_text(container)
    
    def _create_content(
        self,
        base_path: Path,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        """Create OEBPS content directory."""
        oebps = base_path / "OEBPS"
        oebps.mkdir(exist_ok=True)
        
        title = metadata.get('title', 'Untitled')
        authors = metadata.get('authors', ['Unknown'])
        book_id = str(uuid.uuid4())
        
        # Get chapters
        chapters = content.get('chapters', [])
        if not chapters and 'markdown' in content:
            chapters = [{'title': title, 'content': content['markdown']}]
        
        # Create chapter files
        manifest_items = []
        spine_items = []
        toc_items = []
        
        for i, chapter in enumerate(chapters):
            chapter_id = f"chapter{i+1}"
            filename = f"{chapter_id}.xhtml"
            
            chapter_html = self._create_chapter_xhtml(
                chapter.get('title', f'Chapter {i+1}'),
                chapter.get('content', ''),
            )
            (oebps / filename).write_text(chapter_html, encoding='utf-8')
            
            manifest_items.append(
                f'<item id="{chapter_id}" href="{filename}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{chapter_id}"/>')
            toc_items.append({
                'id': chapter_id,
                'title': chapter.get('title', f'Chapter {i+1}'),
                'href': filename,
            })
        
        # Create CSS
        css = self._create_stylesheet()
        (oebps / "styles.css").write_text(css)
        manifest_items.append(
            '<item id="css" href="styles.css" media-type="text/css"/>'
        )
        
        # Create navigation document (EPUB 3)
        if self.config.version.startswith('3'):
            nav_html = self._create_nav_xhtml(title, toc_items)
            (oebps / "nav.xhtml").write_text(nav_html, encoding='utf-8')
            manifest_items.append(
                '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            )
        
        # Create OPF file
        opf = self._create_opf(
            title=title,
            authors=authors,
            book_id=book_id,
            manifest_items=manifest_items,
            spine_items=spine_items,
        )
        (oebps / "content.opf").write_text(opf, encoding='utf-8')
        
        # Create NCX for EPUB 2 compatibility
        ncx = self._create_ncx(title, book_id, toc_items)
        (oebps / "toc.ncx").write_text(ncx, encoding='utf-8')
    
    def _create_chapter_xhtml(self, title: str, content: str) -> str:
        """Create XHTML chapter file."""
        # Convert markdown to HTML (simplified)
        html_content = self._markdown_to_xhtml(content)
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.config.language}">
<head>
    <meta charset="UTF-8"/>
    <title>{title}</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
    <section epub:type="chapter">
        <h1>{title}</h1>
        {html_content}
    </section>
</body>
</html>
"""
    
    def _markdown_to_xhtml(self, markdown: str) -> str:
        """Convert Markdown to XHTML."""
        import html
        
        # Escape HTML
        text = html.escape(markdown)
        
        # Convert headings
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Convert formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # Convert lists
        text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.+</li>\n?)+', r'<ul>\n\g<0></ul>\n', text)
        
        # Wrap paragraphs
        paragraphs = text.split('\n\n')
        wrapped = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                wrapped.append(f'<p>{p}</p>')
            else:
                wrapped.append(p)
        
        return '\n'.join(wrapped)
    
    def _create_stylesheet(self) -> str:
        """Create CSS stylesheet."""
        return """
body {
    font-family: Georgia, serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em;
}

h1, h2, h3 {
    font-family: Helvetica, Arial, sans-serif;
    line-height: 1.2;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}

h1 { font-size: 2em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.25em; }

p {
    margin: 1em 0;
    text-align: justify;
}

code {
    font-family: Consolas, Monaco, monospace;
    font-size: 0.9em;
    background: #f5f5f5;
    padding: 0.2em 0.4em;
}

pre {
    background: #f5f5f5;
    padding: 1em;
    overflow-x: auto;
    font-size: 0.85em;
}

blockquote {
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 3px solid #ccc;
    font-style: italic;
}

ul, ol {
    margin: 1em 0;
    padding-left: 2em;
}

li {
    margin: 0.5em 0;
}
"""
    
    def _create_nav_xhtml(self, title: str, toc_items: List[Dict]) -> str:
        """Create EPUB 3 navigation document."""
        toc_list = '\n'.join([
            f'        <li><a href="{item["href"]}">{item["title"]}</a></li>'
            for item in toc_items
        ])
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.config.language}">
<head>
    <meta charset="UTF-8"/>
    <title>{title} - Navigation</title>
</head>
<body>
    <nav epub:type="toc">
        <h1>Table of Contents</h1>
        <ol>
{toc_list}
        </ol>
    </nav>
</body>
</html>
"""
    
    def _create_opf(
        self,
        title: str,
        authors: List[str],
        book_id: str,
        manifest_items: List[str],
        spine_items: List[str],
    ) -> str:
        """Create OPF package file."""
        author_tags = '\n'.join([
            f'    <dc:creator>{author}</dc:creator>'
            for author in authors
        ])
        
        manifest = '\n'.join([f'    {item}' for item in manifest_items])
        manifest += '\n    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        
        spine = '\n'.join([f'    {item}' for item in spine_items])
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="{self.config.version}" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">urn:uuid:{book_id}</dc:identifier>
    <dc:title>{title}</dc:title>
{author_tags}
    <dc:language>{self.config.language}</dc:language>
    <meta property="dcterms:modified">{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
</package>
"""
    
    def _create_ncx(
        self,
        title: str,
        book_id: str,
        toc_items: List[Dict],
    ) -> str:
        """Create NCX navigation file (EPUB 2 compatibility)."""
        nav_points = '\n'.join([
            f"""    <navPoint id="{item['id']}" playOrder="{i+1}">
      <navLabel><text>{item['title']}</text></navLabel>
      <content src="{item['href']}"/>
    </navPoint>"""
            for i, item in enumerate(toc_items)
        ])
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{title}</text>
  </docTitle>
  <navMap>
{nav_points}
  </navMap>
</ncx>
"""
    
    def _package_epub(self, source_dir: Path, output_path: Path):
        """Package directory as EPUB (ZIP with mimetype first)."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add mimetype first (uncompressed)
            mimetype_path = source_dir / "mimetype"
            zf.write(
                mimetype_path,
                "mimetype",
                compress_type=zipfile.ZIP_STORED
            )
            
            # Add all other files
            for path in source_dir.rglob('*'):
                if path.is_file() and path.name != 'mimetype':
                    arcname = path.relative_to(source_dir)
                    zf.write(path, arcname)


# ============================================================================
# Reveal.js Slides Exporter
# ============================================================================

class SlidesExporter:
    """
    Export to reveal.js slides.
    """
    
    def __init__(self, config: Optional[SlidesConfig] = None):
        self.config = config or SlidesConfig()
    
    def export(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Export content to reveal.js HTML.
        
        Args:
            content: Parsed content
            output_path: Output file path
            metadata: Presentation metadata
            
        Returns:
            Path to generated HTML file
        """
        output_path = Path(output_path)
        metadata = metadata or {}
        
        # Generate slides HTML
        slides_html = self._generate_slides(content, metadata)
        output_path.write_text(slides_html, encoding='utf-8')
        
        return output_path
    
    def _generate_slides(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """Generate reveal.js presentation."""
        title = metadata.get('title', 'Presentation')
        author = metadata.get('authors', [''])[0] if metadata.get('authors') else ''
        
        # Parse slides from content
        slides = self._parse_slides(content)
        
        slides_html = '\n'.join([
            self._render_slide(slide) for slide in slides
        ])
        
        # Plugin scripts
        plugins = []
        for plugin in self.config.plugins:
            if plugin == 'highlight':
                plugins.append("RevealHighlight")
            elif plugin == 'notes':
                plugins.append("RevealNotes")
            elif plugin == 'math':
                plugins.append("RevealMath.KaTeX")
            elif plugin == 'markdown':
                plugins.append("RevealMarkdown")
        
        plugin_scripts = ""
        if 'highlight' in self.config.plugins:
            plugin_scripts += '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/plugin/highlight/monokai.css">\n'
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reset.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reveal.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/theme/{self.config.theme}.css">
    {plugin_scripts}
    <style>
        .reveal h1 {{ font-size: 2.5em; }}
        .reveal h2 {{ font-size: 1.75em; }}
        .reveal h3 {{ font-size: 1.25em; }}
        .reveal pre {{ width: 100%; }}
        .reveal .slide-background {{ background-size: cover; }}
        .two-columns {{ display: flex; gap: 2em; }}
        .two-columns > * {{ flex: 1; }}
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
            <!-- Title Slide -->
            <section>
                <h1>{title}</h1>
                {f'<p>{author}</p>' if author else ''}
            </section>
            
            {slides_html}
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/reveal.js@4/dist/reveal.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/reveal.js@4/plugin/notes/notes.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/reveal.js@4/plugin/highlight/highlight.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/reveal.js@4/plugin/math/math.js"></script>
    <script>
        Reveal.initialize({{
            hash: {str(self.config.hash).lower()},
            slideNumber: {str(self.config.slide_number).lower()},
            progress: {str(self.config.progress).lower()},
            center: {str(self.config.center).lower()},
            controls: {str(self.config.controls).lower()},
            transition: '{self.config.transition}',
            width: {self.config.width},
            height: {self.config.height},
            plugins: [{', '.join(plugins)}]
        }});
    </script>
</body>
</html>
"""
    
    def _parse_slides(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse slides from content."""
        slides = []
        
        if 'slides' in content:
            return content['slides']
        
        # Parse from markdown using horizontal rules
        markdown = content.get('markdown', '')
        
        # Split on --- (horizontal rules)
        raw_slides = re.split(r'\n---+\n', markdown)
        
        for raw in raw_slides:
            if not raw.strip():
                continue
            
            slide = {'content': raw.strip()}
            
            # Check for vertical slides (:::)
            if ':::' in raw:
                vertical = re.split(r'\n:::+\n', raw)
                slide['vertical'] = [{'content': v.strip()} for v in vertical if v.strip()]
            
            # Extract title
            title_match = re.search(r'^#{1,3}\s+(.+)$', raw, re.MULTILINE)
            if title_match:
                slide['title'] = title_match.group(1)
            
            # Check for speaker notes
            notes_match = re.search(r'<aside class="notes">(.*?)</aside>', raw, re.DOTALL)
            if notes_match:
                slide['notes'] = notes_match.group(1).strip()
            
            slides.append(slide)
        
        return slides
    
    def _render_slide(self, slide: Dict[str, Any]) -> str:
        """Render a single slide."""
        content = slide.get('content', '')
        
        # Convert markdown to HTML (simplified)
        html = self._markdown_to_html(content)
        
        # Add speaker notes
        notes = ''
        if slide.get('notes'):
            notes = f'<aside class="notes">{slide["notes"]}</aside>'
        
        # Handle vertical slides
        if slide.get('vertical'):
            vertical_html = '\n'.join([
                f'<section>{self._markdown_to_html(v["content"])}</section>'
                for v in slide['vertical']
            ])
            return f'<section>\n{vertical_html}\n</section>'
        
        # Check for data attributes
        attrs = ''
        if 'data-background' in content or slide.get('background'):
            bg = slide.get('background', '')
            attrs = f' data-background="{bg}"'
        
        if self.config.auto_animate and '<!-- animate -->' in content:
            attrs += ' data-auto-animate'
            html = html.replace('<!-- animate -->', '')
        
        return f'<section{attrs}>\n{html}\n{notes}\n</section>'
    
    def _markdown_to_html(self, markdown: str) -> str:
        """Convert Markdown to HTML for slides."""
        html = markdown
        
        # Headings
        html = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Code blocks
        html = re.sub(
            r'```(\w+)?\n(.*?)```',
            r'<pre><code class="language-\1">\2</code></pre>',
            html,
            flags=re.DOTALL
        )
        
        # Inline formatting
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        
        # Lists
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.+</li>\n?)+', r'<ul class="fragment">\n\g<0></ul>', html)
        
        # Images
        html = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', html)
        
        # Fragments (reveal.js)
        html = re.sub(r'\{\.fragment\}', r'class="fragment"', html)
        
        return html


# ============================================================================
# JATS XML Exporter
# ============================================================================

class JATSExporter:
    """
    Export to JATS XML for academic publishing.
    """
    
    def __init__(self, config: Optional[JATSConfig] = None):
        self.config = config or JATSConfig()
    
    def export(
        self,
        content: Dict[str, Any],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Export content to JATS XML.
        
        Args:
            content: Parsed content
            output_path: Output file path
            metadata: Article metadata
            
        Returns:
            Path to generated JATS file
        """
        output_path = Path(output_path)
        metadata = metadata or {}
        
        jats_xml = self._generate_jats(content, metadata)
        output_path.write_text(jats_xml, encoding='utf-8')
        
        return output_path
    
    def _generate_jats(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """Generate JATS XML document."""
        title = metadata.get('title', 'Untitled Article')
        authors = metadata.get('authors', [])
        abstract = metadata.get('abstract', '')
        keywords = metadata.get('keywords', [])
        
        # Build front matter
        front = self._build_front(title, authors, abstract, keywords, metadata)
        
        # Build body
        body = self._build_body(content)
        
        # Build back matter (references)
        back = self._build_back(content.get('citations', []))
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v{self.config.dtd_version}//EN"
                  "https://jats.nlm.nih.gov/publishing/{self.config.dtd_version}/JATS-journalpublishing1.dtd">
<article article-type="{self.config.article_type}" xml:lang="en"
         xmlns:xlink="http://www.w3.org/1999/xlink"
         xmlns:mml="http://www.w3.org/1998/Math/MathML">
{front}
{body}
{back}
</article>
"""
    
    def _build_front(
        self,
        title: str,
        authors: List[str],
        abstract: str,
        keywords: List[str],
        metadata: Dict[str, Any],
    ) -> str:
        """Build JATS front matter."""
        # Journal metadata
        journal_meta = ""
        if self.config.journal_title:
            journal_meta = f"""
  <journal-meta>
    <journal-title-group>
      <journal-title>{self.config.journal_title}</journal-title>
    </journal-title-group>
    {f'<issn>{self.config.issn}</issn>' if self.config.issn else ''}
    {f'<publisher><publisher-name>{self.config.publisher_name}</publisher-name></publisher>' if self.config.publisher_name else ''}
  </journal-meta>"""
        
        # Article metadata
        author_group = ""
        if authors:
            author_elements = []
            for i, author in enumerate(authors):
                # Parse name (assume "First Last" format)
                parts = author.rsplit(' ', 1)
                given = parts[0] if len(parts) > 1 else ''
                surname = parts[-1]
                
                author_elements.append(f"""
      <contrib contrib-type="author">
        <name>
          <surname>{surname}</surname>
          <given-names>{given}</given-names>
        </name>
      </contrib>""")
            
            author_group = f"""
    <contrib-group>
{chr(10).join(author_elements)}
    </contrib-group>"""
        
        # Keywords
        kwd_group = ""
        if keywords:
            kwd_elements = '\n'.join([f'      <kwd>{kw}</kwd>' for kw in keywords])
            kwd_group = f"""
    <kwd-group>
{kwd_elements}
    </kwd-group>"""
        
        # Abstract
        abstract_elem = ""
        if abstract:
            abstract_elem = f"""
    <abstract>
      <p>{abstract}</p>
    </abstract>"""
        
        return f"""<front>
{journal_meta}
  <article-meta>
    {f'<article-id pub-id-type="doi">{self.config.doi}</article-id>' if self.config.doi else ''}
    <title-group>
      <article-title>{title}</article-title>
    </title-group>
{author_group}
    <pub-date pub-type="epub">
      <year>{datetime.now().year}</year>
    </pub-date>
{abstract_elem}
{kwd_group}
  </article-meta>
</front>"""
    
    def _build_body(self, content: Dict[str, Any]) -> str:
        """Build JATS body."""
        body_content = ""
        
        if 'sections' in content:
            for section in content['sections']:
                body_content += self._render_section(section)
        elif 'markdown' in content:
            body_content = self._markdown_to_jats(content['markdown'])
        
        return f"""<body>
{body_content}
</body>"""
    
    def _render_section(self, section: Dict[str, Any]) -> str:
        """Render a section to JATS."""
        title = section.get('title', '')
        content = section.get('content', '')
        sec_id = section.get('id', '')
        
        jats_content = self._markdown_to_jats(content)
        
        return f"""
  <sec id="{sec_id}">
    <title>{title}</title>
    {jats_content}
  </sec>"""
    
    def _markdown_to_jats(self, markdown: str) -> str:
        """Convert Markdown to JATS elements."""
        jats = markdown
        
        # Paragraphs
        paragraphs = jats.split('\n\n')
        jats_parts = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Skip headings (handled separately)
            if para.startswith('#'):
                continue
            
            # Lists
            if para.startswith('- '):
                items = para.split('\n')
                list_items = '\n'.join([
                    f'      <list-item><p>{item[2:]}</p></list-item>'
                    for item in items if item.startswith('- ')
                ])
                jats_parts.append(f'    <list list-type="bullet">\n{list_items}\n    </list>')
                continue
            
            # Regular paragraph
            # Inline formatting
            para = re.sub(r'\*\*(.+?)\*\*', r'<bold>\1</bold>', para)
            para = re.sub(r'\*(.+?)\*', r'<italic>\1</italic>', para)
            para = re.sub(r'`([^`]+)`', r'<monospace>\1</monospace>', para)
            
            # Citations
            para = re.sub(r'\{cite\}`([^`]+)`', r'<xref ref-type="bibr" rid="\1">\1</xref>', para)
            
            # Math
            para = re.sub(r'\$\$(.+?)\$\$', r'<disp-formula><mml:math>\1</mml:math></disp-formula>', para, flags=re.DOTALL)
            para = re.sub(r'\$([^$]+)\$', r'<inline-formula><mml:math>\1</mml:math></inline-formula>', para)
            
            jats_parts.append(f'    <p>{para}</p>')
        
        return '\n'.join(jats_parts)
    
    def _build_back(self, citations: List[Dict[str, Any]]) -> str:
        """Build JATS back matter with references."""
        if not citations:
            return "<back/>"
        
        ref_list = []
        for cite in citations:
            ref_list.append(self._render_citation(cite))
        
        return f"""<back>
  <ref-list>
    <title>References</title>
{''.join(ref_list)}
  </ref-list>
</back>"""
    
    def _render_citation(self, cite: Dict[str, Any]) -> str:
        """Render a citation to JATS ref element."""
        key = cite.get('key', '')
        title = cite.get('title', '')
        authors = cite.get('authors', [])
        year = cite.get('year', '')
        journal = cite.get('journal', '')
        volume = cite.get('volume', '')
        pages = cite.get('pages', '')
        doi = cite.get('doi', '')
        
        author_group = ""
        if authors:
            names = []
            for author in authors:
                parts = author.rsplit(' ', 1)
                given = parts[0] if len(parts) > 1 else ''
                surname = parts[-1]
                names.append(f"""
          <name>
            <surname>{surname}</surname>
            <given-names>{given}</given-names>
          </name>""")
            author_group = f"""
        <person-group person-group-type="author">
{''.join(names)}
        </person-group>"""
        
        return f"""
    <ref id="{key}">
      <element-citation publication-type="journal">
{author_group}
        <article-title>{title}</article-title>
        {f'<source>{journal}</source>' if journal else ''}
        {f'<year>{year}</year>' if year else ''}
        {f'<volume>{volume}</volume>' if volume else ''}
        {f'<fpage>{pages.split("-")[0] if pages else ""}</fpage>' if pages else ''}
        {f'<pub-id pub-id-type="doi">{doi}</pub-id>' if doi else ''}
      </element-citation>
    </ref>"""
