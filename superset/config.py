"""
Configuration management for Apache Superset integration.

Provides configuration classes for:
- Superset connection settings
- Database connections
- Dataset definitions
- Security settings
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DatabaseEngine(Enum):
    """Supported database engines."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"
    SQLITE = "sqlite"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"
    CLICKHOUSE = "clickhouse"
    TRINO = "trino"
    PRESTO = "presto"
    DRUID = "druid"
    ELASTICSEARCH = "elasticsearch"


class VizType(Enum):
    """Chart visualization types."""
    TABLE = "table"
    BIG_NUMBER = "big_number"
    BIG_NUMBER_TOTAL = "big_number_total"
    LINE = "echarts_timeseries_line"
    BAR = "echarts_timeseries_bar"
    AREA = "echarts_area"
    SCATTER = "echarts_scatter"
    PIE = "pie"
    DONUT = "donut"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    GAUGE = "gauge_chart"
    FUNNEL = "funnel"
    SANKEY = "sankey"
    WORD_CLOUD = "word_cloud"
    MAP = "deck_geojson"
    CHOROPLETH = "choropleth"
    PIVOT_TABLE = "pivot_table_v2"


@dataclass
class SupersetConfig:
    """
    Configuration for Superset connection.
    
    Usage:
        config = SupersetConfig.from_env()
        # or
        config = SupersetConfig(
            base_url="http://localhost:8088",
            username="admin",
            password="admin",
        )
    """
    base_url: str = "http://localhost:8088"
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3
    
    # OAuth2 settings
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_token_url: Optional[str] = None
    
    # Advanced settings
    csrf_enabled: bool = True
    session_cookie_name: str = "session"
    
    @classmethod
    def from_env(cls) -> SupersetConfig:
        """Load configuration from environment variables."""
        return cls(
            base_url=os.environ.get("SUPERSET_URL", "http://localhost:8088"),
            username=os.environ.get("SUPERSET_USERNAME"),
            password=os.environ.get("SUPERSET_PASSWORD"),
            api_key=os.environ.get("SUPERSET_API_KEY"),
            verify_ssl=os.environ.get("SUPERSET_VERIFY_SSL", "true").lower() == "true",
            timeout=int(os.environ.get("SUPERSET_TIMEOUT", "30")),
            oauth_client_id=os.environ.get("SUPERSET_OAUTH_CLIENT_ID"),
            oauth_client_secret=os.environ.get("SUPERSET_OAUTH_CLIENT_SECRET"),
            oauth_token_url=os.environ.get("SUPERSET_OAUTH_TOKEN_URL"),
        )
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> SupersetConfig:
        """Load configuration from JSON/YAML file."""
        path = Path(path)
        
        with open(path) as f:
            if path.suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    data = yaml.safe_load(f)
                except ImportError:
                    raise ImportError("PyYAML required for YAML config files")
            else:
                data = json.load(f)
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_url": self.base_url,
            "username": self.username,
            "verify_ssl": self.verify_ssl,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "csrf_enabled": self.csrf_enabled,
        }


