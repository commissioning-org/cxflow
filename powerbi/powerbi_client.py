"""
Power BI Automation Python SDK

Comprehensive Python implementation based on marclelijveld/Power-BI-Automation.
Provides workspace management, deployment pipelines, dataset operations,
XMLA endpoints, and dataflow management for Power BI and Microsoft Fabric.

@author CXFlow Integration
@version 1.0.0
@see https://github.com/marclelijveld/Power-BI-Automation
"""

from __future__ import annotations

import os
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class PowerBIConfig:
    """Power BI configuration settings."""
    
    tenant_id: str = field(default_factory=lambda: os.getenv("PBI_TENANT_ID", ""))
    client_id: str = field(default_factory=lambda: os.getenv("PBI_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("PBI_CLIENT_SECRET", ""))
    username: str = field(default_factory=lambda: os.getenv("PBI_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("PBI_PASSWORD", ""))
    auth_mode: str = field(default_factory=lambda: os.getenv("PBI_AUTH_MODE", "service_principal"))
    api_base: str = "https://api.powerbi.com/v1.0/myorg/"
    fabric_api_base: str = "https://api.fabric.microsoft.com/v1/"
    xmla_base: str = "powerbi://api.powerbi.com/v1.0/myorg/"
    timeout: int = field(default_factory=lambda: int(os.getenv("PBI_TIMEOUT", "30")))
    retry_count: int = field(default_factory=lambda: int(os.getenv("PBI_RETRY_COUNT", "3")))


# ============================================================================
# Models
# ============================================================================

class Workspace(BaseModel):
    """Power BI Workspace model."""
    id: str
    name: str
    is_on_dedicated_capacity: bool = Field(alias="isOnDedicatedCapacity", default=False)
    capacity_id: Optional[str] = Field(alias="capacityId", default=None)
    type: Optional[str] = None
    
    class Config:
        populate_by_name = True


class Dataset(BaseModel):
    """Power BI Dataset model."""
    id: str
    name: str
    configured_by: Optional[str] = Field(alias="configuredBy", default=None)
    is_refreshable: bool = Field(alias="isRefreshable", default=True)
    is_effective_identity_required: bool = Field(alias="isEffectiveIdentityRequired", default=False)
    target_storage_mode: Optional[str] = Field(alias="targetStorageMode", default=None)
    
    class Config:
        populate_by_name = True


class Dataflow(BaseModel):
    """Power BI Dataflow model."""
    object_id: str = Field(alias="objectId")
    name: str
    description: Optional[str] = None
    model_url: Optional[str] = Field(alias="modelUrl", default=None)
    configured_by: Optional[str] = Field(alias="configuredBy", default=None)
    
    class Config:
        populate_by_name = True


class Pipeline(BaseModel):
    """Deployment Pipeline model."""
    id: str
    display_name: str = Field(alias="displayName")
    description: Optional[str] = None
    stages: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        populate_by_name = True


class RefreshRequest(BaseModel):
    """Dataset refresh request."""
    notify_option: Literal["MailOnCompletion", "MailOnFailure", "NoNotification"] = Field(
        default="NoNotification",
        alias="notifyOption"
    )
    
    class Config:
        populate_by_name = True


class DeploymentRequest(BaseModel):
    """Pipeline deployment request."""
    source_stage_order: int = Field(alias="sourceStageOrder")
    options: Dict[str, bool] = Field(default_factory=lambda: {
        "allowOverwriteArtifact": True,
        "allowCreateArtifact": True
    })
    note: Optional[str] = None
    
    class Config:
        populate_by_name = True


# ============================================================================
# Token Cache
# ============================================================================

class TokenCache:
    """Thread-safe token cache."""
    
    _access_token: Optional[str] = None
    _expires_at: Optional[float] = None
    
    @classmethod
    def get(cls) -> Optional[str]:
        """Get cached token if valid."""
        if cls._access_token and cls._expires_at and time.time() < cls._expires_at - 60:
            return cls._access_token
        return None
    
    @classmethod
    def set(cls, token: str, expires_in: int) -> None:
        """Cache token with expiration."""
        cls._access_token = token
        cls._expires_at = time.time() + expires_in
    
    @classmethod
    def clear(cls) -> None:
        """Clear cached token."""
        cls._access_token = None
        cls._expires_at = None


# ============================================================================
# Power BI Client
# ============================================================================

class PowerBIClient:
    """
    Power BI REST API Client.
    
    Provides comprehensive access to Power BI and Microsoft Fabric APIs
    for workspace management, dataset operations, deployment pipelines,
    dataflow management, and more.
    
    Example:
        ```python
        client = PowerBIClient()
        
        # List workspaces
        workspaces = await client.list_workspaces()
        
        # Trigger dataset refresh
        await client.trigger_refresh(workspace_id, dataset_id)
        
        # Deploy pipeline
        await client.deploy_pipeline(pipeline_id, source_stage=0)
        ```
    """
    
    def __init__(self, config: Optional[PowerBIConfig] = None):
        """Initialize Power BI client."""
        self.config = config or PowerBIConfig()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "PowerBIClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self
    
    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    # ========================================================================
    # Authentication
    # ========================================================================
    
    async def authenticate(self) -> str:
        """
        Authenticate with Azure AD and get access token.
        
        Returns:
            Access token string
            
        Raises:
            Exception: If authentication fails
        """
        # Check cache first
        cached = TokenCache.get()
        if cached:
            logger.debug("Using cached token")
            return cached
        
        token_url = f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token"
        
        if self.config.auth_mode == "service_principal":
            data = {
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "https://analysis.windows.net/powerbi/api/.default",
            }
        else:
            data = {
                "grant_type": "password",
                "client_id": self.config.client_id,
                "username": self.config.username,
                "password": self.config.password,
                "scope": "https://analysis.windows.net/powerbi/api/.default",
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        
        if response.status_code != 200:
            error = response.json()
            raise Exception(f"Authentication failed: {error.get('error_description', error)}")
        
        result = response.json()
        token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        
        TokenCache.set(token, expires_in)
        logger.info("Successfully authenticated with Power BI")
        
        return token
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        body: Optional[Dict] = None,
        use_fabric_api: bool = False,
    ) -> Dict[str, Any]:
        """Make authenticated API request."""
        token = await self.authenticate()
        
        base_url = self.config.fabric_api_base if use_fabric_api else self.config.api_base
        url = base_url + endpoint.lstrip("/")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout)
        
        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=body)
            elif method.upper() == "PATCH":
                response = await client.patch(url, headers=headers, json=body)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=body)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Handle empty response (204 No Content)
            if response.status_code == 204 or not response.content:
                return {"success": True}
            
            data = response.json()
            
            if response.status_code >= 400:
                error_msg = data.get("error", {}).get("message", str(data))
                raise Exception(f"API error ({response.status_code}): {error_msg}")
            
            return data
            
        finally:
            if not self._client:
                await client.aclose()
    
    # ========================================================================
    # Workspace Management
    # ========================================================================
    
    async def list_workspaces(
        self,
        top: int = 100,
        skip: int = 0,
        filter_: Optional[str] = None,
    ) -> List[Workspace]:
        """
        List all workspaces the user has access to.
        
        Args:
            top: Maximum number of results
            skip: Number of results to skip
            filter_: OData filter expression
            
        Returns:
            List of Workspace objects
        """
        endpoint = f"groups?$top={top}&$skip={skip}"
        if filter_:
            endpoint += f"&$filter={filter_}"
        
        data = await self._request("GET", endpoint)
        return [Workspace(**ws) for ws in data.get("value", [])]
    
    async def list_workspaces_admin(
        self,
        top: int = 100,
        filter_: Optional[str] = None,
        expand: str = "",
    ) -> List[Workspace]:
        """List workspaces as admin."""
        endpoint = f"admin/groups?$top={top}"
        if filter_:
            endpoint += f"&$filter={filter_}"
        if expand:
            endpoint += f"&$expand={expand}"
        
        data = await self._request("GET", endpoint)
        return [Workspace(**ws) for ws in data.get("value", [])]
    
    async def get_premium_workspaces(self, top: int = 100) -> List[Workspace]:
        """Get workspaces on Premium capacity."""
        return await self.list_workspaces_admin(top, "isOnDedicatedCapacity eq true")
    
    async def create_workspace(self, name: str) -> Workspace:
        """Create a new workspace."""
        data = await self._request("POST", "groups", {"name": name})
        return Workspace(**data)
    
    async def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace."""
        await self._request("DELETE", f"groups/{workspace_id}")
        return True
    
    async def assign_to_capacity(self, workspace_id: str, capacity_id: str) -> bool:
        """Assign workspace to Premium capacity."""
        await self._request(
            "POST",
            f"groups/{workspace_id}/AssignToCapacity",
            {"capacityId": capacity_id},
        )
        return True
    
    async def unassign_from_capacity(self, workspace_id: str) -> bool:
        """Unassign workspace from Premium capacity."""
        return await self.assign_to_capacity(
            workspace_id,
            "00000000-0000-0000-0000-000000000000"
        )
    
    async def set_large_dataset_format(self, workspace_id: str) -> bool:
        """Set workspace to Large Dataset storage format."""
        await self._request(
            "PATCH",
            f"groups/{workspace_id}",
            {"defaultDatasetStorageFormat": "Large"},
        )
        return True
    
    async def add_user_to_workspace(
        self,
        workspace_id: str,
        email: str,
        role: str = "Contributor",
        as_admin: bool = False,
    ) -> bool:
        """Add user to workspace."""
        endpoint = f"admin/groups/{workspace_id}/users" if as_admin else f"groups/{workspace_id}/users"
        await self._request("POST", endpoint, {
            "emailAddress": email,
            "groupUserAccessRight": role,
        })
        return True
    
    async def add_spn_to_workspace(
        self,
        workspace_id: str,
        object_id: str,
        role: str = "Contributor",
    ) -> bool:
        """Add Service Principal to workspace."""
        await self._request("POST", f"admin/groups/{workspace_id}/users", {
            "identifier": object_id,
            "groupUserAccessRight": role,
            "principalType": "App",
        })
        return True
    
    async def remove_user_from_workspace(self, workspace_id: str, email: str) -> bool:
        """Remove user from workspace."""
        await self._request("DELETE", f"admin/groups/{workspace_id}/users/{email}")
        return True
    
    async def generate_dtap_workspaces(
        self,
        base_name: str,
        capacity_id: str,
        stages: List[str] = ["dev", "tst", ""],
    ) -> Dict[str, Any]:
        """
        Generate DTAP workspaces (Dev/Test/Prod).
        
        Args:
            base_name: Base workspace name
            capacity_id: Premium capacity GUID
            stages: Stage suffixes
            
        Returns:
            Dict with created workspaces and errors
        """
        created = []
        errors = []
        
        for stage in stages:
            ws_name = f"{base_name}-{stage}" if stage else base_name
            
            try:
                workspace = await self.create_workspace(ws_name)
                await self.assign_to_capacity(workspace.id, capacity_id)
                await self.set_large_dataset_format(workspace.id)
                
                created.append({
                    "name": ws_name,
                    "id": workspace.id,
                    "stage": stage or "prod",
                })
            except Exception as e:
                errors.append({"stage": stage, "error": str(e)})
        
        return {"workspaces": created, "errors": errors}
    
    # ========================================================================
    # Deployment Pipeline Management
    # ========================================================================
    
    async def list_pipelines(self) -> List[Pipeline]:
        """List all deployment pipelines."""
        data = await self._request("GET", "pipelines")
        return [Pipeline(**p) for p in data.get("value", [])]
    
    async def list_pipelines_admin(self) -> List[Pipeline]:
        """List all pipelines as admin (with stages)."""
        data = await self._request("GET", "admin/pipelines?$expand=stages")
        return [Pipeline(**p) for p in data.get("value", [])]
    
    async def get_pipeline_users(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """Get pipeline users."""
        data = await self._request("GET", f"admin/pipelines/{pipeline_id}/users")
        return data.get("value", [])
    
    async def add_user_to_pipeline(
        self,
        pipeline_id: str,
        identifier: str,
        access_right: str = "Admin",
        principal_type: str = "User",
    ) -> bool:
        """Add user to deployment pipeline."""
        await self._request("POST", f"admin/pipelines/{pipeline_id}/users", {
            "identifier": identifier,
            "accessRight": access_right,
            "principalType": principal_type,
        })
        return True
    
    async def deploy_pipeline(
        self,
        pipeline_id: str,
        source_stage: int = 0,
        note: str = "",
        options: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger deployment pipeline (deploy all artifacts).
        
        Args:
            pipeline_id: Pipeline GUID
            source_stage: Source stage (0 = Dev, 1 = Test)
            note: Deployment note
            options: Deployment options
            
        Returns:
            Deployment result
        """
        body = {
            "sourceStageOrder": source_stage,
            "options": options or {
                "allowOverwriteArtifact": True,
                "allowCreateArtifact": True,
            },
        }
        
        if note:
            body["note"] = note
        
        return await self._request("POST", f"pipelines/{pipeline_id}/deployAll", body)
    
    # ========================================================================
    # Dataset Operations
    # ========================================================================
    
    async def list_datasets(self, workspace_id: str) -> List[Dataset]:
        """List datasets in a workspace."""
        data = await self._request("GET", f"groups/{workspace_id}/datasets")
        return [Dataset(**ds) for ds in data.get("value", [])]
    
    async def get_dataset_parameters(
        self,
        workspace_id: str,
        dataset_id: str,
    ) -> List[Dict[str, Any]]:
        """Get dataset parameters."""
        data = await self._request(
            "GET",
            f"groups/{workspace_id}/datasets/{dataset_id}/parameters"
        )
        return data.get("value", [])
    
    async def update_dataset_parameters(
        self,
        workspace_id: str,
        dataset_id: str,
        parameters: Dict[str, str],
    ) -> bool:
        """Update dataset parameters."""
        update_details = [
            {"name": name, "newValue": value}
            for name, value in parameters.items()
        ]
        
        await self._request(
            "POST",
            f"groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateParameters",
            {"updateDetails": update_details},
        )
        return True
    
    async def get_refresh_schedule(
        self,
        workspace_id: str,
        dataset_id: str,
    ) -> Dict[str, Any]:
        """Get dataset refresh schedule."""
        return await self._request(
            "GET",
            f"groups/{workspace_id}/datasets/{dataset_id}/refreshSchedule"
        )
    
    async def get_refresh_history(
        self,
        workspace_id: str,
        dataset_id: str,
        top: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get dataset refresh history."""
        data = await self._request(
            "GET",
            f"groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"
        )
        return data.get("value", [])
    
    async def trigger_refresh(
        self,
        workspace_id: str,
        dataset_id: str,
        notify_option: str = "NoNotification",
    ) -> bool:
        """Trigger dataset refresh."""
        await self._request(
            "POST",
            f"groups/{workspace_id}/datasets/{dataset_id}/refreshes",
            {"notifyOption": notify_option},
        )
        return True
    
    async def get_datasources(
        self,
        workspace_id: str,
        dataset_id: str,
    ) -> List[Dict[str, Any]]:
        """Get datasources for a dataset."""
        data = await self._request(
            "GET",
            f"groups/{workspace_id}/datasets/{dataset_id}/datasources"
        )
        return data.get("value", [])
    
    async def update_datasource(
        self,
        workspace_id: str,
        dataset_id: str,
        datasource_type: str,
        source_connection: Dict[str, str],
        target_connection: Dict[str, str],
    ) -> bool:
        """Update datasource connection (swap connections)."""
        await self._request(
            "POST",
            f"groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateDatasources",
            {
                "updateDetails": [{
                    "datasourceSelector": {
                        "datasourceType": datasource_type,
                        "connectionDetails": source_connection,
                    },
                    "connectionDetails": target_connection,
                }],
            },
        )
        return True
    
    async def rebind_report(
        self,
        workspace_id: str,
        report_id: str,
        target_dataset_id: str,
    ) -> bool:
        """Rebind report to different dataset."""
        await self._request(
            "POST",
            f"groups/{workspace_id}/reports/{report_id}/Rebind",
            {"datasetId": target_dataset_id},
        )
        return True
    
    # ========================================================================
    # Dataflow Operations
    # ========================================================================
    
    async def list_dataflows(self, workspace_id: str) -> List[Dataflow]:
        """List dataflows in a workspace."""
        data = await self._request("GET", f"groups/{workspace_id}/dataflows")
        return [Dataflow(**df) for df in data.get("value", [])]
    
    async def get_dataflow_definition(
        self,
        workspace_id: str,
        dataflow_id: str,
    ) -> Dict[str, Any]:
        """Get dataflow definition (model.json)."""
        return await self._request(
            "GET",
            f"groups/{workspace_id}/dataflows/{dataflow_id}"
        )
    
    async def get_dataflow_transactions(
        self,
        workspace_id: str,
        dataflow_id: str,
    ) -> List[Dict[str, Any]]:
        """Get dataflow refresh history (transactions)."""
        data = await self._request(
            "GET",
            f"groups/{workspace_id}/dataflows/{dataflow_id}/transactions"
        )
        return data.get("value", [])
    
    # ========================================================================
    # Report Operations
    # ========================================================================
    
    async def list_reports(self, workspace_id: str) -> List[Dict[str, Any]]:
        """List reports in a workspace."""
        data = await self._request("GET", f"groups/{workspace_id}/reports")
        return data.get("value", [])
    
    async def get_report(self, workspace_id: str, report_id: str) -> Dict[str, Any]:
        """Get report details."""
        return await self._request("GET", f"groups/{workspace_id}/reports/{report_id}")
    
    # ========================================================================
    # Capacity Management
    # ========================================================================
    
    async def list_capacities(self) -> List[Dict[str, Any]]:
        """List capacities."""
        data = await self._request("GET", "capacities")
        return data.get("value", [])
    
    # ========================================================================
    # Fabric Operations
    # ========================================================================
    
    async def fabric_list_workspaces(self) -> List[Dict[str, Any]]:
        """List Fabric workspaces."""
        data = await self._request("GET", "workspaces", use_fabric_api=True)
        return data.get("value", [])
    
    async def fabric_create_workspace(
        self,
        display_name: str,
        capacity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create Fabric workspace."""
        body = {"displayName": display_name}
        if capacity_id:
            body["capacityId"] = capacity_id
        
        return await self._request("POST", "workspaces", body, use_fabric_api=True)
    
    async def fabric_delete_workspace(self, workspace_id: str) -> bool:
        """Delete Fabric workspace."""
        await self._request("DELETE", f"workspaces/{workspace_id}", use_fabric_api=True)
        return True
    
    async def fabric_generate_training_workspaces(
        self,
        base_name: str,
        count: int,
        capacity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate training user workspaces (for workshops)."""
        created = []
        errors = []
        
        for i in range(1, count + 1):
            ws_name = f"{base_name} - User {i}"
            
            try:
                result = await self.fabric_create_workspace(ws_name, capacity_id)
                created.append({
                    "name": ws_name,
                    "id": result.get("id"),
                    "user_index": i,
                })
            except Exception as e:
                errors.append({
                    "name": ws_name,
                    "user_index": i,
                    "error": str(e),
                })
        
        return {"workspaces": created, "errors": errors}
    
    # ========================================================================
    # Bulk Operations
    # ========================================================================
    
    async def export_refresh_history(
        self,
        workspace_id: str,
        output_dir: str,
    ) -> Dict[str, str]:
        """
        Export all refresh history for a workspace to JSON files.
        
        Args:
            workspace_id: Workspace GUID
            output_dir: Output directory path
            
        Returns:
            Dict mapping data type to file path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        date_prefix = datetime.now().strftime("%Y%m%d_%H%M")
        results = {}
        
        # Dataset metadata
        datasets = await self.list_datasets(workspace_id)
        file_path = output_path / f"{date_prefix}_{workspace_id}_DatasetsMetadata.json"
        with open(file_path, "w") as f:
            json.dump([ds.model_dump() for ds in datasets], f, indent=2)
        results["datasets_metadata"] = str(file_path)
        
        # Dataset refresh history
        dataset_refreshes = []
        for ds in datasets:
            history = await self.get_refresh_history(workspace_id, ds.id)
            for r in history:
                r["datasetId"] = ds.id
                r["datasetName"] = ds.name
                dataset_refreshes.append(r)
        
        file_path = output_path / f"{date_prefix}_{workspace_id}_DatasetRefreshHistory.json"
        with open(file_path, "w") as f:
            json.dump(dataset_refreshes, f, indent=2)
        results["dataset_refresh_history"] = str(file_path)
        
        # Dataflow metadata
        dataflows = await self.list_dataflows(workspace_id)
        file_path = output_path / f"{date_prefix}_{workspace_id}_DataflowMetadata.json"
        with open(file_path, "w") as f:
            json.dump([df.model_dump() for df in dataflows], f, indent=2)
        results["dataflows_metadata"] = str(file_path)
        
        # Dataflow transactions
        dataflow_transactions = []
        for df in dataflows:
            trans = await self.get_dataflow_transactions(workspace_id, df.object_id)
            for t in trans:
                t["dataflowId"] = df.object_id
                t["dataflowName"] = df.name
                dataflow_transactions.append(t)
        
        file_path = output_path / f"{date_prefix}_{workspace_id}_DataflowRefreshHistory.json"
        with open(file_path, "w") as f:
            json.dump(dataflow_transactions, f, indent=2)
        results["dataflow_refresh_history"] = str(file_path)
        
        return results


# ============================================================================
# XMLA Endpoint Utilities
# ============================================================================

def get_xmla_endpoint(workspace_name: str, base: str = "powerbi://api.powerbi.com/v1.0/myorg/") -> str:
    """Build XMLA endpoint URL."""
    encoded_name = workspace_name.replace(" ", "%20")
    return base + encoded_name


def tmsl_backup(
    dataset_name: str,
    backup_file: str,
    apply_compression: bool = True,
) -> str:
    """Generate TMSL backup command."""
    return json.dumps({
        "backup": {
            "database": dataset_name,
            "file": backup_file,
            "allowOverwrite": False,
            "applyCompression": apply_compression,
        }
    }, indent=2)


def tmsl_refresh_table(
    dataset_name: str,
    table_name: str,
    refresh_type: str = "automatic",
) -> str:
    """Generate TMSL refresh command for specific table."""
    return json.dumps({
        "refresh": {
            "type": refresh_type,
            "objects": [{
                "database": dataset_name,
                "table": table_name,
            }],
        }
    }, indent=2)


def tmsl_assign_role(
    dataset_name: str,
    role_name: str,
    role_description: str,
    members: List[str],
) -> str:
    """Generate TMSL createOrReplace command for role membership."""
    return json.dumps({
        "createOrReplace": {
            "object": {
                "database": dataset_name,
                "role": role_name,
            },
            "role": {
                "name": role_name,
                "description": role_description,
                "modelPermission": "read",
                "members": [{"memberName": m} for m in members],
            },
        }
    }, indent=2)


# ============================================================================
# Synchronous Wrapper
# ============================================================================

class PowerBIClientSync:
    """
    Synchronous wrapper for PowerBIClient.
    
    Useful for scripts and non-async code.
    """
    
    def __init__(self, config: Optional[PowerBIConfig] = None):
        """Initialize sync client."""
        self.config = config or PowerBIConfig()
        self._token: Optional[str] = None
    
    def _request(
        self,
        method: str,
        endpoint: str,
        body: Optional[Dict] = None,
        use_fabric_api: bool = False,
    ) -> Dict[str, Any]:
        """Make authenticated API request (sync)."""
        import requests
        
        if not self._token:
            self._token = self._authenticate()
        
        base_url = self.config.fabric_api_base if use_fabric_api else self.config.api_base
        url = base_url + endpoint.lstrip("/")
        
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        
        response = requests.request(
            method,
            url,
            headers=headers,
            json=body,
            timeout=self.config.timeout,
        )
        
        if response.status_code == 204 or not response.content:
            return {"success": True}
        
        data = response.json()
        
        if response.status_code >= 400:
            error_msg = data.get("error", {}).get("message", str(data))
            raise Exception(f"API error ({response.status_code}): {error_msg}")
        
        return data
    
    def _authenticate(self) -> str:
        """Authenticate (sync)."""
        import requests
        
        cached = TokenCache.get()
        if cached:
            return cached
        
        token_url = f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token"
        
        if self.config.auth_mode == "service_principal":
            data = {
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "https://analysis.windows.net/powerbi/api/.default",
            }
        else:
            data = {
                "grant_type": "password",
                "client_id": self.config.client_id,
                "username": self.config.username,
                "password": self.config.password,
                "scope": "https://analysis.windows.net/powerbi/api/.default",
            }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.json()}")
        
        result = response.json()
        token = result["access_token"]
        TokenCache.set(token, result.get("expires_in", 3600))
        
        return token
    
    def list_workspaces(self, top: int = 100) -> List[Dict[str, Any]]:
        """List workspaces (sync)."""
        data = self._request("GET", f"groups?$top={top}")
        return data.get("value", [])
    
    def trigger_refresh(self, workspace_id: str, dataset_id: str) -> bool:
        """Trigger dataset refresh (sync)."""
        self._request(
            "POST",
            f"groups/{workspace_id}/datasets/{dataset_id}/refreshes",
            {"notifyOption": "NoNotification"},
        )
        return True
    
    def deploy_pipeline(self, pipeline_id: str, source_stage: int = 0, note: str = "") -> Dict:
        """Deploy pipeline (sync)."""
        body = {
            "sourceStageOrder": source_stage,
            "options": {"allowOverwriteArtifact": True, "allowCreateArtifact": True},
        }
        if note:
            body["note"] = note
        
        return self._request("POST", f"pipelines/{pipeline_id}/deployAll", body)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def main():
        """Example usage of PowerBIClient."""
        async with PowerBIClient() as client:
            # List workspaces
            workspaces = await client.list_workspaces()
            print(f"Found {len(workspaces)} workspaces")
            
            for ws in workspaces[:5]:
                print(f"  - {ws.name} ({ws.id})")
            
            # List capacities
            capacities = await client.list_capacities()
            print(f"\nFound {len(capacities)} capacities")
            
            # List pipelines
            pipelines = await client.list_pipelines()
            print(f"\nFound {len(pipelines)} deployment pipelines")
    
    asyncio.run(main())
