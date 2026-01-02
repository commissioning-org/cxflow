"""
CXFlow Jupyter Book Theme Engine

Advanced theming system with customizable layouts, color schemes,
and component styling for documentation sites.
"""

from __future__ import annotations

import re
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging

import yaml

logger = logging.getLogger(__name__)


# ============================================================================
# Theme Models
# ============================================================================

class ColorScheme(str, Enum):
    """Available color schemes."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    SEPIA = "sepia"
    HIGH_CONTRAST = "high-contrast"


class LayoutType(str, Enum):
    """Available layout types."""
    SIDEBAR = "sidebar"
    FULLWIDTH = "fullwidth"
    CENTERED = "centered"
    SPLIT = "split"


@dataclass
class ColorPalette:
    """Color palette definition."""
    primary: str = "#2563eb"
    secondary: str = "#4f46e5"
    accent: str = "#0891b2"
    background: str = "#ffffff"
    surface: str = "#f8fafc"
    text: str = "#1e293b"
    text_muted: str = "#64748b"
    border: str = "#e2e8f0"
    success: str = "#22c55e"
    warning: str = "#f59e0b"
    error: str = "#ef4444"
    info: str = "#3b82f6"
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "ColorPalette":
        """Create palette from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
    
    def to_css_vars(self) -> str:
        """Convert to CSS custom properties."""
        return "\n".join([
            f"  --color-{key.replace('_', '-')}: {value};"
            for key, value in self.__dict__.items()
        ])


@dataclass
class Typography:
    """Typography configuration."""
    font_family: str = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    font_family_mono: str = "'Fira Code', 'JetBrains Mono', 'SF Mono', monospace"
    font_family_heading: str = "inherit"
    base_size: str = "16px"
    line_height: str = "1.7"
    heading_line_height: str = "1.25"
    scale_ratio: float = 1.25  # Major third
    
    def to_css_vars(self) -> str:
        """Convert to CSS custom properties."""
        return f"""
  --font-family: {self.font_family};
  --font-family-mono: {self.font_family_mono};
  --font-family-heading: {self.font_family_heading};
  --font-size-base: {self.base_size};
  --line-height: {self.line_height};
  --heading-line-height: {self.heading_line_height};
  --scale-ratio: {self.scale_ratio};
"""


@dataclass
class Spacing:
    """Spacing configuration."""
    unit: str = "0.25rem"
    content_max_width: str = "65ch"
    sidebar_width: str = "280px"
    header_height: str = "60px"
    
    def to_css_vars(self) -> str:
        """Convert to CSS custom properties."""
        return f"""
  --spacing-unit: {self.unit};
  --content-max-width: {self.content_max_width};
  --sidebar-width: {self.sidebar_width};
  --header-height: {self.header_height};
"""


