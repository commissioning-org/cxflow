"""Main CLI for CXFlow integrated system."""

import asyncio
import logging
import sys
from pathlib import Path

import click

from .config import CXFlowConfig
from .events import EventBus
from .gateway import APIGateway
from .health import HealthMonitor
from .registry import ServiceRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, debug):
    """CXFlow Integrated System CLI."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    ctx.ensure_object(dict)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", type=int, help="Port to bind to")
def gateway(host, port):
    """Start the API Gateway."""
    config = CXFlowConfig()
    registry = ServiceRegistry()
    event_bus = EventBus()
    health_monitor = HealthMonitor(config, registry)
    
    # Register services
    for service in config.get_enabled_services():
        registry.register(
            name=service.name,
            url=f"http://{service.host}:{service.port}",
        )
    
    # Start health monitor
    asyncio.run(health_monitor.start())
    
    # Create and run gateway
    gw = APIGateway(config, registry, event_bus, health_monitor)
    try:
        gw.run(host=host, port=port)
    finally:
        asyncio.run(health_monitor.stop())


@cli.command()
@click.option("--interval", type=int, default=30, help="Check interval in seconds")
def monitor(interval):
    """Run health monitoring."""
    config = CXFlowConfig()
    registry = ServiceRegistry()
    health_monitor = HealthMonitor(config, registry, check_interval=interval)
    
    # Register services
    for service in config.get_enabled_services():
        registry.register(
            name=service.name,
            url=f"http://{service.host}:{service.port}",
        )
    
    async def run():
        await health_monitor.start()
        try:
            # Run indefinitely
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await health_monitor.stop()
    
    asyncio.run(run())


@cli.command()
def services():
    """List all configured services."""
    config = CXFlowConfig()
    
    click.echo("\nConfigured Services:")
    click.echo("-" * 80)
    
    for service in config.get_all_services():
        status = "✓ Enabled" if service.enabled else "✗ Disabled"
        url = f"http://{service.host}:{service.port}"
        click.echo(f"{service.name:20} {status:12} {url}")
    
    click.echo("-" * 80)
    click.echo(f"Total: {len(config.get_all_services())} services")
    click.echo(f"Enabled: {len(config.get_enabled_services())} services")


@cli.command()
@click.argument("service")
async def check(service):
    """Check health of a specific service."""
    config = CXFlowConfig()
    registry = ServiceRegistry()
    health_monitor = HealthMonitor(config, registry)
    
    # Find service config
    service_config = None
    for svc in config.get_all_services():
        if svc.name == service:
            service_config = svc
            break
    
    if not service_config:
        click.echo(f"Error: Service '{service}' not found", err=True)
        sys.exit(1)
    
    # Check health
    click.echo(f"Checking health of {service}...")
    result = await health_monitor.check_service(service_config)
    
    click.echo(f"Status: {result.status.value}")
    if result.response_time_ms:
        click.echo(f"Response time: {result.response_time_ms:.2f}ms")
    if result.error:
        click.echo(f"Error: {result.error}")
    if result.details:
        click.echo(f"Details: {result.details}")


@cli.command()
def info():
    """Show system information."""
    config = CXFlowConfig()
    
    click.echo("\n=== CXFlow System Information ===\n")
    click.echo(f"Base Directory: {config.base_dir}")
    click.echo(f"Models Directory: {config.models_dir}")
    click.echo(f"Data Directory: {config.data_dir}")
    click.echo(f"\nGateway Port: {config.gateway_port}")
    click.echo(f"Gateway Enabled: {config.gateway_enabled}")
    click.echo(f"Event Bus Enabled: {config.event_bus_enabled}")
    click.echo(f"Event Bus Backend: {config.event_bus_backend}")
    
    click.echo(f"\n=== Enabled Services ({len(config.get_enabled_services())}) ===\n")
    for service in config.get_enabled_services():
        click.echo(f"  - {service.name} @ {service.host}:{service.port}")


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
