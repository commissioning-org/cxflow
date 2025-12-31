"""
Power Automate Sync Workflow

Comprehensive workflow to push memory, macros, metadata, and data
to Power Automate for automation and integration with Microsoft 365.
"""

from __future__ import annotations

import os
import json
import hashlib
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import gzip
import base64

import requests
from pydantic import BaseModel, Field

# Optional async support
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

POWER_AUTOMATE_WEBHOOK_URL = (
    "https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443"
    "/powerautomate/automations/direct/workflows/3d2dbeba15b5425b8551f67e61084464"
    "/triggers/manual/paths/invoke"
    "?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0"
    "&sig=zcOVZS6oRhfwU-R6rTxxk8EW32faD-S-bcar0DiFfno"
)


class SyncType(str, Enum):
    """Types of data that can be synced."""
    MEMORY = "memory"
    MACROS = "macros"
    METADATA = "metadata"
    DATA = "data"
    CONFIG = "config"
    LOGS = "logs"
    METRICS = "metrics"
    EVENTS = "events"
    FULL = "full"


class SyncStatus(str, Enum):
    """Sync operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class MemoryEntry:
    """Memory/context entry for sync."""
    key: str
    value: Any
    category: str = "general"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MacroDefinition:
    """Macro/automation definition."""
    name: str
    description: str
    trigger: str  # event, schedule, manual, webhook
    actions: List[Dict[str, Any]]
    enabled: bool = True
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetadataRecord:
    """Metadata record for sync."""
    entity_type: str
    entity_id: str
    attributes: Dict[str, Any]
    schema_version: str = "1.0"
    source: str = "cxflow"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DataPayload:
    """Generic data payload for sync."""
    collection: str
    records: List[Dict[str, Any]]
    schema: Optional[Dict[str, Any]] = None
    batch_id: str = field(default_factory=lambda: hashlib.md5(
        datetime.now(timezone.utc).isoformat().encode()
    ).hexdigest()[:12])
    total_count: int = 0
    
    def __post_init__(self):
        if self.total_count == 0:
            self.total_count = len(self.records)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    sync_id: str
    sync_type: SyncType
    status: SyncStatus
    items_sent: int = 0
    items_failed: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_ms: int = 0
    errors: List[str] = field(default_factory=list)
    response_data: Optional[Dict[str, Any]] = None


class SyncPayload(BaseModel):
    """Complete sync payload to Power Automate."""
    sync_id: str
    sync_type: str
    source: str = "cxflow"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Data sections
    memory: Optional[List[Dict[str, Any]]] = None
    macros: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[List[Dict[str, Any]]] = None
    data: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    logs: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    events: Optional[List[Dict[str, Any]]] = None
    
    # Sync metadata
    checksum: Optional[str] = None
    compressed: bool = False
    batch_info: Optional[Dict[str, Any]] = None


# ============================================================================
# Memory Manager
# ============================================================================

class MemoryManager:
    """
    Manages memory/context state for sync to Power Automate.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./.cxflow/memory")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, MemoryEntry] = {}
        self._load_persisted()
    
    def _load_persisted(self):
        """Load persisted memory from disk."""
        memory_file = self.storage_path / "memory.json"
        if memory_file.exists():
            try:
                data = json.loads(memory_file.read_text())
                for key, entry in data.items():
                    self._memory[key] = MemoryEntry(**entry)
            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")
    
    def _persist(self):
        """Persist memory to disk."""
        memory_file = self.storage_path / "memory.json"
        data = {k: asdict(v) for k, v in self._memory.items()}
        memory_file.write_text(json.dumps(data, indent=2, default=str))
    
    def set(
        self,
        key: str,
        value: Any,
        category: str = "general",
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Set a memory entry."""
        entry = MemoryEntry(
            key=key,
            value=value,
            category=category,
            ttl_seconds=ttl_seconds,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._memory[key] = entry
        self._persist()
        return entry
    
    def get(self, key: str) -> Optional[MemoryEntry]:
        """Get a memory entry."""
        entry = self._memory.get(key)
        if entry and entry.ttl_seconds:
            created = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - created).total_seconds() > entry.ttl_seconds:
                del self._memory[key]
                self._persist()
                return None
        return entry
    
    def get_all(self, category: Optional[str] = None) -> List[MemoryEntry]:
        """Get all memory entries, optionally filtered by category."""
        entries = list(self._memory.values())
        if category:
            entries = [e for e in entries if e.category == category]
        return entries
    
    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if key in self._memory:
            del self._memory[key]
            self._persist()
            return True
        return False
    
    def clear(self, category: Optional[str] = None):
        """Clear memory entries."""
        if category:
            self._memory = {k: v for k, v in self._memory.items() if v.category != category}
        else:
            self._memory.clear()
        self._persist()
    
    def export_for_sync(self) -> List[Dict[str, Any]]:
        """Export memory for sync payload."""
        return [asdict(entry) for entry in self._memory.values()]


# ============================================================================
# Macro Manager
# ============================================================================

class MacroManager:
    """
    Manages macro/automation definitions for sync.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./.cxflow/macros")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._macros: Dict[str, MacroDefinition] = {}
        self._load_macros()
    
    def _load_macros(self):
        """Load macros from disk."""
        for macro_file in self.storage_path.glob("*.json"):
            try:
                data = json.loads(macro_file.read_text())
                macro = MacroDefinition(**data)
                self._macros[macro.name] = macro
            except Exception as e:
                logger.warning(f"Failed to load macro {macro_file}: {e}")
    
    def _save_macro(self, macro: MacroDefinition):
        """Save macro to disk."""
        macro_file = self.storage_path / f"{macro.name}.json"
        macro_file.write_text(json.dumps(asdict(macro), indent=2, default=str))
    
    def register(
        self,
        name: str,
        description: str,
        trigger: str,
        actions: List[Dict[str, Any]],
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MacroDefinition:
        """Register a new macro."""
        macro = MacroDefinition(
            name=name,
            description=description,
            trigger=trigger,
            actions=actions,
            enabled=enabled,
            metadata=metadata or {},
        )
        self._macros[name] = macro
        self._save_macro(macro)
        return macro
    
    def get(self, name: str) -> Optional[MacroDefinition]:
        """Get a macro by name."""
        return self._macros.get(name)
    
    def list_all(self, enabled_only: bool = False) -> List[MacroDefinition]:
        """List all macros."""
        macros = list(self._macros.values())
        if enabled_only:
            macros = [m for m in macros if m.enabled]
        return macros
    
    def update(self, name: str, **updates) -> Optional[MacroDefinition]:
        """Update a macro."""
        if name not in self._macros:
            return None
        
        macro = self._macros[name]
        for key, value in updates.items():
            if hasattr(macro, key):
                setattr(macro, key, value)
        
        macro.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_macro(macro)
        return macro
    
    def delete(self, name: str) -> bool:
        """Delete a macro."""
        if name in self._macros:
            del self._macros[name]
            macro_file = self.storage_path / f"{name}.json"
            if macro_file.exists():
                macro_file.unlink()
            return True
        return False
    
    def export_for_sync(self) -> List[Dict[str, Any]]:
        """Export macros for sync payload."""
        return [asdict(m) for m in self._macros.values()]


# ============================================================================
# Metadata Manager
# ============================================================================

class MetadataManager:
    """
    Manages metadata records for sync.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./.cxflow/metadata")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._metadata: Dict[str, MetadataRecord] = {}
    
    def set(
        self,
        entity_type: str,
        entity_id: str,
        attributes: Dict[str, Any],
        schema_version: str = "1.0",
    ) -> MetadataRecord:
        """Set metadata for an entity."""
        key = f"{entity_type}:{entity_id}"
        record = MetadataRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            attributes=attributes,
            schema_version=schema_version,
        )
        self._metadata[key] = record
        return record
    
    def get(self, entity_type: str, entity_id: str) -> Optional[MetadataRecord]:
        """Get metadata for an entity."""
        return self._metadata.get(f"{entity_type}:{entity_id}")
    
    def list_by_type(self, entity_type: str) -> List[MetadataRecord]:
        """List all metadata for an entity type."""
        return [m for m in self._metadata.values() if m.entity_type == entity_type]
    
    def export_for_sync(self) -> List[Dict[str, Any]]:
        """Export metadata for sync payload."""
        return [asdict(m) for m in self._metadata.values()]


# ============================================================================
# Power Automate Sync Client
# ============================================================================

class PowerAutomateSyncClient:
    """
    Client for syncing data to Power Automate webhook.
    """
    
    def __init__(
        self,
        webhook_url: str = POWER_AUTOMATE_WEBHOOK_URL,
        timeout: int = 60,
        max_retries: int = 3,
        compress_threshold: int = 1024 * 100,  # 100KB
    ):
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.compress_threshold = compress_threshold
        self._sync_history: List[SyncResult] = []
    
    def _generate_sync_id(self) -> str:
        """Generate unique sync ID."""
        timestamp = datetime.now(timezone.utc).isoformat()
        return hashlib.md5(f"{timestamp}-{id(self)}".encode()).hexdigest()[:16]
    
    def _compute_checksum(self, data: Dict) -> str:
        """Compute checksum for data integrity."""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _compress_payload(self, payload: Dict) -> tuple[bytes, bool]:
        """Compress payload if it exceeds threshold."""
        json_str = json.dumps(payload, default=str)
        json_bytes = json_str.encode('utf-8')
        
        if len(json_bytes) > self.compress_threshold:
            compressed = gzip.compress(json_bytes)
            encoded = base64.b64encode(compressed).decode('ascii')
            return json.dumps({
                "compressed": True,
                "encoding": "gzip+base64",
                "data": encoded,
                "original_size": len(json_bytes),
                "compressed_size": len(compressed),
            }).encode('utf-8'), True
        
        return json_bytes, False
    
    async def sync_async(
        self,
        payload: SyncPayload,
        headers: Optional[Dict[str, str]] = None,
    ) -> SyncResult:
        """
        Async sync to Power Automate.
        
        Requires aiohttp to be installed.
        """
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp is required for async sync. Install with: pip install aiohttp")
        
        sync_id = payload.sync_id or self._generate_sync_id()
        start_time = datetime.now(timezone.utc)
        
        result = SyncResult(
            sync_id=sync_id,
            sync_type=SyncType(payload.sync_type),
            status=SyncStatus.IN_PROGRESS,
        )
        
        try:
            # Prepare payload
            payload_dict = payload.model_dump(exclude_none=True)
            payload_dict['checksum'] = self._compute_checksum(payload_dict)
            
            # Compress if needed
            body, compressed = self._compress_payload(payload_dict)
            payload_dict['compressed'] = compressed
            
            # Count items
            result.items_sent = self._count_items(payload_dict)
            
            # Prepare headers
            request_headers = {
                "Content-Type": "application/json",
                "X-Sync-ID": sync_id,
                "X-Sync-Type": payload.sync_type,
                "X-Source": "cxflow",
                "X-Timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if headers:
                request_headers.update(headers)
            
            # Send request with retries
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.webhook_url,
                            data=body if compressed else json.dumps(payload_dict, default=str),
                            headers=request_headers,
                            timeout=aiohttp.ClientTimeout(total=self.timeout),
                        ) as response:
                            response_data = await response.text()
                            
                            if response.status in (200, 201, 202):
                                result.status = SyncStatus.COMPLETED
                                try:
                                    result.response_data = json.loads(response_data)
                                except:
                                    result.response_data = {"raw": response_data}
                                break
                            else:
                                last_error = f"HTTP {response.status}: {response_data}"
                                
                except aiohttp.ClientError as e:
                    last_error = str(e)
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            if result.status != SyncStatus.COMPLETED:
                result.status = SyncStatus.FAILED
                result.errors.append(last_error or "Unknown error")
                result.items_failed = result.items_sent
                result.items_sent = 0
                
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            logger.exception("Sync failed")
        
        # Finalize result
        end_time = datetime.now(timezone.utc)
        result.completed_at = end_time.isoformat()
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        self._sync_history.append(result)
        return result
    
    def sync(
        self,
        payload: SyncPayload,
        headers: Optional[Dict[str, str]] = None,
    ) -> SyncResult:
        """
        Synchronous sync to Power Automate.
        """
        sync_id = payload.sync_id or self._generate_sync_id()
        start_time = datetime.now(timezone.utc)
        
        result = SyncResult(
            sync_id=sync_id,
            sync_type=SyncType(payload.sync_type),
            status=SyncStatus.IN_PROGRESS,
        )
        
        try:
            # Prepare payload
            payload_dict = payload.model_dump(exclude_none=True)
            payload_dict['checksum'] = self._compute_checksum(payload_dict)
            
            # Count items
            result.items_sent = self._count_items(payload_dict)
            
            # Prepare headers
            request_headers = {
                "Content-Type": "application/json",
                "X-Sync-ID": sync_id,
                "X-Sync-Type": payload.sync_type,
                "X-Source": "cxflow",
                "X-Timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if headers:
                request_headers.update(headers)
            
            # Send request with retries
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(
                        self.webhook_url,
                        json=payload_dict,
                        headers=request_headers,
                        timeout=self.timeout,
                    )
                    
                    if response.status_code in (200, 201, 202):
                        result.status = SyncStatus.COMPLETED
                        try:
                            result.response_data = response.json()
                        except:
                            result.response_data = {"raw": response.text}
                        break
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        
                except requests.RequestException as e:
                    last_error = str(e)
                    import time
                    time.sleep(2 ** attempt)
            
            if result.status != SyncStatus.COMPLETED:
                result.status = SyncStatus.FAILED
                result.errors.append(last_error or "Unknown error")
                result.items_failed = result.items_sent
                result.items_sent = 0
                
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            logger.exception("Sync failed")
        
        # Finalize result
        end_time = datetime.now(timezone.utc)
        result.completed_at = end_time.isoformat()
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        self._sync_history.append(result)
        return result
    
    def _count_items(self, payload: Dict) -> int:
        """Count total items in payload."""
        count = 0
        for key in ['memory', 'macros', 'metadata', 'logs', 'events']:
            if key in payload and payload[key]:
                count += len(payload[key])
        if 'data' in payload and payload['data']:
            records = payload['data'].get('records', [])
            count += len(records) if isinstance(records, list) else 1
        return count
    
    def get_sync_history(self, limit: int = 100) -> List[SyncResult]:
        """Get recent sync history."""
        return self._sync_history[-limit:]


# ============================================================================
# Comprehensive Sync Workflow
# ============================================================================

class CXFlowSyncWorkflow:
    """
    Comprehensive workflow for syncing all CXFlow data to Power Automate.
    """
    
    def __init__(
        self,
        webhook_url: str = POWER_AUTOMATE_WEBHOOK_URL,
        base_path: Path = Path("./.cxflow"),
    ):
        self.webhook_url = webhook_url
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.memory = MemoryManager(base_path / "memory")
        self.macros = MacroManager(base_path / "macros")
        self.metadata = MetadataManager(base_path / "metadata")
        
        # Initialize sync client
        self.client = PowerAutomateSyncClient(webhook_url)
        
        # Event hooks
        self._pre_sync_hooks: List[Callable] = []
        self._post_sync_hooks: List[Callable] = []
    
    def add_pre_sync_hook(self, hook: Callable):
        """Add a pre-sync hook."""
        self._pre_sync_hooks.append(hook)
    
    def add_post_sync_hook(self, hook: Callable):
        """Add a post-sync hook."""
        self._post_sync_hooks.append(hook)
    
    def _run_hooks(self, hooks: List[Callable], context: Dict):
        """Run hooks with context."""
        for hook in hooks:
            try:
                hook(context)
            except Exception as e:
                logger.warning(f"Hook failed: {e}")
    
    def collect_system_info(self) -> Dict[str, Any]:
        """Collect system information."""
        import platform
        import socket
        
        return {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics."""
        try:
            import psutil
            
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "process_count": len(psutil.pids()),
            }
        except ImportError:
            return {}
    
    def collect_config(self) -> Dict[str, Any]:
        """Collect configuration data."""
        config = {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "version": "1.0.0",
            "features": {},
        }
        
        # Load from config file if exists
        config_file = self.base_path / "config.json"
        if config_file.exists():
            try:
                config.update(json.loads(config_file.read_text()))
            except:
                pass
        
        return config
    
    def collect_logs(self, max_entries: int = 100) -> List[Dict[str, Any]]:
        """Collect recent log entries."""
        logs = []
        log_file = self.base_path / "logs" / "app.log"
        
        if log_file.exists():
            try:
                lines = log_file.read_text().split('\n')[-max_entries:]
                for line in lines:
                    if line.strip():
                        logs.append({
                            "message": line,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
            except:
                pass
        
        return logs
    
    def collect_events(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Collect events for sync."""
        events = []
        events_file = self.base_path / "events.json"
        
        if events_file.exists():
            try:
                all_events = json.loads(events_file.read_text())
                if since:
                    events = [
                        e for e in all_events
                        if datetime.fromisoformat(e.get('timestamp', '')) > since
                    ]
                else:
                    events = all_events
            except:
                pass
        
        return events
    
    def record_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str = "cxflow",
    ):
        """Record an event."""
        events_file = self.base_path / "events.json"
        
        events = []
        if events_file.exists():
            try:
                events = json.loads(events_file.read_text())
            except:
                pass
        
        events.append({
            "type": event_type,
            "data": data,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Keep last 1000 events
        events = events[-1000:]
        events_file.write_text(json.dumps(events, indent=2, default=str))
    
    async def sync_all_async(
        self,
        include_metrics: bool = True,
        include_logs: bool = False,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Async full sync of all data to Power Automate.
        """
        sync_id = hashlib.md5(
            datetime.now(timezone.utc).isoformat().encode()
        ).hexdigest()[:16]
        
        context = {"sync_id": sync_id, "sync_type": "full"}
        self._run_hooks(self._pre_sync_hooks, context)
        
        # Build payload
        payload = SyncPayload(
            sync_id=sync_id,
            sync_type=SyncType.FULL.value,
            memory=self.memory.export_for_sync(),
            macros=self.macros.export_for_sync(),
            metadata=self.metadata.export_for_sync(),
            config=self.collect_config(),
            events=self.collect_events(),
        )
        
        if include_metrics:
            payload.metrics = self.collect_metrics()
        
        if include_logs:
            payload.logs = self.collect_logs()
        
        if custom_data:
            payload.data = custom_data
        
        # Add system info
        payload.batch_info = {
            "system": self.collect_system_info(),
            "item_counts": {
                "memory": len(payload.memory or []),
                "macros": len(payload.macros or []),
                "metadata": len(payload.metadata or []),
                "events": len(payload.events or []),
            },
        }
        
        # Sync
        result = await self.client.sync_async(payload)
        
        # Record sync event
        self.record_event("sync_completed", {
            "sync_id": sync_id,
            "status": result.status.value,
            "items_sent": result.items_sent,
            "duration_ms": result.duration_ms,
        })
        
        context["result"] = result
        self._run_hooks(self._post_sync_hooks, context)
        
        return result
    
    def sync_all(
        self,
        include_metrics: bool = True,
        include_logs: bool = False,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Synchronous full sync of all data to Power Automate.
        """
        sync_id = hashlib.md5(
            datetime.now(timezone.utc).isoformat().encode()
        ).hexdigest()[:16]
        
        context = {"sync_id": sync_id, "sync_type": "full"}
        self._run_hooks(self._pre_sync_hooks, context)
        
        # Build payload
        payload = SyncPayload(
            sync_id=sync_id,
            sync_type=SyncType.FULL.value,
            memory=self.memory.export_for_sync(),
            macros=self.macros.export_for_sync(),
            metadata=self.metadata.export_for_sync(),
            config=self.collect_config(),
            events=self.collect_events(),
        )
        
        if include_metrics:
            payload.metrics = self.collect_metrics()
        
        if include_logs:
            payload.logs = self.collect_logs()
        
        if custom_data:
            payload.data = custom_data
        
        # Add system info
        payload.batch_info = {
            "system": self.collect_system_info(),
            "item_counts": {
                "memory": len(payload.memory or []),
                "macros": len(payload.macros or []),
                "metadata": len(payload.metadata or []),
                "events": len(payload.events or []),
            },
        }
        
        # Sync
        result = self.client.sync(payload)
        
        # Record sync event
        self.record_event("sync_completed", {
            "sync_id": sync_id,
            "status": result.status.value,
            "items_sent": result.items_sent,
            "duration_ms": result.duration_ms,
        })
        
        context["result"] = result
        self._run_hooks(self._post_sync_hooks, context)
        
        return result
    
    def sync_memory(self) -> SyncResult:
        """Sync only memory data."""
        payload = SyncPayload(
            sync_id=self.client._generate_sync_id(),
            sync_type=SyncType.MEMORY.value,
            memory=self.memory.export_for_sync(),
        )
        return self.client.sync(payload)
    
    def sync_macros(self) -> SyncResult:
        """Sync only macro definitions."""
        payload = SyncPayload(
            sync_id=self.client._generate_sync_id(),
            sync_type=SyncType.MACROS.value,
            macros=self.macros.export_for_sync(),
        )
        return self.client.sync(payload)
    
    def sync_metadata(self) -> SyncResult:
        """Sync only metadata."""
        payload = SyncPayload(
            sync_id=self.client._generate_sync_id(),
            sync_type=SyncType.METADATA.value,
            metadata=self.metadata.export_for_sync(),
        )
        return self.client.sync(payload)
    
    def sync_data(self, collection: str, records: List[Dict]) -> SyncResult:
        """Sync arbitrary data collection."""
        payload = SyncPayload(
            sync_id=self.client._generate_sync_id(),
            sync_type=SyncType.DATA.value,
            data={
                "collection": collection,
                "records": records,
                "count": len(records),
            },
        )
        return self.client.sync(payload)
    
    def sync_events(self, events: List[Dict[str, Any]]) -> SyncResult:
        """Sync events."""
        payload = SyncPayload(
            sync_id=self.client._generate_sync_id(),
            sync_type=SyncType.EVENTS.value,
            events=events,
        )
        return self.client.sync(payload)


# ============================================================================
# Convenience Functions
# ============================================================================

_default_workflow: Optional[CXFlowSyncWorkflow] = None


def get_workflow() -> CXFlowSyncWorkflow:
    """Get or create default workflow instance."""
    global _default_workflow
    if _default_workflow is None:
        _default_workflow = CXFlowSyncWorkflow()
    return _default_workflow


def sync_to_power_automate(
    data: Optional[Dict[str, Any]] = None,
    include_memory: bool = True,
    include_macros: bool = True,
    include_metadata: bool = True,
    include_metrics: bool = True,
    include_logs: bool = False,
) -> SyncResult:
    """
    Quick sync to Power Automate.
    
    Args:
        data: Custom data to include
        include_memory: Include memory entries
        include_macros: Include macro definitions
        include_metadata: Include metadata
        include_metrics: Include system metrics
        include_logs: Include recent logs
        
    Returns:
        SyncResult with status and details
    """
    workflow = get_workflow()
    return workflow.sync_all(
        include_metrics=include_metrics,
        include_logs=include_logs,
        custom_data=data,
    )


async def sync_to_power_automate_async(
    data: Optional[Dict[str, Any]] = None,
    include_metrics: bool = True,
    include_logs: bool = False,
) -> SyncResult:
    """Async version of sync_to_power_automate."""
    workflow = get_workflow()
    return await workflow.sync_all_async(
        include_metrics=include_metrics,
        include_logs=include_logs,
        custom_data=data,
    )


def set_memory(key: str, value: Any, **kwargs) -> MemoryEntry:
    """Set a memory entry."""
    return get_workflow().memory.set(key, value, **kwargs)


def get_memory(key: str) -> Optional[Any]:
    """Get a memory value."""
    entry = get_workflow().memory.get(key)
    return entry.value if entry else None


def register_macro(name: str, description: str, trigger: str, actions: List[Dict]) -> MacroDefinition:
    """Register a macro."""
    return get_workflow().macros.register(name, description, trigger, actions)


def set_metadata(entity_type: str, entity_id: str, attributes: Dict) -> MetadataRecord:
    """Set metadata for an entity."""
    return get_workflow().metadata.set(entity_type, entity_id, attributes)


def record_event(event_type: str, data: Dict[str, Any]):
    """Record an event."""
    get_workflow().record_event(event_type, data)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="CXFlow Power Automate Sync")
    subparsers = parser.add_subparsers(dest="command")
    
    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync all data")
    sync_parser.add_argument("--include-logs", action="store_true")
    sync_parser.add_argument("--no-metrics", action="store_true")
    
    # memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_parser.add_argument("action", choices=["set", "get", "list", "sync"])
    memory_parser.add_argument("--key", help="Memory key")
    memory_parser.add_argument("--value", help="Memory value")
    
    # macro commands
    macro_parser = subparsers.add_parser("macro", help="Macro operations")
    macro_parser.add_argument("action", choices=["list", "sync"])
    
    # status command
    status_parser = subparsers.add_parser("status", help="Show sync status")
    
    args = parser.parse_args()
    
    workflow = CXFlowSyncWorkflow()
    
    if args.command == "sync":
        print("🔄 Starting full sync to Power Automate...")
        result = workflow.sync_all(
            include_metrics=not args.no_metrics,
            include_logs=args.include_logs,
        )
        
        if result.status == SyncStatus.COMPLETED:
            print(f"✅ Sync completed successfully!")
            print(f"   Items sent: {result.items_sent}")
            print(f"   Duration: {result.duration_ms}ms")
        else:
            print(f"❌ Sync failed: {result.errors}")
    
    elif args.command == "memory":
        if args.action == "set" and args.key and args.value:
            entry = workflow.memory.set(args.key, args.value)
            print(f"✅ Set memory: {args.key}")
        elif args.action == "get" and args.key:
            entry = workflow.memory.get(args.key)
            if entry:
                print(f"{args.key}: {entry.value}")
            else:
                print(f"Key not found: {args.key}")
        elif args.action == "list":
            entries = workflow.memory.get_all()
            for e in entries:
                print(f"  {e.key}: {e.value}")
        elif args.action == "sync":
            result = workflow.sync_memory()
            print(f"Memory sync: {result.status.value}")
    
    elif args.command == "macro":
        if args.action == "list":
            macros = workflow.macros.list_all()
            for m in macros:
                status = "✅" if m.enabled else "⏸️"
                print(f"  {status} {m.name}: {m.description}")
        elif args.action == "sync":
            result = workflow.sync_macros()
            print(f"Macro sync: {result.status.value}")
    
    elif args.command == "status":
        history = workflow.client.get_sync_history(10)
        if history:
            print("Recent syncs:")
            for r in history:
                status = "✅" if r.status == SyncStatus.COMPLETED else "❌"
                print(f"  {status} {r.sync_id} ({r.sync_type.value}) - {r.items_sent} items")
        else:
            print("No sync history")
    
    else:
        parser.print_help()
