"""
Dashboard management for Apache Superset.

Provides high-level dashboard operations:
- Dashboard CRUD operations
- Chart management within dashboards
- Layout management
- Publishing and sharing
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


@dataclass
class Chart:
    """Represents a Superset chart/slice."""
    id: int
    name: str
    viz_type: str
    dataset_id: Optional[int] = None
    description: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    cache_timeout: Optional[int] = None
    created_by: Optional[str] = None
    created_on: Optional[datetime] = None
    changed_on: Optional[datetime] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Chart:
        """Create from API response."""
        return cls(
            id=data.get("id", 0),
            name=data.get("slice_name", ""),
            viz_type=data.get("viz_type", ""),
            dataset_id=data.get("datasource_id"),
            description=data.get("description"),
            params=json.loads(data.get("params", "{}")) if isinstance(data.get("params"), str) else data.get("params", {}),
            cache_timeout=data.get("cache_timeout"),
            created_by=data.get("created_by", {}).get("username") if isinstance(data.get("created_by"), dict) else None,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "viz_type": self.viz_type,
            "dataset_id": self.dataset_id,
            "description": self.description,
            "cache_timeout": self.cache_timeout,
        }


@dataclass
class DashboardFilter:
    """Dashboard native filter configuration."""
    id: str
    name: str
    filter_type: str
    targets: List[Dict[str, Any]] = field(default_factory=list)
    default_value: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "filterType": self.filter_type,
            "targets": self.targets,
            "defaultDataMask": {"filterState": {"value": self.default_value}} if self.default_value else {},
        }


@dataclass
class Dashboard:
    """Represents a Superset dashboard."""
    id: int
    title: str
    slug: Optional[str] = None
    url: Optional[str] = None
    published: bool = False
    
    # Metadata
    description: Optional[str] = None
    certified_by: Optional[str] = None
    certification_details: Optional[str] = None
    
    # Content
    charts: List[Chart] = field(default_factory=list)
    position_json: Dict[str, Any] = field(default_factory=dict)
    json_metadata: Dict[str, Any] = field(default_factory=dict)
    css: Optional[str] = None
    
    # Access control
    owners: List[int] = field(default_factory=list)
    roles: List[int] = field(default_factory=list)
    
    # Timestamps
    created_by: Optional[str] = None
    created_on: Optional[datetime] = None
    changed_by: Optional[str] = None
    changed_on: Optional[datetime] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Dashboard:
        """Create from API response."""
        result = data.get("result", data)
        
        charts = []
        for chart_data in result.get("slices", []):
            charts.append(Chart.from_api(chart_data))
        
        return cls(
            id=result.get("id", 0),
            title=result.get("dashboard_title", ""),
            slug=result.get("slug"),
            url=result.get("url"),
            published=result.get("published", False),
            description=result.get("description"),
            certified_by=result.get("certified_by"),
            certification_details=result.get("certification_details"),
            charts=charts,
            position_json=json.loads(result.get("position_json", "{}")) if isinstance(result.get("position_json"), str) else result.get("position_json", {}),
            json_metadata=json.loads(result.get("json_metadata", "{}")) if isinstance(result.get("json_metadata"), str) else result.get("json_metadata", {}),
            css=result.get("css"),
            owners=[o.get("id") for o in result.get("owners", []) if isinstance(o, dict)],
            roles=[r.get("id") for r in result.get("roles", []) if isinstance(r, dict)],
            created_by=result.get("created_by", {}).get("username") if isinstance(result.get("created_by"), dict) else None,
            changed_by=result.get("changed_by", {}).get("username") if isinstance(result.get("changed_by"), dict) else None,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "published": self.published,
            "charts": [c.to_dict() for c in self.charts],
            "owners": self.owners,
        }
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload for create/update."""
        return {
            "dashboard_title": self.title,
            "slug": self.slug,
            "published": self.published,
            "certified_by": self.certified_by,
            "certification_details": self.certification_details,
            "css": self.css,
            "json_metadata": json.dumps(self.json_metadata),
            "position_json": json.dumps(self.position_json),
            "owners": self.owners,
            "roles": self.roles,
        }


