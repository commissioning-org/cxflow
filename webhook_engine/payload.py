"""Payload builders and formatters for webhook requests."""

from __future__ import annotations

import copy
import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


@dataclass
class PayloadMetadata:
    """Metadata attached to payloads."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "webhook_engine"
    version: str = "1.0"
    correlation_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "version": self.version,
            "correlation_id": self.correlation_id,
            "tags": self.tags,
        }


class PayloadTransformer(ABC):
    """Abstract base class for payload transformers."""
    
    @abstractmethod
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Transform a payload."""
        pass


class FlattenTransformer(PayloadTransformer):
    """Flatten nested dictionaries with dot notation keys."""
    
    def __init__(self, separator: str = ".", max_depth: int = 10):
        self.separator = separator
        self.max_depth = max_depth
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Flatten the payload."""
        return self._flatten(payload, "", 0)
    
    def _flatten(
        self, obj: Any, prefix: str, depth: int
    ) -> dict[str, Any]:
        result = {}
        
        if depth >= self.max_depth:
            result[prefix.rstrip(self.separator)] = obj
            return result
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}{key}{self.separator}" if prefix else f"{key}{self.separator}"
                result.update(self._flatten(value, new_key, depth + 1))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_key = f"{prefix}{i}{self.separator}"
                result.update(self._flatten(item, new_key, depth + 1))
        else:
            result[prefix.rstrip(self.separator)] = obj
        
        return result


class UnflattenTransformer(PayloadTransformer):
    """Unflatten dot-notation keys into nested dictionaries."""
    
    def __init__(self, separator: str = "."):
        self.separator = separator
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Unflatten the payload."""
        result: dict[str, Any] = {}
        
        for key, value in payload.items():
            parts = key.split(self.separator)
            current = result
            
            for i, part in enumerate(parts[:-1]):
                # Check if next part is numeric (array index)
                if parts[i + 1].isdigit():
                    if part not in current:
                        current[part] = []
                    current = current[part]
                else:
                    if part.isdigit():
                        idx = int(part)
                        while len(current) <= idx:
                            current.append({})
                        current = current[idx]
                    else:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
            
            final_key = parts[-1]
            if final_key.isdigit():
                idx = int(final_key)
                while len(current) <= idx:
                    current.append(None)
                current[idx] = value
            else:
                current[final_key] = value
        
        return result


