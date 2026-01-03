"""API Gateway to unify access to all services."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx

from .config import CXFlowConfig
from .events import Event, EventBus
from .health import HealthMonitor
from .registry import ServiceRegistry

logger = logging.getLogger(__name__)


class APIGateway:
    """
    Unified API Gateway for all CXFlow services.
    
    Provides:
    - Single entry point for all services
    - Request routing
    - Load balancing
    - Health checks
    - Event bus integration
    """
    
    def __init__(
        self,
        config: CXFlowConfig,
        registry: ServiceRegistry,
        event_bus: EventBus,
        health_monitor: HealthMonitor,
    ):
        self.config = config
        self.registry = registry
        self.event_bus = event_bus
        self.health_monitor = health_monitor
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """Create the FastAPI application."""
        app = FastAPI(
            title="CXFlow API Gateway",
            version="2.0.0",
            description="Unified API gateway for all CXFlow services",
        )
        
        # Health endpoint
        @app.get("/health")
        async def health():
            """Gateway health check."""
            return {
                "ok": True,
                "version": "2.0.0",
                "gateway": "healthy",
            }
        
        # System health endpoint
        @app.get("/system/health")
        async def system_health():
            """Get health of all services."""
            return self.health_monitor.get_health_summary()
        
        # Service registry endpoint
        @app.get("/system/services")
        async def list_services():
            """List all registered services."""
            services = self.registry.list_services()
            return {
                "services": [
                    {
                        "name": s.name,
                        "url": s.url,
                        "status": s.status.value,
                        "version": s.version,
                        "last_check": s.last_check.isoformat() if s.last_check else None,
                    }
                    for s in services
                ]
            }
        
        # Event history endpoint
        @app.get("/system/events")
        async def event_history(topic: str | None = None, limit: int = 100):
            """Get event history."""
            events = self.event_bus.get_history(topic, limit)
            return {
                "events": [
                    {
                        "id": e.id,
                        "type": e.type,
                        "source": e.source,
                        "timestamp": e.timestamp.isoformat(),
                        "priority": e.priority.value,
                        "payload": e.payload,
                    }
                    for e in events
                ]
            }
        
        # Proxy endpoint for ML service
        @app.api_route("/ml/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def proxy_ml(request: Request, path: str):
            """Proxy requests to ML service."""
            return await self._proxy_request("ml", path, request)
        
        # Proxy endpoint for Webhook Engine
        @app.api_route("/webhook/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def proxy_webhook(request: Request, path: str):
            """Proxy requests to Webhook Engine."""
            return await self._proxy_request("webhook", path, request)
        
        # Proxy endpoint for Research Agent
        @app.api_route("/research/{path:path}", methods=["GET", "POST"])
        async def proxy_research(request: Request, path: str):
            """Proxy requests to Research Agent."""
            return await self._proxy_request("research", path, request)
        
        # Proxy endpoint for JupyterBook
        @app.api_route("/jupyterbook/{path:path}", methods=["GET", "POST"])
        async def proxy_jupyterbook(request: Request, path: str):
            """Proxy requests to JupyterBook."""
            return await self._proxy_request("jupyterbook", path, request)
        
        # Proxy endpoint for Superset
        @app.api_route("/superset/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def proxy_superset(request: Request, path: str):
            """Proxy requests to Superset."""
            return await self._proxy_request("superset", path, request)
        
        return app
    
    async def _proxy_request(self, service: str, path: str, request: Request) -> Any:
        """
        Proxy a request to a service.
        
        Args:
            service: Service name
            path: Request path
            request: FastAPI request
            
        Returns:
            Service response
        """
        # Find service URL
        service_url = self.registry.find_service(service)
        if not service_url:
            raise HTTPException(
                status_code=503,
                detail=f"Service {service} is not available"
            )
        
        # Build target URL
        url = f"{service_url}/{path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        
        # Get request body
        body = await request.body()
        
        # Publish event
        await self.event_bus.publish(Event(
            type=f"gateway.proxy.{service}",
            source="gateway",
            payload={
                "method": request.method,
                "path": path,
                "service": service,
            }
        ))
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=dict(request.headers),
                    content=body,
                )
                
                # Return response
                return JSONResponse(
                    content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"data": response.text},
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
        
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Service timeout")
        
        except Exception as e:
            logger.error(f"Proxy error for {service}/{path}: {e}")
            raise HTTPException(status_code=502, detail=f"Service error: {str(e)}")
    
    def run(self, host: str = "0.0.0.0", port: int | None = None) -> None:
        """
        Run the gateway.
        
        Args:
            host: Host to bind to
            port: Port to bind to (uses config if not specified)
        """
        import uvicorn
        
        port = port or self.config.gateway_port
        logger.info(f"Starting API Gateway on {host}:{port}")
        
        uvicorn.run(self.app, host=host, port=port)