@dataclass
class ThemeConfig:
    """Complete theme configuration."""
    name: str = "default"
    layout: LayoutType = LayoutType.SIDEBAR
    color_scheme: ColorScheme = ColorScheme.AUTO
    colors: ColorPalette = field(default_factory=ColorPalette)
    colors_dark: Optional[ColorPalette] = None
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    custom_css: str = ""
    custom_js: str = ""
    logo: Optional[str] = None
    favicon: Optional[str] = None
    social_links: List[Dict[str, str]] = field(default_factory=list)
    footer: Optional[str] = None
    
    @classmethod
    def load(cls, path: Path) -> "ThemeConfig":
        """Load theme from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ThemeConfig":
        """Create theme from dictionary."""
        config = cls(name=data.get('name', 'default'))
        
        if 'layout' in data:
            config.layout = LayoutType(data['layout'])
        if 'color_scheme' in data:
            config.color_scheme = ColorScheme(data['color_scheme'])
        if 'colors' in data:
            config.colors = ColorPalette.from_dict(data['colors'])
        if 'colors_dark' in data:
            config.colors_dark = ColorPalette.from_dict(data['colors_dark'])
        if 'typography' in data:
            config.typography = Typography(**data['typography'])
        if 'spacing' in data:
            config.spacing = Spacing(**data['spacing'])
        
        config.custom_css = data.get('custom_css', '')
        config.custom_js = data.get('custom_js', '')
        config.logo = data.get('logo')
        config.favicon = data.get('favicon')
        config.social_links = data.get('social_links', [])
        config.footer = data.get('footer')
        
        return config


# ============================================================================
# Built-in Themes
# ============================================================================

THEME_BOOK = ThemeConfig(
    name="book",
    layout=LayoutType.SIDEBAR,
    colors=ColorPalette(
        primary="#1565c0",
        secondary="#1976d2",
        accent="#0288d1",
        background="#ffffff",
        surface="#f5f5f5",
        text="#212121",
        text_muted="#757575",
        border="#e0e0e0",
    ),
    colors_dark=ColorPalette(
        primary="#90caf9",
        secondary="#64b5f6",
        accent="#4fc3f7",
        background="#121212",
        surface="#1e1e1e",
        text="#e0e0e0",
        text_muted="#9e9e9e",
        border="#424242",
    ),
)

THEME_ARTICLE = ThemeConfig(
    name="article",
    layout=LayoutType.CENTERED,
    colors=ColorPalette(
        primary="#6366f1",
        secondary="#8b5cf6",
        accent="#ec4899",
        background="#ffffff",
        surface="#f8fafc",
        text="#1e293b",
        text_muted="#64748b",
        border="#e2e8f0",
    ),
)

THEME_SCIENTIFIC = ThemeConfig(
    name="scientific",
    layout=LayoutType.FULLWIDTH,
    typography=Typography(
        font_family="'Computer Modern', 'Latin Modern Roman', Georgia, serif",
        font_family_mono="'Computer Modern Typewriter', monospace",
        base_size="12pt",
        line_height="1.5",
    ),
    colors=ColorPalette(
        primary="#1a365d",
        secondary="#2c5282",
        accent="#2b6cb0",
        background="#fffef5",
        surface="#f7f5e8",
        text="#1a202c",
        text_muted="#4a5568",
        border="#cbd5e0",
    ),
)

THEME_MODERN = ThemeConfig(
    name="modern",
    layout=LayoutType.SIDEBAR,
    colors=ColorPalette(
        primary="#7c3aed",
        secondary="#8b5cf6",
        accent="#06b6d4",
        background="#fafafa",
        surface="#ffffff",
        text="#18181b",
        text_muted="#71717a",
        border="#e4e4e7",
    ),
    colors_dark=ColorPalette(
        primary="#a78bfa",
        secondary="#c4b5fd",
        accent="#22d3ee",
        background="#09090b",
        surface="#18181b",
        text="#fafafa",
        text_muted="#a1a1aa",
        border="#27272a",
    ),
)

THEME_DOCS = ThemeConfig(
    name="docs",
    layout=LayoutType.SIDEBAR,
    colors=ColorPalette(
        primary="#3b82f6",
        secondary="#60a5fa",
        accent="#2dd4bf",
        background="#ffffff",
        surface="#f9fafb",
        text="#111827",
        text_muted="#6b7280",
        border="#e5e7eb",
    ),
)

BUILTIN_THEMES = {
    "book": THEME_BOOK,
    "article": THEME_ARTICLE,
    "scientific": THEME_SCIENTIFIC,
    "modern": THEME_MODERN,
    "docs": THEME_DOCS,
}


# ============================================================================
# Theme Engine
# ============================================================================

class ThemeEngine:
    """
    Theme rendering engine.
    
    Generates CSS, HTML templates, and assets for themes.
    """
    
    def __init__(self, theme: ThemeConfig):
        """
        Initialize theme engine.
        
        Args:
            theme: Theme configuration
        """
        self.theme = theme
        self._templates: Dict[str, str] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load HTML templates."""
        # NOTE: templates use mustache-like sections and partials.
        # Keep the set of templates self-contained so {{> partial}} always resolves.
        self._templates = {
            "base": self._get_base_template(),
            "page": self._get_page_template(),
            "article": self._get_article_template(),
            "nav": self._get_nav_template(),
            "toc": self._get_toc_template(),
            "search": self._get_search_template(),
            "footer": self._get_footer_template(),
            # Partials referenced by page/article/base
            "layout": "{{> page}}",  # default; can be overridden by caller via context/alt render
            "sidebar": self._get_sidebar_template(),
            "header": self._get_header_template(),
            "breadcrumbs": self._get_breadcrumbs_template(),
            "page_navigation": self._get_page_navigation_template(),
            "toc_sidebar": self._get_toc_sidebar_template(),
            "bibliography": self._get_bibliography_template(),
        }
    
    def generate_css(self) -> str:
        """Generate complete CSS for theme."""
        css_parts = []
        
        # CSS Reset
        css_parts.append(self._get_css_reset())
        
        # CSS Variables
        css_parts.append(self._generate_css_vars())
        
        # Base styles
        css_parts.append(self._get_base_css())
        
        # Layout-specific styles
        css_parts.append(self._get_layout_css())
        
        # Component styles
        css_parts.append(self._get_component_css())
        
        # Typography styles
        css_parts.append(self._get_typography_css())
        
        # Syntax highlighting
        css_parts.append(self._get_syntax_css())
        
        # Responsive styles
        css_parts.append(self._get_responsive_css())
        
        # Custom CSS
        if self.theme.custom_css:
            css_parts.append(self.theme.custom_css)
        
        return "\n\n".join(css_parts)
    
    def _generate_css_vars(self) -> str:
        """Generate CSS custom properties."""
        light_vars = self.theme.colors.to_css_vars()
        dark_vars = (self.theme.colors_dark or self.theme.colors).to_css_vars()
        typography_vars = self.theme.typography.to_css_vars()
        spacing_vars = self.theme.spacing.to_css_vars()
        
        css = f"""
:root {{
{light_vars}
{typography_vars}
{spacing_vars}
}}

@media (prefers-color-scheme: dark) {{
  :root {{
{dark_vars}
  }}
}}

[data-theme="dark"] {{
{dark_vars}
}}

[data-theme="light"] {{
{light_vars}
}}
"""
        return css
    
    def _get_css_reset(self) -> str:
        """Get CSS reset."""
        return """
/* CSS Reset */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-size: var(--font-size-base);
  scroll-behavior: smooth;
  -webkit-text-size-adjust: 100%;
}

body {
  min-height: 100vh;
  font-family: var(--font-family);
  line-height: var(--line-height);
  color: var(--color-text);
  background-color: var(--color-background);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

img, picture, video, canvas, svg {
  display: block;
  max-width: 100%;
}

input, button, textarea, select {
  font: inherit;
}

p, h1, h2, h3, h4, h5, h6 {
  overflow-wrap: break-word;
}

a {
  color: var(--color-primary);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}
"""
    
    def _get_base_css(self) -> str:
        """Get base styles."""
        return """
/* Base Styles */
.container {
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 calc(var(--spacing-unit) * 6);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.skip-link {
  position: absolute;
  top: -100%;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: 0.5rem 1rem;
  z-index: 9999;
}

.skip-link:focus {
  top: 0;
}
"""
    
    def _get_layout_css(self) -> str:
        """Get layout-specific styles."""
        if self.theme.layout == LayoutType.SIDEBAR:
            return self._get_sidebar_layout_css()
        elif self.theme.layout == LayoutType.CENTERED:
            return self._get_centered_layout_css()
        elif self.theme.layout == LayoutType.FULLWIDTH:
            return self._get_fullwidth_layout_css()
        else:
            return self._get_sidebar_layout_css()
    
    def _get_sidebar_layout_css(self) -> str:
        """Get sidebar layout styles."""
        return """
/* Sidebar Layout */
.page-wrapper {
  display: grid;
  grid-template-columns: var(--sidebar-width) 1fr;
  grid-template-rows: auto 1fr auto;
  min-height: 100vh;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  padding: calc(var(--spacing-unit) * 6);
}

.sidebar-header {
  margin-bottom: calc(var(--spacing-unit) * 8);
}

.sidebar-logo {
  max-height: 40px;
  width: auto;
}

.sidebar-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-primary);
}

.main-content {
  padding: calc(var(--spacing-unit) * 8);
  max-width: var(--content-max-width);
}

.toc-sidebar {
  position: sticky;
  top: calc(var(--spacing-unit) * 8);
  max-height: calc(100vh - var(--spacing-unit) * 16);
  overflow-y: auto;
}
"""
    
    def _get_centered_layout_css(self) -> str:
        """Get centered layout styles."""
        return """
/* Centered Layout */
.page-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-header {
  position: sticky;
  top: 0;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  z-index: 100;
}

.main-content {
  flex: 1;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: calc(var(--spacing-unit) * 12) calc(var(--spacing-unit) * 6);
}
"""
    
    def _get_fullwidth_layout_css(self) -> str:
        """Get fullwidth layout styles."""
        return """
/* Fullwidth Layout */
.page-wrapper {
  min-height: 100vh;
}

.main-content {
  max-width: 100%;
  padding: calc(var(--spacing-unit) * 8) calc(var(--spacing-unit) * 12);
}

.main-content > article {
  max-width: var(--content-max-width);
  margin: 0 auto;
}
"""
    
    def _get_component_css(self) -> str:
        """Get component styles."""
        return """
/* Navigation */
.nav-list {
  list-style: none;
}

.nav-item {
  margin: calc(var(--spacing-unit) * 1) 0;
}

.nav-link {
  display: block;
  padding: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 3);
  color: var(--color-text);
  border-radius: calc(var(--spacing-unit) * 1);
  transition: background-color 0.15s, color 0.15s;
}

.nav-link:hover {
  background: var(--color-border);
  text-decoration: none;
}

.nav-link.active {
  background: var(--color-primary);
  color: white;
}

.nav-children {
  padding-left: calc(var(--spacing-unit) * 4);
}

/* Admonitions */
.admonition {
  padding: calc(var(--spacing-unit) * 4);
  border-radius: calc(var(--spacing-unit) * 2);
  margin: calc(var(--spacing-unit) * 6) 0;
  border-left: 4px solid;
}

.admonition-title {
  font-weight: 600;
  margin-bottom: calc(var(--spacing-unit) * 2);
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-unit) * 2);
}

.admonition.note {
  background: color-mix(in srgb, var(--color-info) 10%, var(--color-background));
  border-color: var(--color-info);
}

.admonition.warning {
  background: color-mix(in srgb, var(--color-warning) 10%, var(--color-background));
  border-color: var(--color-warning);
}

.admonition.tip {
  background: color-mix(in srgb, var(--color-success) 10%, var(--color-background));
  border-color: var(--color-success);
}

.admonition.danger, .admonition.error {
  background: color-mix(in srgb, var(--color-error) 10%, var(--color-background));
  border-color: var(--color-error);
}

/* Code Blocks */
pre {
  background: var(--color-surface);
  padding: calc(var(--spacing-unit) * 4);
  border-radius: calc(var(--spacing-unit) * 2);
  overflow-x: auto;
  border: 1px solid var(--color-border);
}

code {
  font-family: var(--font-family-mono);
  font-size: 0.9em;
}

:not(pre) > code {
  background: var(--color-surface);
  padding: 0.2em 0.4em;
  border-radius: calc(var(--spacing-unit) * 1);
}

/* Code Block Header */
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-border);
  padding: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 4);
  border-radius: calc(var(--spacing-unit) * 2) calc(var(--spacing-unit) * 2) 0 0;
  font-size: 0.85em;
  color: var(--color-text-muted);
}

.code-header + pre {
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  margin-top: 0;
}

.copy-button {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: calc(var(--spacing-unit) * 1);
  color: var(--color-text-muted);
  border-radius: calc(var(--spacing-unit) * 1);
}

.copy-button:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: calc(var(--spacing-unit) * 6) 0;
}

th, td {
  padding: calc(var(--spacing-unit) * 3);
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

th {
  font-weight: 600;
  background: var(--color-surface);
}

tr:hover {
  background: var(--color-surface);
}

/* Figures */
figure {
  margin: calc(var(--spacing-unit) * 8) 0;
  text-align: center;
}

figure img {
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}

figcaption {
  margin-top: calc(var(--spacing-unit) * 3);
  color: var(--color-text-muted);
  font-size: 0.9em;
}

/* Cards */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: calc(var(--spacing-unit) * 3);
  padding: calc(var(--spacing-unit) * 6);
  margin: calc(var(--spacing-unit) * 4) 0;
}

.card-header {
  font-weight: 600;
  margin-bottom: calc(var(--spacing-unit) * 3);
}

/* Grid */
.grid {
  display: grid;
  gap: calc(var(--spacing-unit) * 6);
}

.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }

/* Tabs */
.tab-set {
  margin: calc(var(--spacing-unit) * 6) 0;
}

.tab-list {
  display: flex;
  border-bottom: 2px solid var(--color-border);
  gap: calc(var(--spacing-unit) * 1);
}

.tab-button {
  padding: calc(var(--spacing-unit) * 3) calc(var(--spacing-unit) * 4);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}

.tab-button:hover {
  color: var(--color-text);
}

.tab-button.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-panel {
  display: none;
  padding: calc(var(--spacing-unit) * 4) 0;
}

.tab-panel.active {
  display: block;
}

/* Math */
.math {
  overflow-x: auto;
  padding: calc(var(--spacing-unit) * 4) 0;
}

.math-inline {
  display: inline;
}

/* Footnotes */
.footnotes {
  margin-top: calc(var(--spacing-unit) * 12);
  padding-top: calc(var(--spacing-unit) * 6);
  border-top: 1px solid var(--color-border);
  font-size: 0.9em;
}

.footnote-ref {
  vertical-align: super;
  font-size: 0.75em;
}

/* Search */
.search-container {
  position: relative;
}

.search-input {
  width: 100%;
  padding: calc(var(--spacing-unit) * 3);
  border: 1px solid var(--color-border);
  border-radius: calc(var(--spacing-unit) * 2);
  background: var(--color-background);
  color: var(--color-text);
}

.search-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.search-results {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: calc(var(--spacing-unit) * 2);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 400px;
  overflow-y: auto;
  z-index: 1000;
}

.search-result-item {
  padding: calc(var(--spacing-unit) * 3);
  border-bottom: 1px solid var(--color-border);
}

.search-result-item:hover {
  background: var(--color-surface);
}

/* Theme Toggle */
.theme-toggle {
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: calc(var(--spacing-unit) * 2);
  padding: calc(var(--spacing-unit) * 2);
  cursor: pointer;
  color: var(--color-text);
}

.theme-toggle:hover {
  background: var(--color-surface);
}

/* Breadcrumbs */
.breadcrumbs {
  display: flex;
  gap: calc(var(--spacing-unit) * 2);
  font-size: 0.9em;
  color: var(--color-text-muted);
  margin-bottom: calc(var(--spacing-unit) * 4);
}

.breadcrumb-separator {
  color: var(--color-border);
}

/* Progress Bar */
.reading-progress {
  position: fixed;
  top: 0;
  left: 0;
  width: 0%;
  height: 3px;
  background: var(--color-primary);
  z-index: 9999;
  transition: width 0.1s;
}

/* Back to Top */
.back-to-top {
  position: fixed;
  bottom: calc(var(--spacing-unit) * 8);
  right: calc(var(--spacing-unit) * 8);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  cursor: pointer;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s, visibility 0.3s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.back-to-top.visible {
  opacity: 1;
  visibility: visible;
}
"""
    
    def _get_typography_css(self) -> str:
        """Get typography styles."""
        return """
/* Typography */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-family-heading);
  line-height: var(--heading-line-height);
  font-weight: 600;
  margin-top: calc(var(--spacing-unit) * 8);
  margin-bottom: calc(var(--spacing-unit) * 4);
}

h1 { font-size: calc(var(--font-size-base) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio)); }
h2 { font-size: calc(var(--font-size-base) * var(--scale-ratio) * var(--scale-ratio)); }
h3 { font-size: calc(var(--font-size-base) * var(--scale-ratio)); }
h4 { font-size: var(--font-size-base); }
h5 { font-size: calc(var(--font-size-base) / var(--scale-ratio)); }
h6 { font-size: calc(var(--font-size-base) / var(--scale-ratio) / var(--scale-ratio)); }

h1:first-child,
h2:first-child,
h3:first-child {
  margin-top: 0;
}

/* Anchor links */
.header-anchor {
  margin-left: calc(var(--spacing-unit) * 2);
  color: var(--color-text-muted);
  opacity: 0;
  transition: opacity 0.15s;
}

h1:hover .header-anchor,
h2:hover .header-anchor,
h3:hover .header-anchor,
h4:hover .header-anchor,
h5:hover .header-anchor,
h6:hover .header-anchor {
  opacity: 1;
}

p {
  margin-bottom: calc(var(--spacing-unit) * 4);
}

blockquote {
  margin: calc(var(--spacing-unit) * 6) 0;
  padding: calc(var(--spacing-unit) * 4) calc(var(--spacing-unit) * 6);
  border-left: 4px solid var(--color-primary);
  background: var(--color-surface);
  font-style: italic;
}

ul, ol {
  margin: calc(var(--spacing-unit) * 4) 0;
  padding-left: calc(var(--spacing-unit) * 8);
}

li {
  margin: calc(var(--spacing-unit) * 2) 0;
}

hr {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: calc(var(--spacing-unit) * 8) 0;
}

/* Definition Lists */
dl {
  margin: calc(var(--spacing-unit) * 4) 0;
}

dt {
  font-weight: 600;
  margin-top: calc(var(--spacing-unit) * 4);
}

dd {
  margin-left: calc(var(--spacing-unit) * 6);
  margin-top: calc(var(--spacing-unit) * 1);
}

/* Abbreviations */
abbr[title] {
  text-decoration: underline dotted;
  cursor: help;
}

/* Keyboard */
kbd {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: calc(var(--spacing-unit) * 1);
  padding: 0.1em 0.4em;
  font-family: var(--font-family-mono);
  font-size: 0.85em;
  box-shadow: 0 1px 0 var(--color-border);
}
"""
    
    def _get_syntax_css(self) -> str:
        """Get syntax highlighting styles."""
        return """
/* Syntax Highlighting - One Dark Theme */
.highlight .c { color: #5c6370; font-style: italic; } /* Comment */
.highlight .k { color: #c678dd; } /* Keyword */
.highlight .n { color: #abb2bf; } /* Name */
.highlight .o { color: #56b6c2; } /* Operator */
.highlight .p { color: #abb2bf; } /* Punctuation */
.highlight .s { color: #98c379; } /* String */
.highlight .na { color: #d19a66; } /* Name.Attribute */
.highlight .nb { color: #e5c07b; } /* Name.Builtin */
.highlight .nc { color: #e5c07b; } /* Name.Class */
.highlight .nf { color: #61afef; } /* Name.Function */
.highlight .ni { color: #d19a66; } /* Name.Entity */
.highlight .nn { color: #abb2bf; } /* Name.Namespace */
.highlight .nt { color: #e06c75; } /* Name.Tag */
.highlight .nv { color: #e06c75; } /* Name.Variable */
.highlight .m { color: #d19a66; } /* Number */
.highlight .mi { color: #d19a66; } /* Number.Integer */
.highlight .mf { color: #d19a66; } /* Number.Float */

/* Line Numbers */
.linenos {
  color: var(--color-text-muted);
  background: var(--color-surface);
  padding-right: calc(var(--spacing-unit) * 3);
  border-right: 1px solid var(--color-border);
  margin-right: calc(var(--spacing-unit) * 3);
  user-select: none;
}

/* Line Highlight */
.highlight-line {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  display: block;
  margin: 0 calc(var(--spacing-unit) * -4);
  padding: 0 calc(var(--spacing-unit) * 4);
}
"""
    
    def _get_responsive_css(self) -> str:
        """Get responsive styles."""
        return """
/* Responsive */
@media (max-width: 1024px) {
  .page-wrapper {
    grid-template-columns: 1fr;
  }
  
  .sidebar {
    position: fixed;
    left: -100%;
    width: 280px;
    z-index: 1000;
    transition: left 0.3s;
  }
  
  .sidebar.open {
    left: 0;
  }
  
  .sidebar-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s;
  }
  
  .sidebar-overlay.active {
    opacity: 1;
    visibility: visible;
  }
  
  .mobile-nav-toggle {
    display: block;
    position: fixed;
    top: calc(var(--spacing-unit) * 4);
    left: calc(var(--spacing-unit) * 4);
    z-index: 1001;
    background: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: calc(var(--spacing-unit) * 2);
    padding: calc(var(--spacing-unit) * 2);
    cursor: pointer;
  }
  
  .grid-2, .grid-3, .grid-4 {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 1025px) {
  .mobile-nav-toggle {
    display: none;
  }
  
  .sidebar-overlay {
    display: none;
  }
}

/* Print Styles */
@media print {
  .sidebar,
  .mobile-nav-toggle,
  .theme-toggle,
  .back-to-top,
  .reading-progress {
    display: none !important;
  }
  
  .page-wrapper {
    display: block;
  }
  
  .main-content {
    max-width: 100%;
    padding: 0;
  }
  
  a[href]::after {
    content: " (" attr(href) ")";
  }
  
  pre {
    white-space: pre-wrap;
    word-wrap: break-word;
  }
}
"""
    
    def _get_base_template(self) -> str:
        """Get base HTML template."""
        return """<!DOCTYPE html>
<html lang="{{lang}}" data-theme="{{theme}}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}} - {{site_title}}</title>
    <meta name="description" content="{{description}}">
    <meta name="generator" content="CXFlow Book Builder">
    
    {{#favicon}}
    <link rel="icon" href="{{favicon}}">
    {{/favicon}}
    
    <link rel="stylesheet" href="/static/style.css">
    {{#katex}}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    {{/katex}}
    
    {{head_extra}}
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <div class="reading-progress" role="progressbar" aria-label="Reading progress"></div>
    
    {{> layout}}
    
    <button class="back-to-top" aria-label="Back to top">↑</button>
    
    <script src="/static/book.js"></script>
    {{#katex}}
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
    {{/katex}}
    {{#mermaid}}
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    {{/mermaid}}
    {{scripts_extra}}
</body>
</html>
"""
    
    def _get_page_template(self) -> str:
        """Get page content template."""
        return """
<div class="page-wrapper">
    {{> sidebar}}
    
    <main id="main-content" class="main-content">
        {{> breadcrumbs}}
        
        <article>
            {{content}}
        </article>
        
        {{> page_navigation}}
        {{> footer}}
    </main>
    
    {{> toc_sidebar}}
</div>
"""
    
    def _get_article_template(self) -> str:
        """Get article template (centered layout)."""
        return """
<div class="page-wrapper">
    {{> header}}
    
    <main id="main-content" class="main-content">
        <article class="article">
            <header class="article-header">
                <h1>{{title}}</h1>
                {{#authors}}
                <div class="article-meta">
                    <span class="authors">{{authors}}</span>
                    {{#date}}<time datetime="{{date_iso}}">{{date}}</time>{{/date}}
                </div>
                {{/authors}}
            </header>
            
            {{content}}
            
            {{> bibliography}}
        </article>
    </main>
    
    {{> footer}}
</div>
"""
    
    def _get_nav_template(self) -> str:
        """Get navigation template."""
        return """
<nav class="nav" aria-label="Main navigation">
    <ul class="nav-list">
        {{#nav_items}}
        <li class="nav-item">
            <a href="{{url}}" class="nav-link {{#active}}active{{/active}}">
                {{title}}
            </a>
            {{#children}}
            <ul class="nav-children">
                {{#items}}
                <li class="nav-item">
                    <a href="{{url}}" class="nav-link {{#active}}active{{/active}}">{{title}}</a>
                </li>
                {{/items}}
            </ul>
            {{/children}}
        </li>
        {{/nav_items}}
    </ul>
</nav>
"""
    
    def _get_toc_template(self) -> str:
        """Get table of contents template."""
        return """
<nav class="toc" aria-label="On this page">
    <h3 class="toc-title">On this page</h3>
    <ul class="toc-list">
        {{#toc_items}}
        <li class="toc-item toc-level-{{level}}">
            <a href="#{{anchor}}" class="toc-link">{{title}}</a>
        </li>
        {{/toc_items}}
    </ul>
</nav>
"""
    
    def _get_search_template(self) -> str:
        """Get search template."""
        return """
<div class="search-container">
    <input type="search" 
           class="search-input" 
           placeholder="Search..." 
           aria-label="Search documentation">
    <div class="search-results" role="listbox" hidden></div>
</div>
"""
    
    def _get_footer_template(self) -> str:
        """Get footer template."""
        return """
<footer class="site-footer">
    <div class="footer-content">
        {{#footer_text}}
        <p>{{footer_text}}</p>
        {{/footer_text}}
        
        {{#social_links}}
        <div class="social-links">
            {{#links}}
            <a href="{{url}}" aria-label="{{name}}">{{icon}}</a>
            {{/links}}
        </div>
        {{/social_links}}
        
        <p class="powered-by">
            Built with <a href="https://github.com/commissioning-org/cxflow">CXFlow Book Builder</a>
        </p>
    </div>
</footer>
"""
    
    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Render a template with context.
        
        Args:
            template_name: Template name
            context: Template context
            
        Returns:
            Rendered HTML
        """
        template = self._templates.get(template_name, "")
        return self._render_mustache(template, [context])

    # ---------------------------------------------------------------------
    # Mustache-like rendering (minimal but functional)
    # ---------------------------------------------------------------------

    _TAG_RE = re.compile(r"{{\s*(.+?)\s*}}", re.DOTALL)

    def _render_mustache(self, template: str, ctx_stack: List[Dict[str, Any]]) -> str:
        """Render a template supporting: variables, sections, inverted sections, and partials."""

        tokens: List[tuple[str, str]] = []
        last = 0
        for m in self._TAG_RE.finditer(template):
            if m.start() > last:
                tokens.append(("text", template[last:m.start()]))
            tokens.append(("tag", m.group(1).strip()))
            last = m.end()
        if last < len(template):
            tokens.append(("text", template[last:]))

        rendered, _ = self._render_tokens(tokens, 0, ctx_stack)
        return rendered

    def _render_tokens(
        self,
        tokens: List[tuple[str, str]],
        start_idx: int,
        ctx_stack: List[Dict[str, Any]],
        stop_on_section_end: str | None = None,
    ) -> tuple[str, int]:
        out: List[str] = []
        i = start_idx

        while i < len(tokens):
            kind, val = tokens[i]
            if kind == "text":
                out.append(val)
                i += 1
                continue

            tag = val

            # Section end
            if tag.startswith("/"):
                name = tag[1:].strip()
                if stop_on_section_end and name == stop_on_section_end:
                    return "".join(out), i + 1
                i += 1
                continue

            # Partials
            if tag.startswith(">"):
                partial_name = tag[1:].strip()
                partial = self._templates.get(partial_name, "")
                out.append(self._render_mustache(partial, ctx_stack))
                i += 1
                continue

            # Unescaped variables: {{& var}} and {{{var}}}
            if tag.startswith("&"):
                name = tag[1:].strip()
                out.append(self._stringify(self._lookup(name, ctx_stack)))
                i += 1
                continue
            if tag.startswith("{") and tag.endswith("}"):
                name = tag.strip("{} ")
                out.append(self._stringify(self._lookup(name, ctx_stack)))
                i += 1
                continue

            # Sections / inverted sections
            if tag.startswith("#") or tag.startswith("^"):
                inverted = tag.startswith("^")
                name = tag[1:].strip()
                inner, next_i = self._collect_section(tokens, i + 1, name)
                value = self._lookup(name, ctx_stack)

                truthy = bool(value)
                if inverted:
                    if not truthy:
                        rendered, _ = self._render_tokens(inner, 0, ctx_stack)
                        out.append(rendered)
                else:
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                sub_stack = [item] + ctx_stack
                            else:
                                sub_stack = [{".": item}] + ctx_stack
                            rendered, _ = self._render_tokens(inner, 0, sub_stack)
                            out.append(rendered)
                    elif truthy:
                        rendered, _ = self._render_tokens(inner, 0, ctx_stack)
                        out.append(rendered)

                i = next_i
                continue

            # Variable
            out.append(self._stringify(self._lookup(tag, ctx_stack)))
            i += 1

        return "".join(out), i

    def _collect_section(
        self,
        tokens: List[tuple[str, str]],
        start_idx: int,
        name: str,
    ) -> tuple[List[tuple[str, str]], int]:
        """Collect tokens until the matching {{/name}} (supports nesting)."""
        inner: List[tuple[str, str]] = []
        depth = 1
        i = start_idx
        while i < len(tokens):
            kind, val = tokens[i]
            if kind == "tag":
                t = val.strip()
                if t.startswith("#") or t.startswith("^"):
                    if t[1:].strip() == name:
                        depth += 1
                elif t.startswith("/"):
                    if t[1:].strip() == name:
                        depth -= 1
                        if depth == 0:
                            return inner, i + 1
            inner.append(tokens[i])
            i += 1
        return inner, i

    def _lookup(self, name: str, ctx_stack: List[Dict[str, Any]]) -> Any:
        """Look up a variable in the context stack (supports dotted names and '.' value)."""
        if name == ".":
            for ctx in ctx_stack:
                if "." in ctx:
                    return ctx["."]
            return None

        parts = name.split(".")
        for ctx in ctx_stack:
            cur: Any = ctx
            found = True
            for p in parts:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    found = False
                    break
            if found:
                return cur
        return None

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    # ---------------------------------------------------------------------
    # Partial templates (previously missing)
    # ---------------------------------------------------------------------

    def _get_sidebar_template(self) -> str:
        return """