class FilterTransformer(PayloadTransformer):
    """Filter payload keys."""
    
    def __init__(
        self,
        include_keys: Optional[list[str]] = None,
        exclude_keys: Optional[list[str]] = None,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ):
        self.include_keys = set(include_keys) if include_keys else None
        self.exclude_keys = set(exclude_keys) if exclude_keys else set()
        self.include_patterns = [re.compile(p) for p in (include_patterns or [])]
        self.exclude_patterns = [re.compile(p) for p in (exclude_patterns or [])]
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Filter the payload."""
        result = {}
        
        for key, value in payload.items():
            # Check exclusions first
            if key in self.exclude_keys:
                continue
            if any(p.match(key) for p in self.exclude_patterns):
                continue
            
            # Check inclusions
            if self.include_keys is not None:
                if key not in self.include_keys:
                    if not any(p.match(key) for p in self.include_patterns):
                        continue
            elif self.include_patterns:
                if not any(p.match(key) for p in self.include_patterns):
                    continue
            
            # Include the key
            if isinstance(value, dict):
                result[key] = self.transform(value)
            else:
                result[key] = value
        
        return result


class RenameTransformer(PayloadTransformer):
    """Rename payload keys."""
    
    def __init__(self, mapping: dict[str, str], recursive: bool = True):
        self.mapping = mapping
        self.recursive = recursive
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rename keys in the payload."""
        result = {}
        
        for key, value in payload.items():
            new_key = self.mapping.get(key, key)
            
            if self.recursive and isinstance(value, dict):
                result[new_key] = self.transform(value)
            elif self.recursive and isinstance(value, list):
                result[new_key] = [
                    self.transform(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[new_key] = value
        
        return result


class DefaultsTransformer(PayloadTransformer):
    """Apply default values to payload."""
    
    def __init__(self, defaults: dict[str, Any], deep: bool = True):
        self.defaults = defaults
        self.deep = deep
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply defaults to the payload."""
        if self.deep:
            return self._deep_merge(copy.deepcopy(self.defaults), payload)
        else:
            result = copy.deepcopy(self.defaults)
            result.update(payload)
            return result
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


class LambdaTransformer(PayloadTransformer):
    """Apply a custom function to transform payload."""
    
    def __init__(self, fn: Callable[[dict[str, Any]], dict[str, Any]]):
        self.fn = fn
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply the function to the payload."""
        return self.fn(payload)


class ChainTransformer(PayloadTransformer):
    """Chain multiple transformers together."""
    
    def __init__(self, *transformers: PayloadTransformer):
        self.transformers = list(transformers)
    
    def add(self, transformer: PayloadTransformer) -> ChainTransformer:
        """Add a transformer to the chain."""
        self.transformers.append(transformer)
        return self
    
    def transform(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply all transformers in sequence."""
        result = payload
        for transformer in self.transformers:
            result = transformer.transform(result)
        return result


class PayloadFormatter:
    """Format payloads for different webhook targets."""
    
    @staticmethod
    def power_automate(
        data: dict[str, Any],
        action: str = "trigger",
        metadata: Optional[PayloadMetadata] = None,
    ) -> dict[str, Any]:
        """Format payload for Power Automate webhook."""
        metadata = metadata or PayloadMetadata()
        return {
            "action": action,
            "timestamp": metadata.timestamp.isoformat(),
            "correlationId": metadata.correlation_id or metadata.id,
            "source": metadata.source,
            "data": data,
        }
    
    @staticmethod
    def slack(
        text: str,
        blocks: Optional[list[dict]] = None,
        attachments: Optional[list[dict]] = None,
        channel: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
    ) -> dict[str, Any]:
        """Format payload for Slack webhook."""
        payload: dict[str, Any] = {"text": text}
        
        if blocks:
            payload["blocks"] = blocks
        if attachments:
            payload["attachments"] = attachments
        if channel:
            payload["channel"] = channel
        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji
        
        return payload
    
    @staticmethod
    def discord(
        content: Optional[str] = None,
        embeds: Optional[list[dict]] = None,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
        tts: bool = False,
    ) -> dict[str, Any]:
        """Format payload for Discord webhook."""
        payload: dict[str, Any] = {"tts": tts}
        
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        
        return payload
    
    @staticmethod
    def teams(
        title: str,
        text: str,
        theme_color: str = "0076D7",
        sections: Optional[list[dict]] = None,
        actions: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """Format payload for Microsoft Teams webhook (legacy connector)."""
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color,
            "summary": title,
            "title": title,
            "text": text,
        }
        
        if sections:
            payload["sections"] = sections
        if actions:
            payload["potentialAction"] = actions
        
        return payload
    
    @staticmethod
    def generic_event(
        event_type: str,
        data: dict[str, Any],
        source: str = "webhook_engine",
        subject: Optional[str] = None,
        metadata: Optional[PayloadMetadata] = None,
    ) -> dict[str, Any]:
        """Format as CloudEvents-like generic event."""
        metadata = metadata or PayloadMetadata(source=source)
        return {
            "specversion": "1.0",
            "type": event_type,
            "source": source,
            "subject": subject,
            "id": metadata.id,
            "time": metadata.timestamp.isoformat(),
            "datacontenttype": "application/json",
            "data": data,
        }
    
    @staticmethod
    def zapier(
        data: dict[str, Any],
        event: Optional[str] = None,
    ) -> dict[str, Any]:
        """Format payload for Zapier webhook."""
        payload = {**data}
        if event:
            payload["_event"] = event
        payload["_timestamp"] = datetime.now(timezone.utc).isoformat()
        return payload
    
    @staticmethod
    def make(
        data: dict[str, Any],
        scenario: Optional[str] = None,
    ) -> dict[str, Any]:
        """Format payload for Make (Integromat) webhook."""
        payload = {**data}
        if scenario:
            payload["scenario"] = scenario
        return payload


class PayloadBuilder:
    """Fluent builder for constructing webhook payloads."""
    
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._metadata: Optional[PayloadMetadata] = None
        self._transformers: list[PayloadTransformer] = []
        self._wrapper: Optional[str] = None
        self._envelope: Optional[dict[str, Any]] = None
    
    def data(self, data: dict[str, Any]) -> PayloadBuilder:
        """Set the base data."""
        self._data = copy.deepcopy(data)
        return self
    
    def set(self, key: str, value: Any) -> PayloadBuilder:
        """Set a single key-value pair."""
        self._data[key] = value
        return self
    
    def set_nested(self, path: str, value: Any, separator: str = ".") -> PayloadBuilder:
        """Set a nested value using dot notation."""
        parts = path.split(separator)
        current = self._data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
        return self
    
    def merge(self, data: dict[str, Any]) -> PayloadBuilder:
        """Merge data into the payload."""
        self._data.update(data)
        return self
    
    def deep_merge(self, data: dict[str, Any]) -> PayloadBuilder:
        """Deep merge data into the payload."""
        self._data = DefaultsTransformer(self._data).transform(data)
        return self
    
    def remove(self, *keys: str) -> PayloadBuilder:
        """Remove keys from the payload."""
        for key in keys:
            self._data.pop(key, None)
        return self
    
    def metadata(
        self,
        source: Optional[str] = None,
        correlation_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> PayloadBuilder:
        """Set payload metadata."""
        self._metadata = PayloadMetadata(
            source=source or "webhook_engine",
            correlation_id=correlation_id,
            tags=tags or [],
        )
        return self
    
    def transform(self, transformer: PayloadTransformer) -> PayloadBuilder:
        """Add a transformer to the pipeline."""
        self._transformers.append(transformer)
        return self
    
    def flatten(self, separator: str = ".") -> PayloadBuilder:
        """Add flatten transformation."""
        return self.transform(FlattenTransformer(separator))
    
    def filter(
        self,
        include: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
    ) -> PayloadBuilder:
        """Add filter transformation."""
        return self.transform(FilterTransformer(include_keys=include, exclude_keys=exclude))
    
    def rename(self, mapping: dict[str, str]) -> PayloadBuilder:
        """Add rename transformation."""
        return self.transform(RenameTransformer(mapping))
    
    def defaults(self, defaults: dict[str, Any]) -> PayloadBuilder:
        """Add defaults transformation."""
        return self.transform(DefaultsTransformer(defaults))
    
    def map(self, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> PayloadBuilder:
        """Add a custom transformation function."""
        return self.transform(LambdaTransformer(fn))
    
    def wrap(self, key: str) -> PayloadBuilder:
        """Wrap the payload under a key."""
        self._wrapper = key
        return self
    
    def envelope(self, template: dict[str, Any], data_key: str = "data") -> PayloadBuilder:
        """Wrap payload in an envelope template."""
        self._envelope = template
        self._wrapper = data_key
        return self
    
    def build(self) -> dict[str, Any]:
        """Build the final payload."""
        # Start with base data
        result = copy.deepcopy(self._data)
        
        # Apply transformers
        for transformer in self._transformers:
            result = transformer.transform(result)
        
        # Add metadata
        if self._metadata:
            result["_metadata"] = self._metadata.to_dict()
        
        # Apply wrapper
        if self._wrapper:
            result = {self._wrapper: result}
        
        # Apply envelope
        if self._envelope:
            envelope = copy.deepcopy(self._envelope)
            if self._wrapper:
                envelope[self._wrapper] = result[self._wrapper]
            else:
                envelope["data"] = result
            result = envelope
        
        return result
    
    def for_power_automate(self, action: str = "trigger") -> dict[str, Any]:
        """Build and format for Power Automate."""
        data = self.build()
        return PayloadFormatter.power_automate(data, action, self._metadata)
    
    def for_slack(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Build and format for Slack."""
        return PayloadFormatter.slack(text, **kwargs)
    
    def for_discord(self, **kwargs: Any) -> dict[str, Any]:
        """Build and format for Discord."""
        return PayloadFormatter.discord(**kwargs)
    
    def for_teams(self, title: str, text: str, **kwargs: Any) -> dict[str, Any]:
        """Build and format for Teams."""
        return PayloadFormatter.teams(title, text, **kwargs)
    
    def for_event(self, event_type: str, **kwargs: Any) -> dict[str, Any]:
        """Build and format as generic event."""
        data = self.build()
        return PayloadFormatter.generic_event(event_type, data, **kwargs)
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Build and serialize to JSON string."""
        return json.dumps(self.build(), indent=indent, default=str)
