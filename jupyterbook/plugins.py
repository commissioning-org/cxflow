"""
CXFlow Jupyter Book Plugin System

Extensible plugin architecture for custom directives, transforms,
and build hooks.
"""

from __future__ import annotations

import re
import importlib
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Type, TypeVar
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Plugin Types
# ============================================================================

class PluginType(str, Enum):
    """Types of plugins."""
    DIRECTIVE = "directive"
    ROLE = "role"
    TRANSFORM = "transform"
    RENDERER = "renderer"
    HOOK = "hook"
    EXPORTER = "exporter"


class HookType(str, Enum):
    """Build hook types."""
    PRE_BUILD = "pre_build"
    POST_BUILD = "post_build"
    PRE_PARSE = "pre_parse"
    POST_PARSE = "post_parse"
    PRE_RENDER = "pre_render"
    POST_RENDER = "post_render"
    PRE_EXPORT = "pre_export"
    POST_EXPORT = "post_export"


# ============================================================================
# Plugin Base Classes
# ============================================================================

@dataclass
class PluginInfo:
    """Plugin metadata."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: List[str] = field(default_factory=list)


class Plugin(ABC):
    """Base class for all plugins."""
    
    info: PluginInfo
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        pass


class DirectivePlugin(Plugin):
    """
    Base class for directive plugins.
    
    Directives are block-level elements in MyST Markdown:
    ```{directive-name} argument
    :option: value
    Content
    ```
    """
    
    directive_name: str
    has_content: bool = True
    required_arguments: int = 0
    optional_arguments: int = 0
    option_spec: Dict[str, Callable] = field(default_factory=dict)
    
    @abstractmethod
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        """
        Execute the directive.
        
        Args:
            argument: Directive argument (after directive name)
            options: Parsed options dictionary
            content: Directive body content
            source_file: Source file path
            
        Returns:
            Dict with parsed result including 'html', 'type', etc.
        """
        pass
    
    def parse_options(self, body: str) -> tuple[Dict[str, Any], str]:
        """Parse options from body content."""
        lines = body.split('\n')
        options = {}
        content_start = 0
        
        for i, line in enumerate(lines):
            if line.startswith(':'):
                match = re.match(r':(\w+):\s*(.*)', line)
                if match:
                    key = match.group(1)
                    value = match.group(2).strip()
                    
                    # Apply option spec if available
                    if key in self.option_spec:
                        try:
                            value = self.option_spec[key](value)
                        except Exception:
                            pass
                    
                    options[key] = value
                    content_start = i + 1
            else:
                break
        
        content = '\n'.join(lines[content_start:]).strip()
        return options, content


class RolePlugin(Plugin):
    """
    Base class for role plugins.
    
    Roles are inline elements in MyST Markdown:
    {role-name}`content`
    """
    
    role_name: str
    
    @abstractmethod
    def run(
        self,
        content: str,
        source_file: str,
        output_format: str = "html",
    ) -> str:
        """
        Execute the role.
        
        Args:
            content: Role content (inside backticks)
            source_file: Source file path
            output_format: Target output format
            
        Returns:
            Rendered output string
        """
        pass


class TransformPlugin(Plugin):
    """
    Base class for transform plugins.
    
    Transforms modify content during the build process.
    """
    
    priority: int = 500  # 0-1000, lower runs first
    
    @abstractmethod
    def transform(
        self,
        content: str,
        source_file: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Transform content.
        
        Args:
            content: Content to transform
            source_file: Source file path
            context: Build context
            
        Returns:
            Transformed content
        """
        pass