<aside class=\"sidebar\" aria-label=\"Sidebar\">
  <div class=\"sidebar-header\">
    <a class=\"site-title\" href=\"/index.html\">{{site_title}}</a>
    <button class=\"theme-toggle\" type=\"button\" aria-label=\"Toggle theme\">🌓</button>
  </div>
  {{> search}}
  {{> nav}}
</aside>
"""

    def _get_header_template(self) -> str:
        return """
<header class=\"site-header\">
  <div class=\"header-inner\">
    <a class=\"site-title\" href=\"/index.html\">{{site_title}}</a>
    {{> search}}
    <button class=\"theme-toggle\" type=\"button\" aria-label=\"Toggle theme\">🌓</button>
  </div>
</header>
"""

    def _get_breadcrumbs_template(self) -> str:
        return """
{{#breadcrumbs}}
<nav class=\"breadcrumbs\" aria-label=\"Breadcrumb\">
  <ol>
    {{#items}}
    <li><a href=\"{{url}}\">{{title}}</a></li>
    {{/items}}
  </ol>
</nav>
{{/breadcrumbs}}
"""

    def _get_page_navigation_template(self) -> str:
        return """
<nav class=\"page-nav\" aria-label=\"Page navigation\">
  {{#prev}}<a class=\"page-nav-prev\" href=\"{{url}}\">← {{title}}</a>{{/prev}}
  {{#next}}<a class=\"page-nav-next\" href=\"{{url}}\">{{title}} →</a>{{/next}}
</nav>
"""

    def _get_toc_sidebar_template(self) -> str:
        return """
<aside class=\"toc-sidebar\" aria-label=\"On this page\">
  {{> toc}}
</aside>
"""

    def _get_bibliography_template(self) -> str:
        return """
{{#bibliography_html}}
<section class=\"bibliography\">
  <h2>References</h2>
  {{{bibliography_html}}}
</section>
{{/bibliography_html}}
"""
    
    def write_assets(self, output_dir: Path):
        """
        Write theme assets to output directory.
        
        Args:
            output_dir: Output directory
        """
        static_dir = output_dir / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        
        # Write CSS
        css_path = static_dir / "style.css"
        css_path.write_text(self.generate_css())
        
        # Write JS
        js_path = static_dir / "book.js"
        js_path.write_text(self._generate_js())
        
        logger.info(f"Wrote theme assets to {static_dir}")
    
    def _generate_js(self) -> str:
        """Generate JavaScript for theme."""
        return """
// CXFlow Book Builder JavaScript

document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    initMobileNav();
    initSearch();
    initCodeBlocks();
    initBackToTop();
    initReadingProgress();
    initTabs();
    initKatex();
    initMermaid();
    initTocHighlight();
});

// Theme Toggle
function initThemeToggle() {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const stored = localStorage.getItem('theme');
    const initial = stored || (prefersDark ? 'dark' : 'light');
    
    document.documentElement.dataset.theme = initial;
    
    toggle.addEventListener('click', () => {
        const current = document.documentElement.dataset.theme;
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = next;
        localStorage.setItem('theme', next);
    });
}

// Mobile Navigation
function initMobileNav() {
    const toggle = document.querySelector('.mobile-nav-toggle');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    if (!toggle || !sidebar) return;
    
    toggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay?.classList.toggle('active');
    });
    
    overlay?.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    });
}

// Search
function initSearch() {
    const input = document.querySelector('.search-input');
    const results = document.querySelector('.search-results');
    
    if (!input || !results) return;
    
    let searchIndex = null;
    
    input.addEventListener('focus', async () => {
        if (!searchIndex) {
            try {
                const response = await fetch('/search-index.json');
                searchIndex = await response.json();
            } catch (e) {
                console.warn('Search index not available');
            }
        }
    });
    
    input.addEventListener('input', () => {
        const query = input.value.toLowerCase().trim();
        
        if (!query || !searchIndex) {
            results.hidden = true;
            return;
        }
        
        const matches = searchIndex.filter(item =>
            item.title.toLowerCase().includes(query) ||
            item.content.toLowerCase().includes(query)
        ).slice(0, 10);
        
        if (matches.length === 0) {
            results.innerHTML = '<div class="search-result-item">No results found</div>';
        } else {
            results.innerHTML = matches.map(item => `
                <a href="${item.url}" class="search-result-item">
                    <strong>${item.title}</strong>
                    <p>${item.excerpt || ''}</p>
                </a>
            `).join('');
        }
        
        results.hidden = false;
    });
    
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            results.hidden = true;
        }
    });
}

// Code Blocks
function initCodeBlocks() {
    document.querySelectorAll('pre code').forEach(block => {
        const pre = block.parentElement;
        const wrapper = document.createElement('div');
        wrapper.className = 'code-wrapper';
        
        const header = document.createElement('div');
        header.className = 'code-header';
        
        const lang = block.className.match(/language-(\\w+)/)?.[1] || 'text';
        header.innerHTML = `
            <span>${lang}</span>
            <button class="copy-button" aria-label="Copy code">Copy</button>
        `;
        
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(header);
        wrapper.appendChild(pre);
        
        header.querySelector('.copy-button').addEventListener('click', async () => {
            await navigator.clipboard.writeText(block.textContent);
            const btn = header.querySelector('.copy-button');
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 2000);
        });
    });
}