class DashboardManager:
    """
    High-level dashboard management.
    
    Usage:
        manager = DashboardManager(client)
        
        # List all dashboards
        dashboards = manager.list_dashboards()
        
        # Get specific dashboard
        dashboard = manager.get_dashboard(1)
        
        # Create dashboard
        new_dashboard = manager.create_dashboard(
            title="Sales Overview",
            charts=[chart1, chart2],
        )
        
        # Clone dashboard
        cloned = manager.clone_dashboard(1, "Sales Overview - Copy")
    """
    
    def __init__(self, client: SupersetClient):
        self.client = client
    
    def list_dashboards(
        self,
        page: int = 0,
        page_size: int = 100,
        published_only: bool = False,
        search: Optional[str] = None,
    ) -> List[Dashboard]:
        """List all dashboards."""
        filters = []
        
        if published_only:
            filters.append({"col": "published", "opr": "eq", "value": True})
        
        if search:
            filters.append({"col": "dashboard_title", "opr": "ct", "value": search})
        
        result = self.client.get_dashboards(
            page=page,
            page_size=page_size,
            filters=filters,
        )
        
        dashboards = []
        for item in result.get("result", []):
            dashboards.append(Dashboard.from_api({"result": item}))
        
        return dashboards
    
    def get_dashboard(self, dashboard_id: int) -> Dashboard:
        """Get dashboard by ID."""
        result = self.client.get_dashboard(dashboard_id)
        return Dashboard.from_api(result)
    
    def get_dashboard_by_slug(self, slug: str) -> Optional[Dashboard]:
        """Get dashboard by slug."""
        result = self.client.get_dashboards(
            filters=[{"col": "slug", "opr": "eq", "value": slug}]
        )
        
        items = result.get("result", [])
        if items:
            return self.get_dashboard(items[0]["id"])
        return None
    
    def create_dashboard(
        self,
        title: str,
        slug: Optional[str] = None,
        charts: Optional[List[int]] = None,
        published: bool = False,
        owners: Optional[List[int]] = None,
    ) -> Dashboard:
        """Create a new dashboard."""
        dashboard_data = {
            "dashboard_title": title,
            "slug": slug,
            "published": published,
            "owners": owners or [],
        }
        
        result = self.client.create_dashboard(dashboard_data)
        dashboard_id = result.get("id")
        
        # Add charts if specified
        if charts and dashboard_id:
            # Update with charts
            self._add_charts_to_dashboard(dashboard_id, charts)
        
        return self.get_dashboard(dashboard_id)
    
    def update_dashboard(
        self,
        dashboard_id: int,
        title: Optional[str] = None,
        slug: Optional[str] = None,
        published: Optional[bool] = None,
        json_metadata: Optional[Dict] = None,
        position_json: Optional[Dict] = None,
    ) -> Dashboard:
        """Update an existing dashboard."""
        dashboard_data = {}
        
        if title is not None:
            dashboard_data["dashboard_title"] = title
        if slug is not None:
            dashboard_data["slug"] = slug
        if published is not None:
            dashboard_data["published"] = published
        if json_metadata is not None:
            dashboard_data["json_metadata"] = json.dumps(json_metadata)
        if position_json is not None:
            dashboard_data["position_json"] = json.dumps(position_json)
        
        self.client.update_dashboard(dashboard_id, dashboard_data)
        return self.get_dashboard(dashboard_id)
    
    def delete_dashboard(self, dashboard_id: int) -> bool:
        """Delete a dashboard."""
        try:
            self.client.delete_dashboard(dashboard_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete dashboard {dashboard_id}: {e}")
            return False
    
    def clone_dashboard(
        self,
        dashboard_id: int,
        new_title: str,
        new_slug: Optional[str] = None,
    ) -> Dashboard:
        """Clone an existing dashboard."""
        original = self.get_dashboard(dashboard_id)
        
        # Create new dashboard with same settings
        dashboard_data = original.to_api_payload()
        dashboard_data["dashboard_title"] = new_title
        dashboard_data["slug"] = new_slug
        dashboard_data["published"] = False  # Start unpublished
        
        result = self.client.create_dashboard(dashboard_data)
        return self.get_dashboard(result.get("id"))
    
    def publish_dashboard(self, dashboard_id: int) -> Dashboard:
        """Publish a dashboard."""
        return self.update_dashboard(dashboard_id, published=True)
    
    def unpublish_dashboard(self, dashboard_id: int) -> Dashboard:
        """Unpublish a dashboard."""
        return self.update_dashboard(dashboard_id, published=False)
    
    def export_dashboard(self, dashboard_id: int, output_path: str) -> str:
        """Export dashboard to ZIP file."""
        data = self.client.export_dashboards([dashboard_id])
        
        with open(output_path, "wb") as f:
            f.write(data)
        
        return output_path
    
    def import_dashboard(self, zip_path: str, overwrite: bool = False) -> Dict[str, Any]:
        """Import dashboard from ZIP file."""
        with open(zip_path, "rb") as f:
            data = f.read()
        
        return self.client.import_dashboards(data, overwrite=overwrite)
    
    def get_dashboard_charts(self, dashboard_id: int) -> List[Chart]:
        """Get all charts in a dashboard."""
        dashboard = self.get_dashboard(dashboard_id)
        return dashboard.charts
    
    def _add_charts_to_dashboard(
        self,
        dashboard_id: int,
        chart_ids: List[int],
    ) -> None:
        """Add charts to dashboard layout."""
        dashboard = self.get_dashboard(dashboard_id)
        
        # Build position JSON with charts
        position = dashboard.position_json or {}
        
        # Add chart components
        for i, chart_id in enumerate(chart_ids):
            component_id = f"CHART-{chart_id}"
            position[component_id] = {
                "type": "CHART",
                "id": component_id,
                "children": [],
                "meta": {
                    "chartId": chart_id,
                    "width": 4,
                    "height": 50,
                },
            }
        
        self.client.update_dashboard(
            dashboard_id,
            {"position_json": json.dumps(position)}
        )
    
    def add_native_filter(
        self,
        dashboard_id: int,
        filter_config: DashboardFilter,
    ) -> Dashboard:
        """Add a native filter to dashboard."""
        dashboard = self.get_dashboard(dashboard_id)
        
        metadata = dashboard.json_metadata or {}
        native_filter_config = metadata.get("native_filter_configuration", [])
        native_filter_config.append(filter_config.to_dict())
        metadata["native_filter_configuration"] = native_filter_config
        
        return self.update_dashboard(dashboard_id, json_metadata=metadata)
    
    def set_refresh_frequency(
        self,
        dashboard_id: int,
        refresh_frequency: int,  # in seconds, 0 to disable
    ) -> Dashboard:
        """Set dashboard auto-refresh frequency."""
        dashboard = self.get_dashboard(dashboard_id)
        
        metadata = dashboard.json_metadata or {}
        metadata["refresh_frequency"] = refresh_frequency
        
        return self.update_dashboard(dashboard_id, json_metadata=metadata)
    
    def set_color_scheme(
        self,
        dashboard_id: int,
        color_scheme: str,
    ) -> Dashboard:
        """Set dashboard color scheme."""
        dashboard = self.get_dashboard(dashboard_id)
        
        metadata = dashboard.json_metadata or {}
        metadata["color_scheme"] = color_scheme
        
        return self.update_dashboard(dashboard_id, json_metadata=metadata)
