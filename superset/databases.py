"""
Database connection management for Apache Superset.

Provides database connection management:
- Database CRUD operations
- Connection testing
- Schema/table discovery
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .config import DatabaseEngine

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


@dataclass
class Database:
    """Represents a Superset database connection."""
    id: int
    name: str
    sqlalchemy_uri: str
    backend: str = ""
    
    # Settings
    allow_ctas: bool = False
    allow_cvas: bool = False
    allow_dml: bool = False
    allow_run_async: bool = True
    expose_in_sqllab: bool = True
    
    # Extra configuration
    extra: Dict[str, Any] = field(default_factory=dict)
    encrypted_extra: Dict[str, Any] = field(default_factory=dict)
    
    # Cache
    cache_timeout: Optional[int] = None
    
    # Metadata
    created_by: Optional[str] = None
    created_on: Optional[datetime] = None
    changed_by: Optional[str] = None
    changed_on: Optional[datetime] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Database:
        """Create from API response."""
        result = data.get("result", data)
        
        extra = result.get("extra", "{}")
        if isinstance(extra, str):
            extra = json.loads(extra) if extra else {}
        
        return cls(
            id=result.get("id", 0),
            name=result.get("database_name", ""),
            sqlalchemy_uri=result.get("sqlalchemy_uri", ""),
            backend=result.get("backend", ""),
            allow_ctas=result.get("allow_ctas", False),
            allow_cvas=result.get("allow_cvas", False),
            allow_dml=result.get("allow_dml", False),
            allow_run_async=result.get("allow_run_async", True),
            expose_in_sqllab=result.get("expose_in_sqllab", True),
            extra=extra,
            cache_timeout=result.get("cache_timeout"),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        return {
            "database_name": self.name,
            "sqlalchemy_uri": self.sqlalchemy_uri,
            "allow_ctas": self.allow_ctas,
            "allow_cvas": self.allow_cvas,
            "allow_dml": self.allow_dml,
            "allow_run_async": self.allow_run_async,
            "expose_in_sqllab": self.expose_in_sqllab,
            "extra": json.dumps(self.extra) if self.extra else "{}",
            "cache_timeout": self.cache_timeout,
        }
    
    @property
    def masked_uri(self) -> str:
        """Get URI with password masked."""
        import re
        return re.sub(r':([^:@]+)@', ':***@', self.sqlalchemy_uri)


class DatabaseManager:
    """
    High-level database connection management.
    
    Usage:
        manager = DatabaseManager(client)
        
        # List databases
        databases = manager.list_databases()
        
        # Create database connection
        db = manager.create_database(
            name="Analytics DB",
            sqlalchemy_uri="postgresql://user:pass@host:5432/analytics",
        )
        
        # Test connection
        is_valid = manager.test_connection(db.id)
        
        # Discover schemas/tables
        schemas = manager.get_schemas(db.id)
        tables = manager.get_tables(db.id, "public")
    """
    
    def __init__(self, client: SupersetClient):
        self.client = client
    
    def list_databases(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> List[Database]:
        """List all database connections."""
        result = self.client.get_databases(page=page, page_size=page_size)
        
        databases = []
        for item in result.get("result", []):
            databases.append(Database.from_api({"result": item}))
        
        return databases
    
    def get_database(self, database_id: int) -> Database:
        """Get database by ID."""
        result = self.client.get_database(database_id)
        return Database.from_api(result)
    
    def get_database_by_name(self, name: str) -> Optional[Database]:
        """Get database by name."""
        databases = self.list_databases()
        for db in databases:
            if db.name == name:
                return db
        return None
    
    def create_database(
        self,
        name: str,
        sqlalchemy_uri: str,
        expose_in_sqllab: bool = True,
        allow_ctas: bool = False,
        allow_cvas: bool = False,
        allow_dml: bool = False,
        allow_run_async: bool = True,
        extra: Optional[Dict] = None,
    ) -> Database:
        """Create a new database connection."""
        database_data = {
            "database_name": name,
            "sqlalchemy_uri": sqlalchemy_uri,
            "expose_in_sqllab": expose_in_sqllab,
            "allow_ctas": allow_ctas,
            "allow_cvas": allow_cvas,
            "allow_dml": allow_dml,
            "allow_run_async": allow_run_async,
            "extra": json.dumps(extra) if extra else "{}",
        }
        
        result = self.client.create_database(database_data)
        return self.get_database(result.get("id"))
    
    def create_database_from_config(
        self,
        engine: DatabaseEngine,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        **kwargs,
    ) -> Database:
        """Create database connection from parameters."""
        from .config import DatabaseConfig
        
        config = DatabaseConfig(
            name=name,
            engine=engine,
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            **kwargs,
        )
        
        return self.create_database(
            name=name,
            sqlalchemy_uri=config.get_sqlalchemy_uri(),
            **{k: v for k, v in config.to_api_payload().items() if k not in ("database_name", "sqlalchemy_uri")},
        )
    
    def update_database(
        self,
        database_id: int,
        **kwargs,
    ) -> Database:
        """Update an existing database connection."""
        self.client.update_database(database_id, kwargs)
        return self.get_database(database_id)
    
    def delete_database(self, database_id: int) -> bool:
        """Delete a database connection."""
        try:
            self.client.delete_database(database_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete database {database_id}: {e}")
            return False
    
    def test_connection(
        self,
        database_id: Optional[int] = None,
        sqlalchemy_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Test database connection."""
        if database_id:
            db = self.get_database(database_id)
            sqlalchemy_uri = db.sqlalchemy_uri
        
        if not sqlalchemy_uri:
            raise ValueError("Either database_id or sqlalchemy_uri required")
        
        return self.client.test_database_connection({
            "sqlalchemy_uri": sqlalchemy_uri,
        })
    
    def get_schemas(self, database_id: int) -> List[str]:
        """Get all schemas in database."""
        result = self.client.get_database_schemas(database_id)
        return result.get("result", [])
    
    def get_tables(
        self,
        database_id: int,
        schema: str,
    ) -> List[Dict[str, Any]]:
        """Get all tables in a schema."""
        result = self.client.get_database_tables(database_id, schema)
        return result.get("result", [])
    
    def discover_tables(
        self,
        database_id: int,
    ) -> Dict[str, List[str]]:
        """Discover all tables across all schemas."""
        schemas = self.get_schemas(database_id)
        
        discovery = {}
        for schema in schemas:
            tables = self.get_tables(database_id, schema)
            discovery[schema] = [t.get("value", t.get("table_name", "")) for t in tables]
        
        return discovery
