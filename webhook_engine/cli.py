"""Command-line interface for the webhook engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import WebhookConfig, WebhookEndpoint, POWER_AUTOMATE_WEBHOOK
from .payload import PayloadBuilder, PayloadFormatter
from .engine import WebhookEngine, DeliveryResult, trigger_power_automate_sync
from .monitoring import LogFormat


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="webhook-engine",
        description="Comprehensive webhook delivery engine with retry, circuit breaker, and queue support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send to Power Automate
  webhook-engine send power_automate --data '{"event": "test"}'
  
  # Send to custom endpoint
  webhook-engine send myapi --data '{"hello": "world"}' --endpoint-url https://api.example.com/webhook
  
  # Send from file
  webhook-engine send power_automate --file payload.json
  
  # Batch send
  webhook-engine batch power_automate --file payloads.jsonl --concurrency 5
  
  # Start queue processor
  webhook-engine queue start --batch-size 50
  
  # Check status
  webhook-engine status
  
  # Health check
  webhook-engine health
        """,
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file (JSON)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output except errors",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output results as JSON",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Send command
    send_parser = subparsers.add_parser("send", help="Send a webhook")
    send_parser.add_argument(
        "endpoint",
        type=str,
        help="Endpoint name (use 'power_automate' for the configured PA webhook)",
    )
    send_parser.add_argument(
        "--data", "-d",
        type=str,
        help="JSON payload data",
    )
    send_parser.add_argument(
        "--file", "-f",
        type=str,
        help="Read payload from file",
    )
    send_parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read payload from stdin",
    )
    send_parser.add_argument(
        "--endpoint-url",
        type=str,
        help="URL for ad-hoc endpoint",
    )
    send_parser.add_argument(
        "--method",
        type=str,
        default="POST",
        choices=["GET", "POST", "PUT", "PATCH", "DELETE"],
        help="HTTP method",
    )
    send_parser.add_argument(
        "--header", "-H",
        action="append",
        default=[],
        help="Additional header (format: 'Name: Value')",
    )
    send_parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds",
    )
    send_parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable retry on failure",
    )
    send_parser.add_argument(
        "--no-circuit-breaker",
        action="store_true",
        help="Disable circuit breaker",
    )
    send_parser.add_argument(
        "--format",
        type=str,
        choices=["raw", "power_automate", "slack", "discord", "teams", "event"],
        default="raw",
        help="Payload format",
    )
    send_parser.add_argument(
        "--action",
        type=str,
        default="trigger",
        help="Action type for Power Automate format",
    )
    send_parser.add_argument(
        "--event-type",
        type=str,
        help="Event type for CloudEvents format",
    )
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Send batch webhooks")
    batch_parser.add_argument(
        "endpoint",
        type=str,
        help="Endpoint name",
    )
    batch_parser.add_argument(
        "--file", "-f",
        type=str,
        required=True,
        help="JSONL file with payloads (one JSON per line)",
    )
    batch_parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent requests",
    )
    batch_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without sending",
    )
    
    # Queue commands
    queue_parser = subparsers.add_parser("queue", help="Queue operations")
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command")
    
    queue_start = queue_subparsers.add_parser("start", help="Start queue processor")
    queue_start.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for processing",
    )
    queue_start.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Processing interval in seconds",
    )
    queue_start.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Concurrent requests",
    )
    
    queue_add = queue_subparsers.add_parser("add", help="Add message to queue")
    queue_add.add_argument("endpoint", type=str)
    queue_add.add_argument("--data", "-d", type=str)
    queue_add.add_argument("--file", "-f", type=str)
    queue_add.add_argument("--priority", type=int, default=0)
    
    queue_status = queue_subparsers.add_parser("status", help="Show queue status")
    queue_clear = queue_subparsers.add_parser("clear", help="Clear queue")
    
    queue_dlq = queue_subparsers.add_parser("dlq", help="Dead letter queue operations")
    queue_dlq.add_argument(
        "action",
        choices=["list", "retry", "purge"],
        help="DLQ action",
    )
    queue_dlq.add_argument(
        "--message-id",
        type=str,
        help="Message ID for retry",
    )
    
    # Endpoint commands
    endpoint_parser = subparsers.add_parser("endpoint", help="Endpoint management")
    endpoint_subparsers = endpoint_parser.add_subparsers(dest="endpoint_command")
    
    endpoint_list = endpoint_subparsers.add_parser("list", help="List endpoints")
    
    endpoint_add = endpoint_subparsers.add_parser("add", help="Add endpoint")
    endpoint_add.add_argument("name", type=str)
    endpoint_add.add_argument("url", type=str)
    endpoint_add.add_argument("--method", type=str, default="POST")
    endpoint_add.add_argument("--timeout", type=float, default=30.0)
    endpoint_add.add_argument("--auth-type", type=str)
    endpoint_add.add_argument("--auth-token", type=str)
    endpoint_add.add_argument("--save", action="store_true", help="Save to config")
    
    endpoint_remove = endpoint_subparsers.add_parser("remove", help="Remove endpoint")
    endpoint_remove.add_argument("name", type=str)
    
    endpoint_test = endpoint_subparsers.add_parser("test", help="Test endpoint")
    endpoint_test.add_argument("name", type=str)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show engine status")
    status_parser.add_argument(
        "--metrics",
        action="store_true",
        help="Include metrics",
    )
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Health check")
    
    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    config_show = config_subparsers.add_parser("show", help="Show current config")
    config_init = config_subparsers.add_parser("init", help="Initialize config file")
    config_init.add_argument(
        "--output", "-o",
        type=str,
        default="webhook-config.json",
        help="Output file path",
    )
    
    return parser


