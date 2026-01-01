"""
Dataset management for Apache Superset.

Provides dataset and column management:
- Dataset CRUD operations
- Column configuration
- Metric definitions
- Virtual datasets (SQL-based)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


class ColumnType(Enum):
    """Column data types."""
    STRING = "STRING"
    NUMERIC = "NUMERIC"
    TEMPORAL = "TEMPORAL"
    BOOLEAN = "BOOLEAN"


@dataclass
class Column:
    """Represents a dataset column."""
    id: Optional[int] = None
    name: str = ""
    type: str = ""
    column_type: Optional[ColumnType] = None
    
    # Flags
    is_temporal: bool = False
    is_filterable: bool = True
    is_groupby: bool = True
    is_active: bool = True
    
    # Metadata
    description: Optional[str] = None
    verbose_name: Optional[str] = None
    expression: Optional[str] = None
    python_date_format: Optional[str] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Column:
        """Create from API response."""
        return cls(
            id=data.get("id"),
            name=data.get("column_name", ""),
            type=data.get("type", ""),
            is_temporal=data.get("is_dttm", False),
            is_filterable=data.get("filterable", True),
            is_groupby=data.get("groupby", True),
            is_active=data.get("is_active", True),
            description=data.get("description"),
            verbose_name=data.get("verbose_name"),
            expression=data.get("expression"),
            python_date_format=data.get("python_date_format"),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        return {
            "column_name": self.name,
            "type": self.type,
            "is_dttm": self.is_temporal,
            "filterable": self.is_filterable,
            "groupby": self.is_groupby,
            "is_active": self.is_active,
            "description": self.description,
            "verbose_name": self.verbose_name,
            "expression": self.expression,
            "python_date_format": self.python_date_format,
        }


@dataclass
class Metric:
    """Represents a dataset metric."""
    id: Optional[int] = None
    name: str = ""
    expression: str = ""
    metric_type: str = "count"
    
    # Metadata
    description: Optional[str] = None
    verbose_name: Optional[str] = None
    d3format: Optional[str] = None
    warning_text: Optional[str] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Metric:
        """Create from API response."""
        return cls(
            id=data.get("id"),
            name=data.get("metric_name", ""),
            expression=data.get("expression", ""),
            metric_type=data.get("metric_type", ""),
            description=data.get("description"),
            verbose_name=data.get("verbose_name"),
            d3format=data.get("d3format"),
            warning_text=data.get("warning_text"),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        return {
            "metric_name": self.name,
            "expression": self.expression,
            "metric_type": self.metric_type,
            "description": self.description,
            "verbose_name": self.verbose_name,
            "d3format": self.d3format,
            "warning_text": self.warning_text,
        }


@dataclass
class Dataset:
    """Represents a Superset dataset (table)."""
    id: int
    name: str
    table_name: str
    database_id: int
    database_name: Optional[str] = None
    schema: Optional[str] = None
    
    # SQL for virtual datasets
    sql: Optional[str] = None
    is_sqllab_view: bool = False
    
    # Columns and metrics
    columns: List[Column] = field(default_factory=list)
    metrics: List[Metric] = field(default_factory=list)
    
    # Time settings
    main_dttm_col: Optional[str] = None
    offset: int = 0
    
    # Settings
    cache_timeout: Optional[int] = None
    default_endpoint: Optional[str] = None
    description: Optional[str] = None
    
    # Metadata
    created_by: Optional[str] = None
    created_on: Optional[datetime] = None
    changed_by: Optional[str] = None
    changed_on: Optional[datetime] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Dataset:
        """Create from API response."""
        result = data.get("result", data)
        
        columns = [Column.from_api(c) for c in result.get("columns", [])]
        metrics = [Metric.from_api(m) for m in result.get("metrics", [])]
        
        return cls(
            id=result.get("id", 0),
            name=result.get("table_name", ""),
            table_name=result.get("table_name", ""),
            database_id=result.get("database", {}).get("id", 0) if isinstance(result.get("database"), dict) else result.get("database", 0),
            database_name=result.get("database", {}).get("database_name") if isinstance(result.get("database"), dict) else None,
            schema=result.get("schema"),
            sql=result.get("sql"),
            is_sqllab_view=result.get("is_sqllab_view", False),
            columns=columns,
            metrics=metrics,
            main_dttm_col=result.get("main_dttm_col"),
            offset=result.get("offset", 0),
            cache_timeout=result.get("cache_timeout"),
            description=result.get("description"),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        return {
            "table_name": self.table_name,
            "database": self.database_id,
            "schema": self.schema,
            "sql": self.sql,
            "is_sqllab_view": self.is_sqllab_view,
            "main_dttm_col": self.main_dttm_col,
            "offset": self.offset,
            "cache_timeout": self.cache_timeout,
            "description": self.description,
        }
    
    def get_temporal_columns(self) -> List[Column]:
        """Get all temporal columns."""
        return [c for c in self.columns if c.is_temporal]
    
    def get_metric_by_name(self, name: str) -> Optional[Metric]:
        """Get metric by name."""
        for metric in self.metrics:
            if metric.name == name:
                return metric
        return None


class DatasetManager:
    """
    High-level dataset management.
    
    Usage:
        manager = DatasetManager(client)
        
        # List datasets
        datasets = manager.list_datasets()
        
        # Create physical dataset
        dataset = manager.create_physical_dataset(
            database_id=1,
            table_name="sales",
            schema="public",
        )
        
        # Create virtual dataset
        virtual = manager.create_virtual_dataset(
            database_id=1,
            name="sales_summary",
            sql="SELECT category, SUM(amount) as total FROM sales GROUP BY category",
        )
        
        # Add metric
        manager.add_metric(dataset.id, "total_sales", "SUM(amount)")
    """
    
    def __init__(self, client: SupersetClient):
        self.client = client
    
    def list_datasets(
        self,
        page: int = 0,
        page_size: int = 100,
        database_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dataset]:
        """List all datasets."""
        filters = []
        
        if database_id:
            filters.append({"col": "database", "opr": "rel_o_m", "value": database_id})
        
        if search:
            filters.append({"col": "table_name", "opr": "ct", "value": search})
        
        result = self.client.get_datasets(
            page=page,
            page_size=page_size,
            filters=filters,
        )
        
        datasets = []
        for item in result.get("result", []):
            datasets.append(Dataset.from_api({"result": item}))
        
        return datasets
    
    def get_dataset(self, dataset_id: int) -> Dataset:
        """Get dataset by ID."""
        result = self.client.get_dataset(dataset_id)
        return Dataset.from_api(result)
    
    def create_physical_dataset(
        self,
        database_id: int,
        table_name: str,
        schema: Optional[str] = None,
    ) -> Dataset:
        """Create a physical dataset from a database table."""
        dataset_data = {
            "database": database_id,
            "table_name": table_name,
            "schema": schema,
        }
        
        result = self.client.create_dataset(dataset_data)
        return self.get_dataset(result.get("id"))
    
    def create_virtual_dataset(
        self,
        database_id: int,
        name: str,
        sql: str,
        schema: Optional[str] = None,
    ) -> Dataset:
        """Create a virtual dataset from SQL query."""
        dataset_data = {
            "database": database_id,
            "table_name": name,
            "sql": sql,
            "schema": schema,
            "is_sqllab_view": True,
        }
        
        result = self.client.create_dataset(dataset_data)
        return self.get_dataset(result.get("id"))
    
    def update_dataset(
        self,
        dataset_id: int,
        **kwargs,
    ) -> Dataset:
        """Update an existing dataset."""
        self.client.update_dataset(dataset_id, kwargs)
        return self.get_dataset(dataset_id)
    
    def delete_dataset(self, dataset_id: int) -> bool:
        """Delete a dataset."""
        try:
            self.client.delete_dataset(dataset_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete dataset {dataset_id}: {e}")
            return False
    
    def refresh_columns(self, dataset_id: int) -> Dataset:
        """Refresh dataset columns from source."""
        self.client.refresh_dataset(dataset_id)
        return self.get_dataset(dataset_id)
    
    def add_column(
        self,
        dataset_id: int,
        column: Column,
    ) -> Dataset:
        """Add a calculated column to dataset."""
        dataset = self.get_dataset(dataset_id)
        
        columns = [c.to_api_payload() for c in dataset.columns]
        columns.append(column.to_api_payload())
        
        self.client.update_dataset(dataset_id, {"columns": columns})
        return self.get_dataset(dataset_id)
    
    def add_metric(
        self,
        dataset_id: int,
        name: str,
        expression: str,
        metric_type: str = "count",
        description: Optional[str] = None,
        d3format: Optional[str] = None,
    ) -> Dataset:
        """Add a metric to dataset."""
        dataset = self.get_dataset(dataset_id)
        
        metrics = [m.to_api_payload() for m in dataset.metrics]
        metrics.append({
            "metric_name": name,
            "expression": expression,
            "metric_type": metric_type,
            "description": description,
            "d3format": d3format,
        })
        
        self.client.update_dataset(dataset_id, {"metrics": metrics})
        return self.get_dataset(dataset_id)
    
    def remove_metric(
        self,
        dataset_id: int,
        metric_name: str,
    ) -> Dataset:
        """Remove a metric from dataset."""
        dataset = self.get_dataset(dataset_id)
        
        metrics = [
            m.to_api_payload()
            for m in dataset.metrics
            if m.name != metric_name
        ]
        
        self.client.update_dataset(dataset_id, {"metrics": metrics})
        return self.get_dataset(dataset_id)
    
    def set_main_temporal_column(
        self,
        dataset_id: int,
        column_name: str,
    ) -> Dataset:
        """Set the main temporal column for time-series charts."""
        return self.update_dataset(dataset_id, main_dttm_col=column_name)
    
    def set_cache_timeout(
        self,
        dataset_id: int,
        timeout: int,
    ) -> Dataset:
        """Set dataset cache timeout in seconds."""
        return self.update_dataset(dataset_id, cache_timeout=timeout)
    
    def get_columns(self, dataset_id: int) -> List[Column]:
        """Get all columns for a dataset."""
        dataset = self.get_dataset(dataset_id)
        return dataset.columns
    
    def get_metrics(self, dataset_id: int) -> List[Metric]:
        """Get all metrics for a dataset."""
        dataset = self.get_dataset(dataset_id)
        return dataset.metrics
