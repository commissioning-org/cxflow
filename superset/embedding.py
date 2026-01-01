"""
Dashboard embedding for Apache Superset.

Provides embedding capabilities:
- Guest token generation
- Embedded dashboard management
- Iframe integration
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


@dataclass
class GuestTokenResource:
    """Resource configuration for guest tokens."""
    type: str  # "dashboard" or "chart"
    id: str
    rls: Optional[List[Dict[str, str]]] = None  # Row-level security clauses
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type, "id": self.id}
        if self.rls:
            result["rls"] = self.rls
        return result


@dataclass
class GuestToken:
    """Represents a guest token for embedded dashboards."""
    token: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_in: int = 300  # seconds
    
    @property
    def expires_at(self) -> datetime:
        return self.created_at + timedelta(seconds=self.expires_in)
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at
    
    @property
    def remaining_seconds(self) -> int:
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))


@dataclass
class EmbeddedDashboard:
    """Represents an embedded dashboard configuration."""
    dashboard_id: str
    uuid: str
    allowed_domains: List[str] = field(default_factory=list)
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> EmbeddedDashboard:
        """Create from API response."""
        result = data.get("result", data)
        return cls(
            dashboard_id=str(result.get("dashboard_id", "")),
            uuid=result.get("uuid", ""),
            allowed_domains=result.get("allowed_domains", []),
        )


class EmbeddingManager:
    """
    High-level embedding management.
    
    Usage:
        manager = EmbeddingManager(client, superset_url="https://superset.example.com")
        
        # Configure dashboard for embedding
        embedded = manager.enable_embedding(dashboard_id=1)
        
        # Generate guest token
        token = manager.create_guest_token(
            resources=[
                GuestTokenResource(type="dashboard", id="1")
            ],
            user={"username": "embed_user"},
        )
        
        # Get embed URL
        url = manager.get_embed_url(
            dashboard_id=1,
            token=token.token,
        )
    """
    
    def __init__(
        self,
        client: SupersetClient,
        superset_url: Optional[str] = None,
    ):
        self.client = client
        self.superset_url = superset_url or client.base_url.rstrip("/api/v1").rstrip("/")
    
    def enable_embedding(
        self,
        dashboard_id: int,
        allowed_domains: Optional[List[str]] = None,
    ) -> EmbeddedDashboard:
        """Enable embedding for a dashboard."""
        result = self.client.enable_dashboard_embedding(
            dashboard_id,
            allowed_domains=allowed_domains or [],
        )
        return EmbeddedDashboard.from_api(result)
    
    def disable_embedding(self, dashboard_id: int) -> bool:
        """Disable embedding for a dashboard."""
        try:
            self.client.disable_dashboard_embedding(dashboard_id)
            return True
        except Exception as e:
            logger.error(f"Failed to disable embedding for dashboard {dashboard_id}: {e}")
            return False
    
    def get_embedded_config(self, dashboard_id: int) -> Optional[EmbeddedDashboard]:
        """Get embedding configuration for a dashboard."""
        try:
            result = self.client.get_dashboard_embedded(dashboard_id)
            return EmbeddedDashboard.from_api(result)
        except Exception:
            return None
    
    def create_guest_token(
        self,
        resources: List[GuestTokenResource],
        user: Optional[Dict[str, Any]] = None,
        rls: Optional[List[Dict[str, str]]] = None,
    ) -> GuestToken:
        """
        Create a guest token for embedded dashboards.
        
        Args:
            resources: List of resources to grant access to
            user: User context for the guest token
            rls: Row-level security clauses to apply
        """
        payload = {
            "resources": [r.to_dict() for r in resources],
            "user": user or {},
            "rls": rls or [],
        }
        
        result = self.client.create_guest_token(payload)
        
        return GuestToken(
            token=result.get("token", ""),
            expires_in=result.get("exp", 300),
        )
    
    def refresh_guest_token(
        self,
        resources: List[GuestTokenResource],
        user: Optional[Dict[str, Any]] = None,
        rls: Optional[List[Dict[str, str]]] = None,
    ) -> GuestToken:
        """Refresh/regenerate a guest token."""
        return self.create_guest_token(resources, user, rls)
    
    def get_embed_url(
        self,
        dashboard_id: int,
        token: Optional[str] = None,
        standalone: bool = True,
        show_title: bool = True,
        show_filters: bool = True,
        expand_filters: bool = False,
        preselect_filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate embed URL for a dashboard.
        
        Args:
            dashboard_id: Dashboard ID to embed
            token: Guest token (if using guest token auth)
            standalone: Hide Superset navigation
            show_title: Show dashboard title
            show_filters: Show filter bar
            expand_filters: Expand filter panel by default
            preselect_filters: Pre-selected filter values
        """
        params = {}
        
        if standalone:
            standalone_mode = 1
            if not show_title:
                standalone_mode = 2
            if not show_filters:
                standalone_mode = 3
            params["standalone"] = standalone_mode
        
        if expand_filters:
            params["expand_filters"] = "true"
        
        if preselect_filters:
            params["preselect_filters"] = json.dumps(preselect_filters)
        
        base_url = f"{self.superset_url}/superset/dashboard/{dashboard_id}/"
        
        if params:
            base_url = f"{base_url}?{urlencode(params)}"
        
        return base_url
    
    def get_embedded_sdk_url(
        self,
        dashboard_id: int,
        embedded_id: str,
        standalone: int = 1,
    ) -> str:
        """Get URL for Superset Embedded SDK."""
        return f"{self.superset_url}/embedded/{embedded_id}?standalone={standalone}"
    
    def generate_iframe_html(
        self,
        dashboard_id: int,
        token: Optional[str] = None,
        width: str = "100%",
        height: str = "600px",
        standalone: bool = True,
        show_title: bool = True,
        show_filters: bool = True,
    ) -> str:
        """Generate HTML iframe code for embedding."""
        url = self.get_embed_url(
            dashboard_id=dashboard_id,
            token=token,
            standalone=standalone,
            show_title=show_title,
            show_filters=show_filters,
        )
        
        return f'''<iframe
    src="{url}"
    width="{width}"
    height="{height}"
    frameborder="0"
    allowfullscreen
></iframe>'''
    
    def generate_sdk_code(
        self,
        dashboard_id: str,
        domain: str,
        container_id: str = "superset-container",
        fetch_guest_token_path: str = "/api/guest-token",
    ) -> str:
        """
        Generate JavaScript code for Superset Embedded SDK.
        
        Returns code snippet that can be added to a web page.
        """
        return f'''import {{ embedDashboard }} from "@superset-ui/embedded-sdk";

async function fetchGuestToken() {{
    const response = await fetch("{fetch_guest_token_path}");
    const data = await response.json();
    return data.token;
}}

embedDashboard({{
    id: "{dashboard_id}",
    supersetDomain: "{domain}",
    mountPoint: document.getElementById("{container_id}"),
    fetchGuestToken: fetchGuestToken,
    dashboardUiConfig: {{
        hideTitle: false,
        hideChartControls: false,
        hideTab: false,
    }},
}});'''


def generate_signed_url(
    base_url: str,
    dashboard_id: int,
    secret_key: str,
    expires_in: int = 3600,
    user_id: Optional[str] = None,
) -> str:
    """
    Generate a signed URL for dashboard access.
    
    This is useful for custom authentication flows where you want
    to verify the URL hasn't been tampered with.
    """
    expires = int(time.time()) + expires_in
    
    data = f"{dashboard_id}:{expires}"
    if user_id:
        data = f"{data}:{user_id}"
    
    signature = hmac.new(
        secret_key.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    
    params = {
        "expires": expires,
        "signature": signature,
    }
    
    if user_id:
        params["user_id"] = user_id
    
    return f"{base_url}/superset/dashboard/{dashboard_id}/?{urlencode(params)}"
