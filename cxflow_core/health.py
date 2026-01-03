"""Health monitoring for all services."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import CXFlowConfig, ServiceConfig
from .registry import ServiceRegistry, ServiceStatus

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    
    service: str
    status: ServiceStatus
    response_time_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HealthMonitor:
    """
    Monitor health of all services.
    
    Performs periodic health checks and updates the service registry.
    """
    
    def __init__(
        self,
        config: CXFlowConfig,
        registry: ServiceRegistry,
        check_interval: int = 30,
    ):
        """
        Initialize health monitor.
        
        Args:
            config: CXFlow configuration
            registry: Service registry
            check_interval: Seconds between health checks
        """
        self.config = config
        self.registry = registry
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def check_service(self, service: ServiceConfig) -> HealthCheckResult:
        """
        Check health of a single service.
        
        Args:
            service: Service configuration
            
        Returns:
            HealthCheckResult
        """
        url = f"http://{service.host}:{service.port}{service.health_endpoint}"
        start = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(timeout=service.timeout) as client:
                response = await client.get(url)
                elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                
                if response.status_code == 200:
                    try:
                        details = response.json()
                    except Exception:
                        details = {}
                    
                    return HealthCheckResult(
                        service=service.name,
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=elapsed_ms,
                        details=details,
                    )
                else:
                    return HealthCheckResult(
                        service=service.name,
                        status=ServiceStatus.UNHEALTHY,
                        response_time_ms=elapsed_ms,
                        error=f"HTTP {response.status_code}",
                    )
        
        except httpx.TimeoutException:
            return HealthCheckResult(
                service=service.name,
                status=ServiceStatus.UNHEALTHY,
                error="Timeout",
            )
        
        except Exception as e:
            return HealthCheckResult(
                service=service.name,
                status=ServiceStatus.UNHEALTHY,
                error=str(e),
            )
    
    async def check_all_services(self) -> list[HealthCheckResult]:
        """
        Check health of all enabled services.
        
        Returns:
            List of health check results
        """
        services = self.config.get_enabled_services()
        tasks = [self.check_service(s) for s in services]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update registry
        for result in results:
            if isinstance(result, HealthCheckResult):
                self.registry.update_status(result.service, result.status)
        
        return [r for r in results if isinstance(r, HealthCheckResult)]
    
    async def start(self) -> None:
        """Start the health monitor."""
        if self._running:
            logger.warning("Health monitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitor started (interval: {self.check_interval}s)")
    
    async def stop(self) -> None:
        """Stop the health monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                results = await self.check_all_services()
                
                # Log unhealthy services
                unhealthy = [r for r in results if r.status != ServiceStatus.HEALTHY]
                if unhealthy:
                    for result in unhealthy:
                        logger.warning(
                            f"Service {result.service} is {result.status.value}: {result.error}"
                        )
                
                await asyncio.sleep(self.check_interval)
            
            except asyncio.CancelledError:
                break
            
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.check_interval)
    
    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for all services."""
        services = self.registry.list_services()
        
        return {
            "total": len(services),
            "healthy": len([s for s in services if s.status == ServiceStatus.HEALTHY]),
            "degraded": len([s for s in services if s.status == ServiceStatus.DEGRADED]),
            "unhealthy": len([s for s in services if s.status == ServiceStatus.UNHEALTHY]),
            "unknown": len([s for s in services if s.status == ServiceStatus.UNKNOWN]),
            "services": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "url": s.url,
                    "last_check": s.last_check.isoformat() if s.last_check else None,
                }
                for s in services
            ],
        }
