"""Service registry for dynamic service discovery."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service health status."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """Information about a registered service."""
    
    name: str
    url: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    version: str | None = None
    
    def update_status(self, status: ServiceStatus) -> None:
        """Update service status."""
        self.status = status
        self.last_check = datetime.now(timezone.utc)


class ServiceRegistry:
    """
    Registry for service discovery and health tracking.
    
    Allows services to register themselves and be discovered by other services.
    """
    
    def __init__(self):
        self._services: dict[str, ServiceInfo] = {}
        self._event_handlers: list[callable] = []
    
    def register(
        self, 
        name: str, 
        url: str, 
        metadata: dict[str, Any] | None = None,
        version: str | None = None,
    ) -> ServiceInfo:
        """
        Register a service.
        
        Args:
            name: Service name
            url: Service URL
            metadata: Optional metadata
            version: Service version
            
        Returns:
            ServiceInfo object
        """
        info = ServiceInfo(
            name=name,
            url=url,
            metadata=metadata or {},
            version=version,
        )
        self._services[name] = info
        logger.info(f"Registered service: {name} at {url}")
        self._notify_event("register", info)
        return info
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a service.
        
        Args:
            name: Service name
            
        Returns:
            True if service was unregistered, False if not found
        """
        if name in self._services:
            info = self._services.pop(name)
            logger.info(f"Unregistered service: {name}")
            self._notify_event("unregister", info)
            return True
        return False
    
    def get(self, name: str) -> ServiceInfo | None:
        """Get service info by name."""
        return self._services.get(name)
    
    def list_services(self, status: ServiceStatus | None = None) -> list[ServiceInfo]:
        """
        List all registered services.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of ServiceInfo objects
        """
        services = list(self._services.values())
        if status:
            services = [s for s in services if s.status == status]
        return services
    
    def update_status(self, name: str, status: ServiceStatus) -> bool:
        """
        Update service status.
        
        Args:
            name: Service name
            status: New status
            
        Returns:
            True if updated, False if service not found
        """
        if name in self._services:
            old_status = self._services[name].status
            self._services[name].update_status(status)
            if old_status != status:
                logger.info(f"Service {name} status changed: {old_status} -> {status}")
                self._notify_event("status_change", self._services[name])
            return True
        return False
    
    def on_event(self, handler: callable) -> None:
        """Register an event handler for registry events."""
        self._event_handlers.append(handler)
    
    def _notify_event(self, event_type: str, service: ServiceInfo) -> None:
        """Notify event handlers."""
        for handler in self._event_handlers:
            try:
                handler(event_type, service)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    def get_healthy_services(self) -> list[ServiceInfo]:
        """Get all healthy services."""
        return self.list_services(ServiceStatus.HEALTHY)
    
    def find_service(self, name: str) -> str | None:
        """
        Find a service URL by name.
        
        Args:
            name: Service name
            
        Returns:
            Service URL if found and healthy, None otherwise
        """
        service = self.get(name)
        if service and service.status == ServiceStatus.HEALTHY:
            return service.url
        return None
