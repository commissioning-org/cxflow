"""
Apache Superset API Client.

Provides sync and async clients for interacting with Superset's REST API.
Features:
- Authentication (username/password, API key, OAuth2)
- CSRF token handling
- Retry logic with exponential backoff
- Session management
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

from .config import SupersetConfig

logger = logging.getLogger(__name__)


@dataclass
class AuthToken:
    """Authentication token."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at


class SupersetAPIError(Exception):
    """Superset API error."""
    
    def __init__(self, message: str, status_code: int = 0, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class SupersetClient:
    """
    Synchronous client for Apache Superset API.
    
    Features:
    - Multiple authentication methods
    - Automatic CSRF token handling
    - Request retry with backoff
    - Full API coverage
    
    Usage:
        client = SupersetClient("http://localhost:8088", "admin", "admin")
        
        # List dashboards
        dashboards = client.get_dashboards()
        
        # Search
        results = client.search("sales dashboard")
        
        # Execute SQL
        result = client.execute_sql(1, "SELECT * FROM sales LIMIT 10")
    """
    
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[SupersetConfig] = None,
    ):
        self.config = config or SupersetConfig(
            base_url=base_url,
            username=username,
            password=password,
            api_key=api_key,
        )
        
        self.base_url = self.config.base_url.rstrip("/")
        self._session_cookie: Optional[str] = None
        self._csrf_token: Optional[str] = None
        self._auth_token: Optional[AuthToken] = None
        
        # Cookie handling
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        )
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry: int = 0,
    ) -> Dict[str, Any]:
        """Make HTTP request to Superset API."""
        url = f"{self.base_url}{endpoint}"
        
        if params:
            url += "?" + urllib.parse.urlencode(params)
        
        req_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Add authentication
        if self.config.api_key:
            req_headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif self._auth_token and not self._auth_token.is_expired:
            req_headers["Authorization"] = f"Bearer {self._auth_token.access_token}"
        
        # Add CSRF token for mutating requests
        if method in ("POST", "PUT", "PATCH", "DELETE") and self._csrf_token:
            req_headers["X-CSRFToken"] = self._csrf_token
        
        if headers:
            req_headers.update(headers)
        
        body = None
        if data:
            body = json.dumps(data).encode("utf-8")
        
        request = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method,
        )
        
        try:
            response = self._opener.open(request, timeout=self.config.timeout)
            response_data = response.read().decode("utf-8")
            
            if response_data:
                return json.loads(response_data)
            return {}
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            error_data = {}
            
            try:
                error_data = json.loads(error_body)
            except json.JSONDecodeError:
                pass
            
            # Handle 401 - try to re-authenticate
            if e.code == 401 and retry < self.config.max_retries:
                self._authenticate()
                return self._request(method, endpoint, data, params, headers, retry + 1)
            
            # Handle 403 - might need CSRF token refresh
            if e.code == 403 and retry < self.config.max_retries:
                self._refresh_csrf()
                return self._request(method, endpoint, data, params, headers, retry + 1)
            
            raise SupersetAPIError(
                f"API error: {e.code} - {error_body}",
                status_code=e.code,
                response=error_data,
            )
            
        except urllib.error.URLError as e:
            if retry < self.config.max_retries:
                time.sleep(2 ** retry)
                return self._request(method, endpoint, data, params, headers, retry + 1)
            raise SupersetAPIError(f"Connection error: {e.reason}")
    
    def _authenticate(self) -> None:
        """Authenticate with Superset."""
        if not self.config.username or not self.config.password:
            raise SupersetAPIError("Username and password required for authentication")
        
        # Login endpoint
        login_data = {
            "username": self.config.username,
            "password": self.config.password,
            "provider": "db",
            "refresh": True,
        }
        
        try:
            result = self._request("POST", "/api/v1/security/login", data=login_data)
            
            self._auth_token = AuthToken(
                access_token=result.get("access_token", ""),
                refresh_token=result.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            
            logger.info("Successfully authenticated with Superset")
            
            # Get CSRF token
            self._refresh_csrf()
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    def _refresh_csrf(self) -> None:
        """Refresh CSRF token."""
        try:
            result = self._request("GET", "/api/v1/security/csrf_token/")
            self._csrf_token = result.get("result", "")
        except Exception as e:
            logger.warning(f"Could not get CSRF token: {e}")
    
    def login(self) -> None:
        """Explicitly login to Superset."""
        self._authenticate()
    
    # ==================== Dashboard API ====================
    
    def get_dashboards(
        self,
        page: int = 0,
        page_size: int = 100,
        filters: Optional[List[Dict]] = None,
        order_column: str = "changed_on_delta_humanized",
        order_direction: str = "desc",
    ) -> Dict[str, Any]:
        """Get list of dashboards."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
                "order_column": order_column,
                "order_direction": order_direction,
                "filters": filters or [],
            })
        }
        return self._request("GET", "/api/v1/dashboard/", params=params)
    
    def get_dashboard(self, dashboard_id: int) -> Dict[str, Any]:
        """Get dashboard by ID."""
        return self._request("GET", f"/api/v1/dashboard/{dashboard_id}")
    
    def create_dashboard(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new dashboard."""
        return self._request("POST", "/api/v1/dashboard/", data=dashboard_data)
    
    def update_dashboard(self, dashboard_id: int, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing dashboard."""
        return self._request("PUT", f"/api/v1/dashboard/{dashboard_id}", data=dashboard_data)
    
    def delete_dashboard(self, dashboard_id: int) -> Dict[str, Any]:
        """Delete a dashboard."""
        return self._request("DELETE", f"/api/v1/dashboard/{dashboard_id}")
    
    def export_dashboards(self, dashboard_ids: List[int]) -> bytes:
        """Export dashboards as ZIP."""
        params = {"q": json.dumps(dashboard_ids)}
        # Returns binary data
        url = f"{self.base_url}/api/v1/dashboard/export/"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        
        request = urllib.request.Request(url, method="GET")
        if self._auth_token:
            request.add_header("Authorization", f"Bearer {self._auth_token.access_token}")
        
        response = self._opener.open(request, timeout=self.config.timeout)
        return response.read()
    
    def import_dashboards(self, zip_file: bytes, overwrite: bool = False) -> Dict[str, Any]:
        """Import dashboards from ZIP."""
        # Multipart form upload
        boundary = "----SupersetBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="formData"; filename="dashboards.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
        ).encode() + zip_file + f"\r\n--{boundary}--\r\n".encode()
        
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        
        return self._request("POST", "/api/v1/dashboard/import/", headers=headers)
    
    def get_dashboard_charts(self, dashboard_id: int) -> Dict[str, Any]:
        """Get charts in a dashboard."""
        return self._request("GET", f"/api/v1/dashboard/{dashboard_id}/charts")
    
    # ==================== Chart API ====================
    
    def get_charts(
        self,
        page: int = 0,
        page_size: int = 100,
        filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Get list of charts."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
                "filters": filters or [],
            })
        }
        return self._request("GET", "/api/v1/chart/", params=params)
    
    def get_chart(self, chart_id: int) -> Dict[str, Any]:
        """Get chart by ID."""
        return self._request("GET", f"/api/v1/chart/{chart_id}")
    
    def create_chart(self, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new chart."""
        return self._request("POST", "/api/v1/chart/", data=chart_data)
    
    def update_chart(self, chart_id: int, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing chart."""
        return self._request("PUT", f"/api/v1/chart/{chart_id}", data=chart_data)
    
    def delete_chart(self, chart_id: int) -> Dict[str, Any]:
        """Delete a chart."""
        return self._request("DELETE", f"/api/v1/chart/{chart_id}")
    
    def get_chart_data(self, chart_id: int) -> Dict[str, Any]:
        """Get chart data/results."""
        return self._request("GET", f"/api/v1/chart/{chart_id}/data/")
    
    # ==================== Dataset API ====================
    
    def get_datasets(
        self,
        page: int = 0,
        page_size: int = 100,
        filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Get list of datasets."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
                "filters": filters or [],
            })
        }
        return self._request("GET", "/api/v1/dataset/", params=params)
    
    def get_dataset(self, dataset_id: int) -> Dict[str, Any]:
        """Get dataset by ID."""
        return self._request("GET", f"/api/v1/dataset/{dataset_id}")
    
    def create_dataset(self, dataset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new dataset."""
        return self._request("POST", "/api/v1/dataset/", data=dataset_data)
    
    def update_dataset(self, dataset_id: int, dataset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing dataset."""
        return self._request("PUT", f"/api/v1/dataset/{dataset_id}", data=dataset_data)
    
    def delete_dataset(self, dataset_id: int) -> Dict[str, Any]:
        """Delete a dataset."""
        return self._request("DELETE", f"/api/v1/dataset/{dataset_id}")
    
    def refresh_dataset(self, dataset_id: int) -> Dict[str, Any]:
        """Refresh dataset columns from source."""
        return self._request("PUT", f"/api/v1/dataset/{dataset_id}/refresh")
    
    # ==================== Database API ====================
    
    def get_databases(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get list of database connections."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
            })
        }
        return self._request("GET", "/api/v1/database/", params=params)
    
    def get_database(self, database_id: int) -> Dict[str, Any]:
        """Get database by ID."""
        return self._request("GET", f"/api/v1/database/{database_id}")
    
    def create_database(self, database_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new database connection."""
        return self._request("POST", "/api/v1/database/", data=database_data)
    
    def update_database(self, database_id: int, database_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing database connection."""
        return self._request("PUT", f"/api/v1/database/{database_id}", data=database_data)
    
    def delete_database(self, database_id: int) -> Dict[str, Any]:
        """Delete a database connection."""
        return self._request("DELETE", f"/api/v1/database/{database_id}")
    
    def test_database_connection(self, database_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test database connection."""
        return self._request("POST", "/api/v1/database/test_connection/", data=database_data)
    
    def get_database_schemas(self, database_id: int) -> Dict[str, Any]:
        """Get schemas in a database."""
        return self._request("GET", f"/api/v1/database/{database_id}/schemas/")
    
    def get_database_tables(self, database_id: int, schema: str) -> Dict[str, Any]:
        """Get tables in a database schema."""
        params = {"q": json.dumps({"schema_name": schema})}
        return self._request("GET", f"/api/v1/database/{database_id}/tables/", params=params)
    
    # ==================== SQL Lab API ====================
    
    def execute_sql(
        self,
        database_id: int,
        sql: str,
        schema: Optional[str] = None,
        run_async: bool = False,
        select_as_cta: bool = False,
        ctas_method: str = "TABLE",
        tmp_table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute SQL query."""
        data = {
            "database_id": database_id,
            "sql": sql,
            "schema": schema,
            "runAsync": run_async,
            "select_as_cta": select_as_cta,
            "ctas_method": ctas_method,
        }
        
        if tmp_table_name:
            data["tmp_table_name"] = tmp_table_name
        
        return self._request("POST", "/api/v1/sqllab/execute/", data=data)
    
    def get_query_results(self, query_id: str) -> Dict[str, Any]:
        """Get results of an async query."""
        return self._request("GET", f"/api/v1/sqllab/results/", params={"key": query_id})
    
    def get_query_history(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get SQL query history."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
            })
        }
        return self._request("GET", "/api/v1/query/", params=params)
    
    def stop_query(self, query_id: str) -> Dict[str, Any]:
        """Stop a running query."""
        return self._request("POST", "/api/v1/sqllab/stop/", data={"client_id": query_id})
    
    # ==================== Security API ====================
    
    def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user."""
        return self._request("GET", "/api/v1/me/")
    
    def get_roles(self) -> Dict[str, Any]:
        """Get list of roles."""
        return self._request("GET", "/api/v1/security/roles/")
    
    def get_users(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get list of users."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
            })
        }
        return self._request("GET", "/api/v1/security/users/", params=params)
    
    # ==================== Reports API ====================
    
    def get_reports(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get list of reports/alerts."""
        params = {
            "q": json.dumps({
                "page": page,
                "page_size": page_size,
            })
        }
        return self._request("GET", "/api/v1/report/", params=params)
    
    def get_report(self, report_id: int) -> Dict[str, Any]:
        """Get report by ID."""
        return self._request("GET", f"/api/v1/report/{report_id}")
    
    def create_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new report."""
        return self._request("POST", "/api/v1/report/", data=report_data)
    
    def update_report(self, report_id: int, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing report."""
        return self._request("PUT", f"/api/v1/report/{report_id}", data=report_data)
    
    def delete_report(self, report_id: int) -> Dict[str, Any]:
        """Delete a report."""
        return self._request("DELETE", f"/api/v1/report/{report_id}")
    
    # ==================== Misc API ====================
    
    def get_available_domains(self) -> Dict[str, Any]:
        """Get available domains for embedding."""
        return self._request("GET", "/api/v1/dashboard/available_domains/")
    
    def search(
        self,
        query: str,
        page: int = 0,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        """Global search across Superset."""
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,
        }
        return self._request("GET", "/api/v1/search/", params=params)
    
    def health_check(self) -> Dict[str, Any]:
        """Check Superset health."""
        return self._request("GET", "/health")
    
    def get_version(self) -> Dict[str, Any]:
        """Get Superset version info."""
        return self._request("GET", "/api/v1/version")


class AsyncSupersetClient:
    """
    Asynchronous client for Apache Superset API.
    
    Requires aiohttp package.
    
    Usage:
        async with AsyncSupersetClient("http://localhost:8088", "admin", "admin") as client:
            dashboards = await client.get_dashboards()
    """
    
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[SupersetConfig] = None,
    ):
        self.config = config or SupersetConfig(
            base_url=base_url,
            username=username,
            password=password,
            api_key=api_key,
        )
        
        self.base_url = self.config.base_url.rstrip("/")
        self._session = None
        self._csrf_token: Optional[str] = None
        self._auth_token: Optional[AuthToken] = None
    
    async def __aenter__(self):
        try:
            import aiohttp
            self._session = aiohttp.ClientSession()
            await self._authenticate()
            return self
        except ImportError:
            raise ImportError("aiohttp required for async client")
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make async HTTP request."""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token.access_token}"
        
        if method in ("POST", "PUT", "PATCH", "DELETE") and self._csrf_token:
            headers["X-CSRFToken"] = self._csrf_token
        
        async with self._session.request(
            method,
            url,
            json=data,
            params=params,
            headers=headers,
            timeout=self.config.timeout,
        ) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise SupersetAPIError(
                    f"API error: {response.status}",
                    status_code=response.status,
                )
            
            if response.content_type == "application/json":
                return await response.json()
            return {}
    
    async def _authenticate(self) -> None:
        """Authenticate with Superset."""
        if not self.config.username or not self.config.password:
            return
        
        login_data = {
            "username": self.config.username,
            "password": self.config.password,
            "provider": "db",
            "refresh": True,
        }
        
        result = await self._request("POST", "/api/v1/security/login", data=login_data)
        
        self._auth_token = AuthToken(
            access_token=result.get("access_token", ""),
            refresh_token=result.get("refresh_token"),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        
        # Get CSRF token
        csrf_result = await self._request("GET", "/api/v1/security/csrf_token/")
        self._csrf_token = csrf_result.get("result", "")
    
    # Async versions of main API methods
    async def get_dashboards(self, **kwargs) -> Dict[str, Any]:
        """Get list of dashboards."""
        params = {"q": json.dumps(kwargs)}
        return await self._request("GET", "/api/v1/dashboard/", params=params)
    
    async def get_dashboard(self, dashboard_id: int) -> Dict[str, Any]:
        """Get dashboard by ID."""
        return await self._request("GET", f"/api/v1/dashboard/{dashboard_id}")
    
    async def get_charts(self, **kwargs) -> Dict[str, Any]:
        """Get list of charts."""
        params = {"q": json.dumps(kwargs)}
        return await self._request("GET", "/api/v1/chart/", params=params)
    
    async def get_chart(self, chart_id: int) -> Dict[str, Any]:
        """Get chart by ID."""
        return await self._request("GET", f"/api/v1/chart/{chart_id}")
    
    async def execute_sql(self, database_id: int, sql: str, **kwargs) -> Dict[str, Any]:
        """Execute SQL query."""
        data = {"database_id": database_id, "sql": sql, **kwargs}
        return await self._request("POST", "/api/v1/sqllab/execute/", data=data)
    
    async def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """Global search."""
        params = {"q": query, **kwargs}
        return await self._request("GET", "/api/v1/search/", params=params)