def parse_headers(header_list: list[str]) -> dict[str, str]:
    """Parse header arguments into dictionary."""
    headers = {}
    for h in header_list:
        if ": " in h:
            name, value = h.split(": ", 1)
            headers[name] = value
        elif ":" in h:
            name, value = h.split(":", 1)
            headers[name] = value.strip()
    return headers


def load_payload(
    data: Optional[str],
    file_path: Optional[str],
    stdin: bool,
) -> dict[str, Any]:
    """Load payload from various sources."""
    if stdin:
        content = sys.stdin.read()
    elif file_path:
        with open(file_path) as f:
            content = f.read()
    elif data:
        content = data
    else:
        return {}
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)


def format_payload(
    payload: dict[str, Any],
    format_type: str,
    action: str = "trigger",
    event_type: Optional[str] = None,
) -> dict[str, Any]:
    """Format payload according to specified format."""
    if format_type == "raw":
        return payload
    elif format_type == "power_automate":
        return PayloadFormatter.power_automate(payload, action)
    elif format_type == "slack":
        text = payload.get("text", json.dumps(payload))
        return PayloadFormatter.slack(text)
    elif format_type == "discord":
        content = payload.get("content", json.dumps(payload))
        return PayloadFormatter.discord(content=content)
    elif format_type == "teams":
        title = payload.get("title", "Webhook")
        text = payload.get("text", json.dumps(payload))
        return PayloadFormatter.teams(title, text)
    elif format_type == "event":
        return PayloadFormatter.generic_event(
            event_type or "webhook.triggered",
            payload,
        )
    return payload


def output_result(
    result: DeliveryResult,
    json_output: bool,
    verbose: bool,
) -> None:
    """Output the delivery result."""
    if json_output:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        if result.success:
            print(f"✓ Success ({result.elapsed_ms:.0f}ms)")
            if verbose and result.response:
                print(f"  Status: {result.response.status_code}")
                print(f"  Request ID: {result.response.request_id}")
                if result.response.body:
                    print(f"  Response: {result.response.body[:200]}")
        else:
            print(f"✗ Failed: {result.error}")
            if result.retries > 0:
                print(f"  Retries: {result.retries}")
            if verbose and result.response:
                print(f"  Status: {result.response.status_code}")
                print(f"  Body: {result.response.body[:500]}")