@dataclass
class DatabaseConfig:
    """
    Configuration for a database connection in Superset.
    
    Usage:
        db_config = DatabaseConfig(
            name="Production DB",
            engine=DatabaseEngine.POSTGRESQL,
            host="db.example.com",
            port=5432,
            database="analytics",
            username="readonly",
            password="secret",
        )
    """
    name: str
    engine: DatabaseEngine
    host: str
    port: int
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Connection options
    extra: Dict[str, Any] = field(default_factory=dict)
    encrypted_extra: Dict[str, Any] = field(default_factory=dict)
    
    # Schema settings
    allow_ctas: bool = False
    allow_cvas: bool = False
    allow_dml: bool = False
    allow_run_async: bool = True
    expose_in_sqllab: bool = True
    
    # Cache settings
    cache_timeout: Optional[int] = None
    
    def get_sqlalchemy_uri(self) -> str:
        """Generate SQLAlchemy connection URI."""
        engine_map = {
            DatabaseEngine.POSTGRESQL: "postgresql+psycopg2",
            DatabaseEngine.MYSQL: "mysql+pymysql",
            DatabaseEngine.MSSQL: "mssql+pymssql",
            DatabaseEngine.SQLITE: "sqlite",
            DatabaseEngine.BIGQUERY: "bigquery",
            DatabaseEngine.SNOWFLAKE: "snowflake",
            DatabaseEngine.REDSHIFT: "redshift+psycopg2",
            DatabaseEngine.CLICKHOUSE: "clickhouse+native",
            DatabaseEngine.TRINO: "trino",
            DatabaseEngine.PRESTO: "presto",
        }
        
        driver = engine_map.get(self.engine, self.engine.value)
        
        if self.engine == DatabaseEngine.SQLITE:
            return f"{driver}:///{self.database}"
        
        auth = ""
        if self.username:
            auth = self.username
            if self.password:
                auth += f":{self.password}"
            auth += "@"
        
        return f"{driver}://{auth}{self.host}:{self.port}/{self.database}"
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Superset API payload."""
        return {
            "database_name": self.name,
            "sqlalchemy_uri": self.get_sqlalchemy_uri(),
            "extra": json.dumps(self.extra) if self.extra else "{}",
            "encrypted_extra": json.dumps(self.encrypted_extra) if self.encrypted_extra else "{}",
            "allow_ctas": self.allow_ctas,
            "allow_cvas": self.allow_cvas,
            "allow_dml": self.allow_dml,
            "allow_run_async": self.allow_run_async,
            "expose_in_sqllab": self.expose_in_sqllab,
            "cache_timeout": self.cache_timeout,
        }


@dataclass
class ColumnConfig:
    """Configuration for a dataset column."""
    name: str
    type: str
    is_temporal: bool = False
    is_filterable: bool = True
    is_groupby: bool = True
    description: Optional[str] = None
    expression: Optional[str] = None
    python_date_format: Optional[str] = None


@dataclass
class MetricConfig:
    """Configuration for a dataset metric."""
    name: str
    expression: str
    metric_type: str = "count"
    description: Optional[str] = None
    d3format: Optional[str] = None
    warning_text: Optional[str] = None


@dataclass
class DatasetConfig:
    """
    Configuration for a Superset dataset.
    
    Usage:
        dataset_config = DatasetConfig(
            name="Sales Data",
            table_name="sales",
            schema="public",
            database_id=1,
            columns=[
                ColumnConfig(name="id", type="INTEGER"),
                ColumnConfig(name="amount", type="NUMERIC"),
                ColumnConfig(name="created_at", type="TIMESTAMP", is_temporal=True),
            ],
            metrics=[
                MetricConfig(name="total_sales", expression="SUM(amount)"),
                MetricConfig(name="avg_order", expression="AVG(amount)"),
            ],
        )
    """
    name: str
    table_name: str
    database_id: int
    schema: Optional[str] = None
    sql: Optional[str] = None  # For virtual datasets
    
    columns: List[ColumnConfig] = field(default_factory=list)
    metrics: List[MetricConfig] = field(default_factory=list)
    
    # Settings
    is_sqllab_view: bool = False
    cache_timeout: Optional[int] = None
    default_endpoint: Optional[str] = None
    description: Optional[str] = None
    
    # Time settings
    main_dttm_col: Optional[str] = None
    offset: int = 0
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Superset API payload."""
        payload = {
            "table_name": self.table_name,
            "database": self.database_id,
            "schema": self.schema,
            "is_sqllab_view": self.is_sqllab_view,
        }
        
        if self.sql:
            payload["sql"] = self.sql
        
        if self.main_dttm_col:
            payload["main_dttm_col"] = self.main_dttm_col
        
        if self.cache_timeout:
            payload["cache_timeout"] = self.cache_timeout
        
        if self.description:
            payload["description"] = self.description
        
        return payload


@dataclass
class ChartConfig:
    """Configuration for a Superset chart."""
    name: str
    viz_type: VizType
    dataset_id: int
    
    # Query settings
    metrics: List[str] = field(default_factory=list)
    groupby: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    
    # Time settings
    time_column: Optional[str] = None
    time_range: str = "Last week"
    
    # Display settings
    row_limit: int = 10000
    order_desc: bool = True
    
    # Additional params
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Superset API payload."""
        params = {
            "viz_type": self.viz_type.value,
            "datasource": f"{self.dataset_id}__table",
            "metrics": self.metrics,
            "groupby": self.groupby,
            "columns": self.columns,
            "adhoc_filters": self.filters,
            "time_range": self.time_range,
            "row_limit": self.row_limit,
            "order_desc": self.order_desc,
            **self.extra_params,
        }
        
        if self.time_column:
            params["granularity_sqla"] = self.time_column
        
        return {
            "slice_name": self.name,
            "viz_type": self.viz_type.value,
            "datasource_id": self.dataset_id,
            "datasource_type": "table",
            "params": json.dumps(params),
        }


@dataclass  
class DashboardConfig:
    """Configuration for a Superset dashboard."""
    name: str
    slug: Optional[str] = None
    
    # Layout
    charts: List[int] = field(default_factory=list)
    position_json: Optional[str] = None
    
    # Settings
    published: bool = False
    certified_by: Optional[str] = None
    certification_details: Optional[str] = None
    
    # Filters
    json_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Access
    owners: List[int] = field(default_factory=list)
    roles: List[int] = field(default_factory=list)
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to Superset API payload."""
        return {
            "dashboard_title": self.name,
            "slug": self.slug,
            "published": self.published,
            "certified_by": self.certified_by,
            "certification_details": self.certification_details,
            "json_metadata": json.dumps(self.json_metadata),
            "owners": self.owners,
            "roles": self.roles,
        }