class RendererPlugin(Plugin):
    """
    Base class for renderer plugins.
    
    Renderers convert parsed content to output format.
    """
    
    output_format: str
    
    @abstractmethod
    def render(
        self,
        element: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """
        Render an element.
        
        Args:
            element: Parsed element dictionary
            context: Render context
            
        Returns:
            Rendered output string
        """
        pass


class HookPlugin(Plugin):
    """
    Base class for build hook plugins.
    
    Hooks are called at various points in the build process.
    """
    
    hook_type: HookType
    priority: int = 500
    
    @abstractmethod
    def execute(
        self,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Execute the hook.
        
        Args:
            context: Build context
            
        Returns:
            Modified context or None
        """
        pass


class ExporterPlugin(Plugin):
    """
    Base class for exporter plugins.
    
    Exporters produce output in different formats.
    """
    
    format_name: str
    file_extension: str
    
    @abstractmethod
    def export(
        self,
        content: Dict[str, Any],
        output_path: Path,
        config: Dict[str, Any],
    ) -> Path:
        """
        Export content to file.
        
        Args:
            content: Parsed content
            output_path: Output file path
            config: Export configuration
            
        Returns:
            Path to exported file
        """
        pass


# ============================================================================
# Built-in Directive Plugins
# ============================================================================

class MermaidDirective(DirectivePlugin):
    """Mermaid diagram directive."""
    
    info = PluginInfo(
        name="mermaid",
        description="Render Mermaid diagrams",
    )
    directive_name = "mermaid"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.theme = config.get('theme', 'default')
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        caption = options.get('caption', '')
        name = options.get('name', '')
        
        html = f'''
<figure class="mermaid-figure" id="{name}">
    <div class="mermaid" data-theme="{self.theme}">
{content}
    </div>
    {f'<figcaption>{caption}</figcaption>' if caption else ''}
</figure>
'''
        return {
            'type': 'mermaid',
            'html': html,
            'content': content,
            'caption': caption,
            'name': name,
        }


class YouTubeDirective(DirectivePlugin):
    """YouTube video embed directive."""
    
    info = PluginInfo(
        name="youtube",
        description="Embed YouTube videos",
    )
    directive_name = "youtube"
    has_content = False
    required_arguments = 1
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        video_id = argument.strip()
        width = options.get('width', '100%')
        height = options.get('height', '400')
        
        html = f'''
<div class="video-container">
    <iframe 
        src="https://www.youtube.com/embed/{video_id}"
        width="{width}"
        height="{height}"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen>
    </iframe>
</div>
'''
        return {
            'type': 'youtube',
            'html': html,
            'video_id': video_id,
        }


class DropdownDirective(DirectivePlugin):
    """Collapsible dropdown directive."""
    
    info = PluginInfo(
        name="dropdown",
        description="Collapsible content sections",
    )
    directive_name = "dropdown"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        title = argument or options.get('title', 'Click to expand')
        open_by_default = options.get('open', False)
        icon = options.get('icon', '▶')
        
        open_attr = 'open' if open_by_default else ''
        
        html = f'''
<details class="dropdown" {open_attr}>
    <summary class="dropdown-title">
        <span class="dropdown-icon">{icon}</span>
        {title}
    </summary>
    <div class="dropdown-content">
        {content}
    </div>
</details>
'''
        return {
            'type': 'dropdown',
            'html': html,
            'title': title,
            'content': content,
        }


class ProofDirective(DirectivePlugin):
    """Mathematical proof directive."""
    
    info = PluginInfo(
        name="proof",
        description="Mathematical proofs with QED",
    )
    directive_name = "proof"
    
    PROOF_TYPES = {
        'proof': 'Proof',
        'theorem': 'Theorem',
        'lemma': 'Lemma',
        'corollary': 'Corollary',
        'proposition': 'Proposition',
        'definition': 'Definition',
        'example': 'Example',
        'remark': 'Remark',
    }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._counters: Dict[str, int] = {t: 0 for t in self.PROOF_TYPES}
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        proof_type = options.get('type', 'proof')
        title = argument or self.PROOF_TYPES.get(proof_type, 'Proof')
        name = options.get('name', '')
        numbered = options.get('numbered', True)
        
        if numbered and proof_type in self._counters:
            self._counters[proof_type] += 1
            number = self._counters[proof_type]
            full_title = f'{title} {number}'
        else:
            full_title = title
        
        html = f'''
<div class="proof proof-{proof_type}" id="{name}">
    <p class="proof-title"><strong>{full_title}.</strong></p>
    <div class="proof-content">
        {content}
    </div>
    <span class="qed">∎</span>
</div>
'''
        return {
            'type': 'proof',
            'html': html,
            'proof_type': proof_type,
            'title': full_title,
            'content': content,
        }


class ExerciseDirective(DirectivePlugin):
    """Exercise with solution directive."""
    
    info = PluginInfo(
        name="exercise",
        description="Exercises with hidden solutions",
    )
    directive_name = "exercise"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._counter = 0
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        self._counter += 1
        number = options.get('number', self._counter)
        title = argument or f'Exercise {number}'
        difficulty = options.get('difficulty', '')
        solution = options.get('solution', '')
        name = options.get('name', f'exercise-{number}')
        
        difficulty_badge = ''
        if difficulty:
            colors = {'easy': 'green', 'medium': 'yellow', 'hard': 'red'}
            color = colors.get(difficulty.lower(), 'gray')
            difficulty_badge = f'<span class="badge badge-{color}">{difficulty}</span>'
        
        solution_html = ''
        if solution:
            solution_html = f'''
<details class="exercise-solution">
    <summary>Show Solution</summary>
    <div class="solution-content">{solution}</div>
</details>
'''
        
        html = f'''
<div class="exercise" id="{name}">
    <div class="exercise-header">
        <span class="exercise-title">{title}</span>
        {difficulty_badge}
    </div>
    <div class="exercise-content">
        {content}
    </div>
    {solution_html}
</div>
'''
        return {
            'type': 'exercise',
            'html': html,
            'title': title,
            'number': number,
            'content': content,
        }


class MarginNoteDirective(DirectivePlugin):
    """Margin note directive (like Tufte)."""
    
    info = PluginInfo(
        name="margin",
        description="Margin notes (Tufte style)",
    )
    directive_name = "margin"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        label = argument or ''
        
        html = f'''
<span class="margin-note">
    <span class="margin-note-label">{label}</span>
    <span class="margin-note-content">{content}</span>
</span>
'''
        return {
            'type': 'margin-note',
            'html': html,
            'label': label,
            'content': content,
        }


class TimelineDirective(DirectivePlugin):
    """Timeline directive."""
    
    info = PluginInfo(
        name="timeline",
        description="Event timeline visualization",
    )
    directive_name = "timeline"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def run(
        self,
        argument: str,
        options: Dict[str, Any],
        content: str,
        source_file: str,
    ) -> Dict[str, Any]:
        # Parse timeline entries from content
        # Format: - YYYY-MM-DD: Event description
        entries = []
        for line in content.strip().split('\n'):
            match = re.match(r'-\s*(\d{4}(?:-\d{2})?(?:-\d{2})?):?\s*(.*)', line)
            if match:
                entries.append({
                    'date': match.group(1),
                    'content': match.group(2),
                })
        
        items_html = '\n'.join([
            f'''
<div class="timeline-item">
    <div class="timeline-date">{e['date']}</div>
    <div class="timeline-content">{e['content']}</div>
</div>
'''
            for e in entries
        ])
        
        html = f'''
<div class="timeline">
    {items_html}
</div>
'''
        return {
            'type': 'timeline',
            'html': html,
            'entries': entries,
        }


# ============================================================================
# Built-in Role Plugins
# ============================================================================

class AbbreviationRole(RolePlugin):
    """Abbreviation role with tooltip."""
    
    info = PluginInfo(
        name="abbr",
        description="Abbreviations with definitions",
    )
    role_name = "abbr"
    
    def __init__(self):
        self._abbreviations: Dict[str, str] = {}
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._abbreviations = config.get('abbreviations', {})
    
    def run(
        self,
        content: str,
        source_file: str,
        output_format: str = "html",
    ) -> str:
        # Check for inline definition: {abbr}`API (Application Programming Interface)`
        match = re.match(r'(\w+)\s*\(([^)]+)\)', content)
        if match:
            abbr = match.group(1)
            definition = match.group(2)
        else:
            abbr = content
            definition = self._abbreviations.get(abbr, abbr)
        
        if output_format == "html":
            return f'<abbr title="{definition}">{abbr}</abbr>'
        else:
            return f'{abbr} ({definition})'


class KeyboardRole(RolePlugin):
    """Keyboard shortcut role."""
    
    info = PluginInfo(
        name="kbd",
        description="Keyboard shortcuts",
    )
    role_name = "kbd"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def run(
        self,
        content: str,
        source_file: str,
        output_format: str = "html",
    ) -> str:
        # Split on + and wrap each key
        keys = [k.strip() for k in content.split('+')]
        
        if output_format == "html":
            key_html = '+'.join([f'<kbd>{k}</kbd>' for k in keys])
            return f'<span class="keyboard-shortcut">{key_html}</span>'
        else:
            return content


class BadgeRole(RolePlugin):
    """Badge/label role."""
    
    info = PluginInfo(
        name="badge",
        description="Inline badges and labels",
    )
    role_name = "badge"
    
    COLORS = {
        'new': 'green',
        'deprecated': 'red',
        'experimental': 'yellow',
        'beta': 'blue',
        'stable': 'green',
        'warning': 'orange',
    }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def run(
        self,
        content: str,
        source_file: str,
        output_format: str = "html",
    ) -> str:
        # Check for color specification: {badge}`NEW:green`
        parts = content.split(':')
        text = parts[0]
        color = parts[1] if len(parts) > 1 else self.COLORS.get(text.lower(), 'gray')
        
        if output_format == "html":
            return f'<span class="badge badge-{color}">{text}</span>'
        else:
            return f'[{text}]'


class DownloadRole(RolePlugin):
    """Download link role."""
    
    info = PluginInfo(
        name="download",
        description="File download links",
    )
    role_name = "download"
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.assets_dir = config.get('assets_dir', '_assets')
    
    def run(
        self,
        content: str,
        source_file: str,
        output_format: str = "html",
    ) -> str:
        # Check for display text: {download}`Download PDF <file.pdf>`
        match = re.match(r'([^<]+)<([^>]+)>', content)
        if match:
            text = match.group(1).strip()
            path = match.group(2).strip()
        else:
            path = content
            text = Path(path).name
        
        if output_format == "html":
            return f'<a href="{path}" download class="download-link">⬇ {text}</a>'
        else:
            return f'[{text}]({path})'


# ============================================================================
# Built-in Transform Plugins
# ============================================================================

class AutoLinkTransform(TransformPlugin):
    """Auto-link URLs and email addresses."""
    
    info = PluginInfo(
        name="autolink",
        description="Auto-link URLs and emails",
    )
    priority = 100
    
    URL_PATTERN = re.compile(
        r'(?<![\[\(])(https?://[^\s<>\[\]]+)(?![\]\)])'
    )
    EMAIL_PATTERN = re.compile(
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    )
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def transform(
        self,
        content: str,
        source_file: str,
        context: Dict[str, Any],
    ) -> str:
        # Don't process inside code blocks
        def replace_urls(text):
            return self.URL_PATTERN.sub(r'[\1](\1)', text)
        
        def replace_emails(text):
            return self.EMAIL_PATTERN.sub(r'[\1](mailto:\1)', text)
        
        # Simple approach: don't process in code blocks
        parts = []
        in_code = False
        
        for line in content.split('\n'):
            if line.startswith('```'):
                in_code = not in_code
            
            if not in_code:
                line = replace_urls(line)
                line = replace_emails(line)
            
            parts.append(line)
        
        return '\n'.join(parts)


class EmojiTransform(TransformPlugin):
    """Convert emoji shortcodes to Unicode."""
    
    info = PluginInfo(
        name="emoji",
        description="Emoji shortcode conversion",
    )
    priority = 200
    
    EMOJI_MAP = {
        ':smile:': '😄', ':heart:': '❤️', ':fire:': '🔥',
        ':star:': '⭐', ':check:': '✅', ':x:': '❌',
        ':warning:': '⚠️', ':info:': 'ℹ️', ':question:': '❓',
        ':bulb:': '💡', ':rocket:': '🚀', ':tada:': '🎉',
        ':thumbsup:': '👍', ':thumbsdown:': '👎', ':eyes:': '👀',
        ':book:': '📖', ':memo:': '📝', ':link:': '🔗',
        ':gear:': '⚙️', ':wrench:': '🔧', ':hammer:': '🔨',
        ':zap:': '⚡', ':clock:': '🕐', ':calendar:': '📅',
        ':folder:': '📁', ':file:': '📄', ':lock:': '🔒',
        ':key:': '🔑', ':bug:': '🐛', ':sparkles:': '✨',
    }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        custom = config.get('custom_emoji', {})
        self.EMOJI_MAP.update(custom)
    
    def transform(
        self,
        content: str,
        source_file: str,
        context: Dict[str, Any],
    ) -> str:
        for shortcode, emoji in self.EMOJI_MAP.items():
            content = content.replace(shortcode, emoji)
        return content


class SmartQuotesTransform(TransformPlugin):
    """Convert straight quotes to smart quotes."""
    
    info = PluginInfo(
        name="smartquotes",
        description="Smart quote conversion",
    )
    priority = 900
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.enabled = config.get('enabled', True)
    
    def transform(
        self,
        content: str,
        source_file: str,
        context: Dict[str, Any],
    ) -> str:
        if not self.enabled:
            return content
        
        # Don't process code blocks
        parts = []
        in_code = False
        
        for line in content.split('\n'):
            if line.startswith('```'):
                in_code = not in_code
            
            if not in_code and '`' not in line:
                # Opening double quotes
                line = re.sub(r'"(\w)', r'"\1', line)
                # Closing double quotes
                line = re.sub(r'(\w)"', r'\1"', line)
                # Opening single quotes
                line = re.sub(r"'(\w)", r''\1', line)
                # Closing single quotes / apostrophes
                line = re.sub(r"(\w)'", r'\1'', line)
                # Em-dashes
                line = line.replace('---', '—')
                # En-dashes
                line = line.replace('--', '–')
                # Ellipsis
                line = line.replace('...', '…')
            
            parts.append(line)
        
        return '\n'.join(parts)


# ============================================================================
# Plugin Registry
# ============================================================================

class PluginRegistry:
    """
    Central registry for all plugins.
    """
    
    def __init__(self):
        self._directives: Dict[str, DirectivePlugin] = {}
        self._roles: Dict[str, RolePlugin] = {}
        self._transforms: List[TransformPlugin] = []
        self._renderers: Dict[str, RendererPlugin] = {}
        self._hooks: Dict[HookType, List[HookPlugin]] = {
            hook_type: [] for hook_type in HookType
        }
        self._exporters: Dict[str, ExporterPlugin] = {}
        
        self._register_builtins()
    
    def _register_builtins(self):
        """Register built-in plugins."""
        # Directives
        self.register_directive(MermaidDirective())
        self.register_directive(YouTubeDirective())
        self.register_directive(DropdownDirective())
        self.register_directive(ProofDirective())
        self.register_directive(ExerciseDirective())
        self.register_directive(MarginNoteDirective())
        self.register_directive(TimelineDirective())
        
        # Roles
        self.register_role(AbbreviationRole())
        self.register_role(KeyboardRole())
        self.register_role(BadgeRole())
        self.register_role(DownloadRole())
        
        # Transforms
        self.register_transform(AutoLinkTransform())
        self.register_transform(EmojiTransform())
        self.register_transform(SmartQuotesTransform())
    
    def register_directive(self, plugin: DirectivePlugin):
        """Register a directive plugin."""
        self._directives[plugin.directive_name] = plugin
        logger.debug(f"Registered directive: {plugin.directive_name}")
    
    def register_role(self, plugin: RolePlugin):
        """Register a role plugin."""
        self._roles[plugin.role_name] = plugin
        logger.debug(f"Registered role: {plugin.role_name}")
    
    def register_transform(self, plugin: TransformPlugin):
        """Register a transform plugin."""
        self._transforms.append(plugin)
        self._transforms.sort(key=lambda p: p.priority)
        logger.debug(f"Registered transform: {plugin.info.name}")
    
    def register_renderer(self, plugin: RendererPlugin):
        """Register a renderer plugin."""
        self._renderers[plugin.output_format] = plugin
        logger.debug(f"Registered renderer: {plugin.output_format}")
    
    def register_hook(self, plugin: HookPlugin):
        """Register a hook plugin."""
        self._hooks[plugin.hook_type].append(plugin)
        self._hooks[plugin.hook_type].sort(key=lambda p: p.priority)
        logger.debug(f"Registered hook: {plugin.info.name} ({plugin.hook_type})")
    
    def register_exporter(self, plugin: ExporterPlugin):
        """Register an exporter plugin."""
        self._exporters[plugin.format_name] = plugin
        logger.debug(f"Registered exporter: {plugin.format_name}")
    
    def get_directive(self, name: str) -> Optional[DirectivePlugin]:
        """Get a directive plugin by name."""
        return self._directives.get(name)
    
    def get_role(self, name: str) -> Optional[RolePlugin]:
        """Get a role plugin by name."""
        return self._roles.get(name)
    
    def get_transforms(self) -> List[TransformPlugin]:
        """Get all transform plugins sorted by priority."""
        return self._transforms.copy()
    
    def get_renderer(self, format_: str) -> Optional[RendererPlugin]:
        """Get a renderer plugin by format."""
        return self._renderers.get(format_)
    
    def get_hooks(self, hook_type: HookType) -> List[HookPlugin]:
        """Get all hook plugins for a hook type."""
        return self._hooks[hook_type].copy()
    
    def get_exporter(self, format_: str) -> Optional[ExporterPlugin]:
        """Get an exporter plugin by format."""
        return self._exporters.get(format_)
    
    def list_directives(self) -> List[str]:
        """List all registered directives."""
        return list(self._directives.keys())
    
    def list_roles(self) -> List[str]:
        """List all registered roles."""
        return list(self._roles.keys())
    
    def list_exporters(self) -> List[str]:
        """List all registered exporters."""
        return list(self._exporters.keys())
    
    def initialize_all(self, config: Dict[str, Any]):
        """Initialize all plugins with configuration."""
        for plugin in self._directives.values():
            plugin.initialize(config.get(plugin.directive_name, {}))
        
        for plugin in self._roles.values():
            plugin.initialize(config.get(plugin.role_name, {}))
        
        for plugin in self._transforms:
            plugin.initialize(config.get(plugin.info.name, {}))
        
        for plugin in self._renderers.values():
            plugin.initialize(config.get(plugin.output_format, {}))
        
        for hooks in self._hooks.values():
            for plugin in hooks:
                plugin.initialize(config.get(plugin.info.name, {}))
        
        for plugin in self._exporters.values():
            plugin.initialize(config.get(plugin.format_name, {}))


# ============================================================================
# Plugin Loader
# ============================================================================

class PluginLoader:
    """
    Loads plugins from various sources.
    """
    
    def __init__(self, registry: PluginRegistry):
        self.registry = registry
    
    def load_from_module(self, module_name: str):
        """
        Load plugins from a Python module.
        
        Args:
            module_name: Full module name (e.g., 'mypackage.plugins')
        """
        try:
            module = importlib.import_module(module_name)
            self._register_from_module(module)
        except ImportError as e:
            logger.error(f"Failed to import plugin module {module_name}: {e}")
    
    def load_from_file(self, file_path: Path):
        """
        Load plugins from a Python file.
        
        Args:
            file_path: Path to Python file
        """
        try:
            spec = importlib.util.spec_from_file_location(
                file_path.stem,
                file_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._register_from_module(module)
        except Exception as e:
            logger.error(f"Failed to load plugin file {file_path}: {e}")
    
    def load_from_directory(self, dir_path: Path):
        """
        Load all plugins from a directory.
        
        Args:
            dir_path: Directory containing plugin files
        """
        if not dir_path.exists():
            return
        
        for file_path in dir_path.glob("*.py"):
            if file_path.name.startswith('_'):
                continue
            self.load_from_file(file_path)
    
    def _register_from_module(self, module):
        """Register all plugins from a module."""
        for name in dir(module):
            obj = getattr(module, name)
            
            if not isinstance(obj, type):
                continue
            
            if issubclass(obj, DirectivePlugin) and obj != DirectivePlugin:
                try:
                    self.registry.register_directive(obj())
                except Exception as e:
                    logger.error(f"Failed to register directive {name}: {e}")
            
            elif issubclass(obj, RolePlugin) and obj != RolePlugin:
                try:
                    self.registry.register_role(obj())
                except Exception as e:
                    logger.error(f"Failed to register role {name}: {e}")
            
            elif issubclass(obj, TransformPlugin) and obj != TransformPlugin:
                try:
                    self.registry.register_transform(obj())
                except Exception as e:
                    logger.error(f"Failed to register transform {name}: {e}")
            
            elif issubclass(obj, HookPlugin) and obj != HookPlugin:
                try:
                    self.registry.register_hook(obj())
                except Exception as e:
                    logger.error(f"Failed to register hook {name}: {e}")
            
            elif issubclass(obj, ExporterPlugin) and obj != ExporterPlugin:
                try:
                    self.registry.register_exporter(obj())
                except Exception as e:
                    logger.error(f"Failed to register exporter {name}: {e}")


# ============================================================================
# Global Registry
# ============================================================================

# Global plugin registry instance
_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_registry():
    """Reset the global plugin registry."""
    global _registry
    _registry = PluginRegistry()
