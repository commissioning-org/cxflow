"""
SQL Lab client for Apache Superset.

Provides SQL Lab functionality:
- Query execution
- Query history
- Saved queries
- Results export
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


class QueryStatus(Enum):
    """Query execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    STOPPED = "stopped"


@dataclass
class QueryColumn:
    """Represents a column in query results."""
    name: str
    type: str
    is_date: bool = False
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> QueryColumn:
        return cls(
            name=data.get("name", data.get("column_name", "")),
            type=data.get("type", ""),
            is_date=data.get("is_date", False),
        )


@dataclass
class QueryResult:
    """Represents query execution results."""
    status: QueryStatus
    query_id: Optional[str] = None
    
    # Results
    columns: List[QueryColumn] = field(default_factory=list)
    data: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    
    # Error
    error_message: Optional[str] = None
    
    # Pagination
    is_limited: bool = False
    limit: Optional[int] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> QueryResult:
        """Create from API response."""
        status = QueryStatus.SUCCESS
        if data.get("status"):
            try:
                status = QueryStatus(data.get("status"))
            except ValueError:
                status = QueryStatus.FAILED if data.get("error") else QueryStatus.SUCCESS
        
        columns = [
            QueryColumn.from_api(c)
            for c in data.get("columns", [])
        ]
        
        return cls(
            status=status,
            query_id=str(data.get("query_id", "")),
            columns=columns,
            data=data.get("data", []),
            row_count=len(data.get("data", [])),
            execution_time_ms=data.get("query", {}).get("executedSql", 0),
            error_message=data.get("error"),
            is_limited=data.get("isLimited", False),
            limit=data.get("limit"),
        )
    
    def to_dataframe(self):
        """Convert to pandas DataFrame."""
        try:
            import pandas as pd
            return pd.DataFrame(self.data)
        except ImportError:
            raise ImportError("pandas is required for to_dataframe()")
    
    def to_csv(self) -> str:
        """Convert to CSV string."""
        if not self.data:
            return ""
        
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[c.name for c in self.columns])
        writer.writeheader()
        writer.writerows(self.data)
        
        return output.getvalue()
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.data)
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over result rows."""
        return iter(self.data)
    
    def __len__(self) -> int:
        return self.row_count


@dataclass
class Query:
    """Represents a SQL Lab query."""
    id: int
    sql: str
    database_id: int
    schema: Optional[str] = None
    
    # Status
    status: QueryStatus = QueryStatus.PENDING
    error_message: Optional[str] = None
    
    # Results
    rows: int = 0
    columns: List[str] = field(default_factory=list)
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    
    # Metadata
    user_id: Optional[int] = None
    tab_name: Optional[str] = None
    client_id: Optional[str] = None
    
    # Limits
    limit: Optional[int] = None
    limit_used: bool = False
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Query:
        """Create from API response."""
        status = QueryStatus.PENDING
        if data.get("status"):
            try:
                status = QueryStatus(data.get("status"))
            except ValueError:
                pass
        
        return cls(
            id=data.get("id", 0),
            sql=data.get("sql", ""),
            database_id=data.get("database_id", 0),
            schema=data.get("schema"),
            status=status,
            error_message=data.get("error_message"),
            rows=data.get("rows", 0),
            columns=data.get("columns", []),
            execution_time_ms=data.get("executed_sql"),
            user_id=data.get("user_id"),
            tab_name=data.get("tab_name"),
            limit=data.get("limit"),
            limit_used=data.get("limit_used", False),
        )


@dataclass
class SavedQuery:
    """Represents a saved SQL query."""
    id: int
    label: str
    sql: str
    database_id: int
    schema: Optional[str] = None
    
    # Metadata
    description: Optional[str] = None
    template_parameters: Optional[Dict[str, Any]] = None
    
    # Ownership
    created_by: Optional[str] = None
    changed_by: Optional[str] = None
    created_on: Optional[datetime] = None
    changed_on: Optional[datetime] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> SavedQuery:
        """Create from API response."""
        result = data.get("result", data)
        
        return cls(
            id=result.get("id", 0),
            label=result.get("label", ""),
            sql=result.get("sql", ""),
            database_id=result.get("db_id", 0),
            schema=result.get("schema"),
            description=result.get("description"),
            template_parameters=result.get("template_parameters"),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        return {
            "label": self.label,
            "sql": self.sql,
            "db_id": self.database_id,
            "schema": self.schema,
            "description": self.description,
            "template_parameters": json.dumps(self.template_parameters) if self.template_parameters else None,
        }


class SQLLabClient:
    """
    SQL Lab client for executing queries.
    
    Usage:
        sql = SQLLabClient(client)
        
        # Execute query
        result = sql.execute(
            database_id=1,
            sql="SELECT * FROM users LIMIT 10",
        )
        
        for row in result:
            print(row)
        
        # Execute with timeout
        result = sql.execute(
            database_id=1,
            sql="SELECT * FROM large_table",
            timeout=30,
            limit=1000,
        )
        
        # Async execution
        query = sql.submit_query(database_id=1, sql="SELECT ...")
        result = sql.wait_for_query(query.id)
        
        # Saved queries
        saved = sql.save_query(
            label="Active Users",
            database_id=1,
            sql="SELECT * FROM users WHERE active = true",
        )
    """
    
    def __init__(self, client: SupersetClient):
        self.client = client
    
    def execute(
        self,
        database_id: int,
        sql: str,
        schema: Optional[str] = None,
        limit: int = 1000,
        timeout: int = 300,
        run_async: bool = False,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """
        Execute a SQL query.
        
        Args:
            database_id: Database to run query against
            sql: SQL query to execute
            schema: Schema to use
            limit: Maximum rows to return
            timeout: Query timeout in seconds
            run_async: Whether to run asynchronously
            template_params: Jinja template parameters
        """
        query_payload = {
            "database_id": database_id,
            "sql": sql,
            "schema": schema,
            "queryLimit": limit,
            "runAsync": run_async,
            "ctas": False,
            "ctas_method": "TABLE",
        }
        
        if template_params:
            query_payload["templateParams"] = json.dumps(template_params)
        
        if run_async:
            # Submit and wait
            result = self.client.execute_sql(query_payload)
            query_id = result.get("query_id") or result.get("query", {}).get("queryId")
            
            if query_id:
                return self._wait_for_results(query_id, timeout=timeout)
            
            return QueryResult.from_api(result)
        else:
            # Synchronous execution
            result = self.client.execute_sql(query_payload)
            return QueryResult.from_api(result)
    
    def submit_query(
        self,
        database_id: int,
        sql: str,
        schema: Optional[str] = None,
        limit: int = 1000,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> Query:
        """Submit a query for async execution."""
        query_payload = {
            "database_id": database_id,
            "sql": sql,
            "schema": schema,
            "queryLimit": limit,
            "runAsync": True,
        }
        
        if template_params:
            query_payload["templateParams"] = json.dumps(template_params)
        
        result = self.client.execute_sql(query_payload)
        query_data = result.get("query", {})
        query_data["id"] = result.get("query_id") or query_data.get("queryId")
        
        return Query.from_api(query_data)
    
    def get_query_status(self, query_id: str) -> Query:
        """Get query execution status."""
        result = self.client.get_query_status(query_id)
        return Query.from_api(result.get("query", result))
    
    def get_query_results(self, query_id: str) -> QueryResult:
        """Get results for a completed query."""
        result = self.client.get_query_results(query_id)
        return QueryResult.from_api(result)
    
    def wait_for_query(
        self,
        query_id: str,
        timeout: int = 300,
        poll_interval: float = 1.0,
    ) -> QueryResult:
        """Wait for query to complete and return results."""
        return self._wait_for_results(query_id, timeout, poll_interval)
    
    def _wait_for_results(
        self,
        query_id: str,
        timeout: int = 300,
        poll_interval: float = 1.0,
    ) -> QueryResult:
        """Internal method to poll for query results."""
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return QueryResult(
                    status=QueryStatus.TIMED_OUT,
                    query_id=query_id,
                    error_message=f"Query timed out after {timeout} seconds",
                )
            
            query = self.get_query_status(query_id)
            
            if query.status == QueryStatus.SUCCESS:
                return self.get_query_results(query_id)
            elif query.status == QueryStatus.FAILED:
                return QueryResult(
                    status=QueryStatus.FAILED,
                    query_id=query_id,
                    error_message=query.error_message,
                )
            elif query.status in (QueryStatus.STOPPED, QueryStatus.TIMED_OUT):
                return QueryResult(
                    status=query.status,
                    query_id=query_id,
                    error_message=query.error_message,
                )
            
            time.sleep(poll_interval)
    
    def stop_query(self, query_id: str) -> bool:
        """Stop a running query."""
        try:
            self.client.stop_query(query_id)
            return True
        except Exception as e:
            logger.error(f"Failed to stop query {query_id}: {e}")
            return False
    
    def get_query_history(
        self,
        database_id: Optional[int] = None,
        user_id: Optional[int] = None,
        status: Optional[QueryStatus] = None,
        page: int = 0,
        page_size: int = 100,
    ) -> List[Query]:
        """Get query history."""
        filters = []
        
        if database_id:
            filters.append({"col": "database_id", "opr": "eq", "value": database_id})
        if user_id:
            filters.append({"col": "user_id", "opr": "eq", "value": user_id})
        if status:
            filters.append({"col": "status", "opr": "eq", "value": status.value})
        
        result = self.client.get_queries(
            page=page,
            page_size=page_size,
            filters=filters,
        )
        
        queries = []
        for item in result.get("result", []):
            queries.append(Query.from_api(item))
        
        return queries
    
    # Saved queries
    
    def list_saved_queries(
        self,
        database_id: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 0,
        page_size: int = 100,
    ) -> List[SavedQuery]:
        """List saved queries."""
        filters = []
        
        if database_id:
            filters.append({"col": "db_id", "opr": "eq", "value": database_id})
        if search:
            filters.append({"col": "label", "opr": "ct", "value": search})
        
        result = self.client.get_saved_queries(
            page=page,
            page_size=page_size,
            filters=filters,
        )
        
        queries = []
        for item in result.get("result", []):
            queries.append(SavedQuery.from_api({"result": item}))
        
        return queries
    
    def get_saved_query(self, query_id: int) -> SavedQuery:
        """Get saved query by ID."""
        result = self.client.get_saved_query(query_id)
        return SavedQuery.from_api(result)
    
    def save_query(
        self,
        label: str,
        database_id: int,
        sql: str,
        schema: Optional[str] = None,
        description: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> SavedQuery:
        """Save a query."""
        query_data = {
            "label": label,
            "db_id": database_id,
            "sql": sql,
            "schema": schema,
            "description": description,
        }
        
        if template_params:
            query_data["template_parameters"] = json.dumps(template_params)
        
        result = self.client.create_saved_query(query_data)
        return self.get_saved_query(result.get("id"))
    
    def update_saved_query(
        self,
        query_id: int,
        **kwargs,
    ) -> SavedQuery:
        """Update a saved query."""
        self.client.update_saved_query(query_id, kwargs)
        return self.get_saved_query(query_id)
    
    def delete_saved_query(self, query_id: int) -> bool:
        """Delete a saved query."""
        try:
            self.client.delete_saved_query(query_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete saved query {query_id}: {e}")
            return False
    
    def execute_saved_query(
        self,
        query_id: int,
        template_params: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
        timeout: int = 300,
    ) -> QueryResult:
        """Execute a saved query."""
        saved = self.get_saved_query(query_id)
        
        # Merge template parameters
        params = saved.template_parameters or {}
        if template_params:
            params.update(template_params)
        
        return self.execute(
            database_id=saved.database_id,
            sql=saved.sql,
            schema=saved.schema,
            limit=limit,
            timeout=timeout,
            template_params=params if params else None,
        )
