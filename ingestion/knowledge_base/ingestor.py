"""
Knowledge Base Ingestor - Processes and stores data from Power Automate.
"""

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

from .client import PowerAutomateClient, IngestionResponse
from .config import IngestionConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    success: bool
    items_processed: int
    items_stored: int
    items_failed: int
    duration_seconds: float
    errors: List[str] = field(default_factory=list)
    file_paths: List[Path] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "items_processed": self.items_processed,
            "items_stored": self.items_stored,
            "items_failed": self.items_failed,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "file_paths": [str(p) for p in self.file_paths],
        }


class KnowledgeBaseIngestor:
    """
    Ingests data from Power Automate into the knowledge base.
    
    Usage:
        ingestor = KnowledgeBaseIngestor()
        
        # Run ingestion
        result = ingestor.ingest()
        
        print(f"Processed {result.items_processed} items")
        print(f"Stored {result.items_stored} items")
        
        # Run with custom transformer
        result = ingestor.ingest(
            transformer=lambda item: {
                "id": item["Id"],
                "content": item["Content"],
                "metadata": item.get("Metadata", {}),
            }
        )
        
        # Scheduled ingestion
        ingestor.run_scheduled(interval_minutes=60)
    """
    
    def __init__(
        self,
        config: Optional[IngestionConfig] = None,
        client: Optional[PowerAutomateClient] = None,
    ):
        self.config = config or DEFAULT_CONFIG
        self.client = client or PowerAutomateClient(self.config)
        self._setup_storage()
    
    def _setup_storage(self) -> None:
        """Set up storage directories."""
        self.config.ensure_storage_path()
        
        # Create subdirectories
        (self.config.storage_path / "raw").mkdir(exist_ok=True)
        (self.config.storage_path / "processed").mkdir(exist_ok=True)
        (self.config.storage_path / "failed").mkdir(exist_ok=True)
        (self.config.storage_path / "logs").mkdir(exist_ok=True)
    
    def _generate_id(self, item: Any) -> str:
        """Generate unique ID for an item."""
        if isinstance(item, dict):
            # Try to use existing ID
            for key in ("id", "Id", "ID", "_id", "uuid", "guid"):
                if key in item:
                    return str(item[key])
        
        # Generate hash-based ID
        content = json.dumps(item, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _validate_item(self, item: Any) -> bool:
        """Validate an item before storage."""
        if item is None:
            return False
        
        if isinstance(item, dict):
            return len(item) > 0
        
        return True
    
    def _store_item(
        self,
        item: Any,
        item_id: str,
        subdirectory: str = "processed",
    ) -> Path:
        """Store a single item to disk."""
        directory = self.config.storage_path / subdirectory
        file_path = directory / f"{item_id}.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(item, f, indent=2, default=str, ensure_ascii=False)
        
        return file_path
    
    def _store_raw_response(self, response: IngestionResponse) -> Path:
        """Store raw response for debugging."""
        timestamp = response.timestamp.strftime("%Y%m%d_%H%M%S")
        file_path = self.config.storage_path / "raw" / f"response_{timestamp}.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(response.to_dict(), f, indent=2, default=str)
        
        return file_path
    
    def _extract_items(self, data: Any) -> List[Any]:
        """Extract items from response data."""
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            # Common response formats
            for key in ("items", "value", "data", "results", "records"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            
            # Single item response
            return [data]
        
        return [data] if data else []
    
    def ingest(
        self,
        payload: Optional[Dict[str, Any]] = None,
        transformer: Optional[Callable[[Any], Any]] = None,
        validator: Optional[Callable[[Any], bool]] = None,
    ) -> IngestionResult:
        """
        Run the ingestion process.
        
        Args:
            payload: Optional payload to send with request
            transformer: Optional function to transform items
            validator: Optional function to validate items
            
        Returns:
            IngestionResult with processing statistics
        """
        start_time = datetime.now()
        
        items_processed = 0
        items_stored = 0
        items_failed = 0
        errors: List[str] = []
        file_paths: List[Path] = []
        
        logger.info("Starting knowledge base ingestion")
        
        # Fetch data from Power Automate
        response = self.client.fetch(payload=payload)
        
        if not response.success:
            logger.error(f"Failed to fetch data: {response.error_message}")
            return IngestionResult(
                success=False,
                items_processed=0,
                items_stored=0,
                items_failed=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[response.error_message or "Unknown error"],
            )
        
        # Store raw response
        raw_path = self._store_raw_response(response)
        file_paths.append(raw_path)
        
        # Extract items
        items = self._extract_items(response.data)
        logger.info(f"Extracted {len(items)} items from response")
        
        # Process items
        for item in items:
            items_processed += 1
            
            try:
                # Transform if needed
                if transformer:
                    item = transformer(item)
                
                # Validate
                validate_fn = validator or self._validate_item
                if self.config.validate_data and not validate_fn(item):
                    logger.warning(f"Item failed validation: {item}")
                    items_failed += 1
                    continue
                
                # Generate ID and store
                item_id = self._generate_id(item)
                file_path = self._store_item(item, item_id)
                file_paths.append(file_path)
                items_stored += 1
                
            except Exception as e:
                error_msg = f"Error processing item: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                items_failed += 1
                
                # Store failed item for debugging
                try:
                    item_id = self._generate_id(item)
                    self._store_item(
                        {"item": item, "error": str(e)},
                        f"failed_{item_id}",
                        subdirectory="failed",
                    )
                except Exception:
                    pass
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log summary
        logger.info(
            f"Ingestion complete: {items_processed} processed, "
            f"{items_stored} stored, {items_failed} failed "
            f"({duration:.2f}s)"
        )
        
        # Store ingestion log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "items_processed": items_processed,
            "items_stored": items_stored,
            "items_failed": items_failed,
            "duration_seconds": duration,
            "errors": errors,
        }
        
        log_path = self.config.storage_path / "logs" / f"ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_path, "w") as f:
            json.dump(log_entry, f, indent=2)
        
        return IngestionResult(
            success=items_failed == 0,
            items_processed=items_processed,
            items_stored=items_stored,
            items_failed=items_failed,
            duration_seconds=duration,
            errors=errors,
            file_paths=file_paths,
        )
    
    def ingest_all(
        self,
        page_size: int = 100,
        max_pages: Optional[int] = None,
        transformer: Optional[Callable[[Any], Any]] = None,
    ) -> IngestionResult:
        """
        Ingest all available data with pagination.
        
        Args:
            page_size: Number of items per page
            max_pages: Maximum pages to fetch (None for all)
            transformer: Optional transform function
            
        Returns:
            Combined IngestionResult
        """
        start_time = datetime.now()
        
        total_processed = 0
        total_stored = 0
        total_failed = 0
        all_errors: List[str] = []
        all_paths: List[Path] = []
        
        responses = self.client.fetch_with_pagination(
            page_size=page_size,
            max_pages=max_pages,
        )
        
        for response in responses:
            if response.success:
                items = self._extract_items(response.data)
                
                for item in items:
                    total_processed += 1
                    
                    try:
                        if transformer:
                            item = transformer(item)
                        
                        if self._validate_item(item):
                            item_id = self._generate_id(item)
                            path = self._store_item(item, item_id)
                            all_paths.append(path)
                            total_stored += 1
                        else:
                            total_failed += 1
                            
                    except Exception as e:
                        total_failed += 1
                        all_errors.append(str(e))
            else:
                all_errors.append(response.error_message or "Unknown error")
        
        return IngestionResult(
            success=total_failed == 0 and len(all_errors) == 0,
            items_processed=total_processed,
            items_stored=total_stored,
            items_failed=total_failed,
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            errors=all_errors,
            file_paths=all_paths,
        )
    
    def get_stored_items(self) -> List[Dict[str, Any]]:
        """Get all stored items from the knowledge base."""
        items = []
        processed_dir = self.config.storage_path / "processed"
        
        for file_path in processed_dir.glob("*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                items.append(json.load(f))
        
        return items
    
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific item by ID."""
        file_path = self.config.storage_path / "processed" / f"{item_id}.json"
        
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None
    
    def clear_storage(self, include_logs: bool = False) -> int:
        """Clear stored items. Returns number of files deleted."""
        count = 0
        
        for subdir in ["raw", "processed", "failed"]:
            directory = self.config.storage_path / subdir
            for file_path in directory.glob("*.json"):
                file_path.unlink()
                count += 1
        
        if include_logs:
            logs_dir = self.config.storage_path / "logs"
            for file_path in logs_dir.glob("*.json"):
                file_path.unlink()
                count += 1
        
        return count