// Back to Top
function initBackToTop() {
    const btn = document.querySelector('.back-to-top');
    if (!btn) return;
    
    window.addEventListener('scroll', () => {
        btn.classList.toggle('visible', window.scrollY > 500);
    });
    
    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// Reading Progress
function initReadingProgress() {
    const bar = document.querySelector('.reading-progress');
    if (!bar) return;
    
    window.addEventListener('scroll', () => {
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        const progress = (window.scrollY / scrollable) * 100;
        bar.style.width = `${Math.min(progress, 100)}%`;
    });
}

// Tabs
function initTabs() {
    document.querySelectorAll('.tab-set').forEach(tabSet => {
        const buttons = tabSet.querySelectorAll('.tab-button');
        const panels = tabSet.querySelectorAll('.tab-panel');
        
        buttons.forEach((btn, i) => {
            btn.addEventListener('click', () => {
                buttons.forEach(b => b.classList.remove('active'));
                panels.forEach(p => p.classList.remove('active'));
                
                btn.classList.add('active');
                panels[i]?.classList.add('active');
            });
        });
        
        // Activate first tab
        buttons[0]?.classList.add('active');
        panels[0]?.classList.add('active');
    });
}

// KaTeX
function initKatex() {
    if (typeof renderMathInElement === 'undefined') return;
    
    renderMathInElement(document.body, {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\\\[', right: '\\\\]', display: true},
            {left: '\\\\(', right: '\\\\)', display: false},
        ],
        throwOnError: false,
    });
}