async def cmd_send(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute send command."""
    # Load payload
    payload = load_payload(args.data, args.file, args.stdin)
    
    if not payload:
        print("Error: No payload provided. Use --data, --file, or --stdin", file=sys.stderr)
        return 1
    
    # Format payload
    payload = format_payload(
        payload,
        args.format,
        action=args.action,
        event_type=args.event_type,
    )
    
    # Parse headers
    headers = parse_headers(args.header)
    
    # Create engine
    engine = WebhookEngine(
        config=config,
        enable_queue=False,
        log_level="DEBUG" if args.verbose else "WARNING",
    )
    
    # Add ad-hoc endpoint if URL provided
    if args.endpoint_url:
        engine.add_endpoint(WebhookEndpoint(
            name=args.endpoint,
            url=args.endpoint_url,
            method=args.method,
            timeout=args.timeout,
        ))
    
    try:
        result = await engine.send(
            args.endpoint,
            payload,
            headers=headers if headers else None,
            timeout=args.timeout,
            retry=not args.no_retry,
            use_circuit_breaker=not args.no_circuit_breaker,
        )
        
        output_result(result, args.json_output, args.verbose)
        return 0 if result.success else 1
    finally:
        await engine.close()


async def cmd_batch(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute batch command."""
    # Load payloads from JSONL file
    payloads = []
    with open(args.file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Error parsing line: {e}", file=sys.stderr)
                    continue
    
    if not payloads:
        print("No valid payloads found in file", file=sys.stderr)
        return 1
    
    print(f"Loaded {len(payloads)} payloads")
    
    if args.dry_run:
        for i, p in enumerate(payloads[:5]):
            print(f"  [{i+1}] {json.dumps(p)[:100]}...")
        if len(payloads) > 5:
            print(f"  ... and {len(payloads) - 5} more")
        return 0
    
    engine = WebhookEngine(
        config=config,
        enable_queue=False,
        log_level="WARNING",
    )
    
    try:
        results = await engine.send_batch(
            args.endpoint,
            payloads,
            concurrency=args.concurrency,
        )
        
        success = sum(1 for r in results if r.success)
        failed = len(results) - success
        
        print(f"\nResults: {success} succeeded, {failed} failed")
        
        if args.json_output:
            print(json.dumps([r.to_dict() for r in results], indent=2, default=str))
        
        return 0 if failed == 0 else 1
    finally:
        await engine.close()


async def cmd_queue(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute queue commands."""
    engine = WebhookEngine(config=config, enable_queue=True)
    
    try:
        if args.queue_command == "start":
            print(f"Starting queue processor (batch={args.batch_size}, interval={args.interval}s)")
            await engine.start_queue_processor(
                batch_size=args.batch_size,
                interval=args.interval,
                concurrency=args.concurrency,
            )
        
        elif args.queue_command == "add":
            payload = load_payload(args.data, args.file, False)
            if not payload:
                print("Error: No payload provided", file=sys.stderr)
                return 1
            
            message_id = engine.enqueue(
                args.endpoint,
                payload,
                priority=args.priority,
            )
            print(f"Enqueued: {message_id}")
        
        elif args.queue_command == "status":
            status = engine._queue.get_stats() if engine._queue else {}
            if args.json_output:
                print(json.dumps(status, indent=2, default=str))
            else:
                print(f"Queue size: {status.get('queue_size', 0)}")
                print(f"DLQ size: {status.get('dlq_size', 0)}")
                print(f"Processing: {status.get('processing', False)}")
        
        elif args.queue_command == "clear":
            if engine._queue:
                count = engine._queue.clear()
                print(f"Cleared {count} messages")
        
        elif args.queue_command == "dlq":
            if not engine._queue or not engine._queue.dlq:
                print("DLQ not enabled")
                return 1
            
            dlq = engine._queue.dlq
            
            if args.action == "list":
                messages = dlq.get_all()
                if args.json_output:
                    print(json.dumps([m.to_dict() for m in messages], indent=2, default=str))
                else:
                    for m in messages:
                        print(f"  {m.id}: {m.endpoint_name} - {m.last_error}")
                    print(f"\nTotal: {len(messages)}")
            
            elif args.action == "retry":
                if args.message_id:
                    msg = dlq.retry(args.message_id)
                    if msg:
                        engine._queue._backend.push(msg)
                        print(f"Retrying: {msg.id}")
                    else:
                        print(f"Message not found: {args.message_id}")
                else:
                    messages = dlq.retry_all()
                    for msg in messages:
                        engine._queue._backend.push(msg)
                    print(f"Retrying {len(messages)} messages")
            
            elif args.action == "purge":
                count = dlq.purge()
                print(f"Purged {count} messages")
        
        return 0
    finally:
        await engine.close()


def cmd_endpoint(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute endpoint commands."""
    if args.endpoint_command == "list":
        if args.json_output:
            print(json.dumps([ep.to_dict() for ep in config.endpoints.values()], indent=2))
        else:
            print("Configured endpoints:")
            for name, ep in config.endpoints.items():
                print(f"  {name}: {ep.url} ({ep.method})")
    
    elif args.endpoint_command == "add":
        endpoint = WebhookEndpoint(
            name=args.name,
            url=args.url,
            method=args.method,
            timeout=args.timeout,
            auth_type=args.auth_type,
            auth_config={"token": args.auth_token} if args.auth_token else {},
        )
        config.add_endpoint(endpoint)
        print(f"Added endpoint: {args.name}")
        
        if args.save:
            config.save("webhook-config.json")
            print("Saved to webhook-config.json")
    
    elif args.endpoint_command == "remove":
        if config.remove_endpoint(args.name):
            print(f"Removed: {args.name}")
        else:
            print(f"Not found: {args.name}")
            return 1
    
    elif args.endpoint_command == "test":
        print(f"Testing endpoint: {args.name}")
        result = trigger_power_automate_sync({"test": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        output_result(result, args.json_output, True)
        return 0 if result.success else 1
    
    return 0


async def cmd_status(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute status command."""
    engine = WebhookEngine(config=config, enable_queue=True, enable_logging=False)
    
    try:
        status = engine.get_status()
        
        if args.json_output:
            print(json.dumps(status, indent=2, default=str))
        else:
            print("Webhook Engine Status")
            print("=" * 40)
            print(f"Endpoints: {', '.join(status['endpoints'])}")
            print(f"Health: {'OK' if status['health']['healthy'] else 'DEGRADED'}")
            
            if status.get('queue'):
                q = status['queue']
                print(f"\nQueue:")
                print(f"  Size: {q.get('queue_size', 0)}")
                print(f"  DLQ: {q.get('dlq_size', 0)}")
            
            if args.metrics and status.get('metrics'):
                print(f"\nMetrics:")
                for key, value in status['metrics'].get('counters', {}).items():
                    print(f"  {key}: {value}")
        
        return 0
    finally:
        await engine.close()


def cmd_health(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute health command."""
    engine = WebhookEngine(config=config, enable_logging=False)
    health = engine.health_check()
    
    if args.json_output:
        print(json.dumps(health.to_dict(), indent=2))
    else:
        status = "✓ Healthy" if health.healthy else "✗ Unhealthy"
        print(status)
        for check, ok in health.checks.items():
            icon = "✓" if ok else "✗"
            print(f"  {icon} {check}")
    
    return 0 if health.healthy else 1


def cmd_config(args: argparse.Namespace, config: WebhookConfig) -> int:
    """Execute config commands."""
    if args.config_command == "show":
        print(json.dumps(config.to_dict(), indent=2))
    
    elif args.config_command == "init":
        # Create sample config
        sample = WebhookConfig()
        sample.add_endpoint(POWER_AUTOMATE_WEBHOOK)
        sample.add_endpoint(WebhookEndpoint(
            name="example",
            url="https://api.example.com/webhook",
            method="POST",
            timeout=30.0,
            retry_enabled=True,
        ))
        
        sample.save(args.output)
        print(f"Created config: {args.output}")
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Load config
    if args.config and Path(args.config).exists():
        config = WebhookConfig.from_file(args.config)
    else:
        config = WebhookConfig()
        config.add_endpoint(POWER_AUTOMATE_WEBHOOK)
    
    # Route to command handler
    try:
        if args.command == "send":
            return asyncio.run(cmd_send(args, config))
        elif args.command == "batch":
            return asyncio.run(cmd_batch(args, config))
        elif args.command == "queue":
            return asyncio.run(cmd_queue(args, config))
        elif args.command == "endpoint":
            return cmd_endpoint(args, config)
        elif args.command == "status":
            return asyncio.run(cmd_status(args, config))
        elif args.command == "health":
            return cmd_health(args, config)
        elif args.command == "config":
            return cmd_config(args, config)
        else:
            parser.print_help()
            return 0
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