// Mermaid
function initMermaid() {
    if (typeof mermaid === 'undefined') return;
    
    mermaid.initialize({
        startOnLoad: true,
        theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'default',
    });
}

// TOC Highlight
function initTocHighlight() {
    const toc = document.querySelector('.toc');
    if (!toc) return;
    
    const headings = Array.from(document.querySelectorAll('h2, h3, h4'));
    const links = toc.querySelectorAll('.toc-link');
    
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                links.forEach(link => {
                    link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
                });
            }
        });
    }, { rootMargin: '-100px 0px -80%' });
    
    headings.forEach(h => observer.observe(h));
}
""" + (self.theme.custom_js or '')


# ============================================================================
# Theme Manager
# ============================================================================

class ThemeManager:
    """
    Manages theme loading and registration.
    """
    
    def __init__(self, themes_dir: Optional[Path] = None):
        """
        Initialize theme manager.
        
        Args:
            themes_dir: Directory containing custom themes
        """
        self.themes_dir = themes_dir
        self._themes: Dict[str, ThemeConfig] = BUILTIN_THEMES.copy()
        
        if themes_dir:
            self._load_custom_themes()
    
    def _load_custom_themes(self):
        """Load custom themes from directory."""
        if not self.themes_dir or not self.themes_dir.exists():
            return
        
        for theme_file in self.themes_dir.glob("*.yml"):
            try:
                theme = ThemeConfig.load(theme_file)
                self._themes[theme.name] = theme
                logger.info(f"Loaded custom theme: {theme.name}")
            except Exception as e:
                logger.warning(f"Failed to load theme {theme_file}: {e}")
    
    def get_theme(self, name: str) -> ThemeConfig:
        """Get theme by name."""
        if name not in self._themes:
            logger.warning(f"Theme '{name}' not found, using default")
            return THEME_BOOK
        return self._themes[name]
    
    def list_themes(self) -> List[str]:
        """List available themes."""
        return list(self._themes.keys())
    
    def register_theme(self, theme: ThemeConfig):
        """Register a custom theme."""
        self._themes[theme.name] = theme
    
    def create_engine(self, theme_name: str) -> ThemeEngine:
        """Create theme engine for a theme."""
        theme = self.get_theme(theme_name)
        return ThemeEngine(theme)
