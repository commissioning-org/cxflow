#!/usr/bin/env python3
"""
CLI for Knowledge Base Ingestion from Power Automate.

Usage:
    python -m ingestion.knowledge_base.cli ingest
    python -m ingestion.knowledge_base.cli ingest --paginated --page-size 50
    python -m ingestion.knowledge_base.cli list
    python -m ingestion.knowledge_base.cli health
    python -m ingestion.knowledge_base.cli clear
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import IngestionConfig
from .client import PowerAutomateClient
from .ingestor import KnowledgeBaseIngestor


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_ingest(args) -> int:
    """Run ingestion."""
    config = IngestionConfig()
    
    if args.storage_path:
        config.storage_path = Path(args.storage_path)
    
    ingestor = KnowledgeBaseIngestor(config)
    
    if args.paginated:
        result = ingestor.ingest_all(
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
    else:
        result = ingestor.ingest()
    
    print(f"\n{'='*50}")
    print("Ingestion Results")
    print(f"{'='*50}")
    print(f"Success:         {result.success}")
    print(f"Items Processed: {result.items_processed}")
    print(f"Items Stored:    {result.items_stored}")
    print(f"Items Failed:    {result.items_failed}")
    print(f"Duration:        {result.duration_seconds:.2f}s")
    
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for error in result.errors[:10]:
            print(f"  - {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more")
    
    if args.verbose and result.file_paths:
        print(f"\nFiles created ({len(result.file_paths)}):")
        for path in result.file_paths[:10]:
            print(f"  - {path}")
        if len(result.file_paths) > 10:
            print(f"  ... and {len(result.file_paths) - 10} more")
    
    return 0 if result.success else 1


def cmd_list(args) -> int:
    """List stored items."""
    config = IngestionConfig()
    
    if args.storage_path:
        config.storage_path = Path(args.storage_path)
    
    ingestor = KnowledgeBaseIngestor(config)
    items = ingestor.get_stored_items()
    
    print(f"Found {len(items)} items in knowledge base\n")
    
    if args.format == "json":
        print(json.dumps(items, indent=2, default=str))
    else:
        for i, item in enumerate(items[:args.limit]):
            if isinstance(item, dict):
                item_id = item.get("id", item.get("Id", f"item_{i}"))
                print(f"{i+1}. {item_id}")
                if args.verbose:
                    for key, value in list(item.items())[:5]:
                        print(f"   {key}: {str(value)[:100]}")
            else:
                print(f"{i+1}. {str(item)[:100]}")
    
    if len(items) > args.limit:
        print(f"\n... and {len(items) - args.limit} more items")
    
    return 0


def cmd_health(args) -> int:
    """Check Power Automate endpoint health."""
    config = IngestionConfig()
    client = PowerAutomateClient(config)
    
    print("Checking Power Automate endpoint...")
    print(f"URL: {config.webhook_url}")
    
    is_healthy = client.health_check()
    
    if is_healthy:
        print("✓ Endpoint is accessible")
        return 0
    else:
        print("✗ Endpoint is not accessible")
        return 1


def cmd_clear(args) -> int:
    """Clear stored items."""
    config = IngestionConfig()
    
    if args.storage_path:
        config.storage_path = Path(args.storage_path)
    
    if not args.force:
        response = input("Are you sure you want to clear all stored items? [y/N] ")
        if response.lower() != "y":
            print("Cancelled")
            return 0
    
    ingestor = KnowledgeBaseIngestor(config)
    count = ingestor.clear_storage(include_logs=args.include_logs)
    
    print(f"Deleted {count} files")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Base Ingestion from Power Automate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--storage-path",
        help="Override storage path",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Run ingestion")
    ingest_parser.add_argument(
        "--paginated",
        action="store_true",
        help="Use pagination",
    )
    ingest_parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Page size for pagination",
    )
    ingest_parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum pages to fetch",
    )
    ingest_parser.set_defaults(func=cmd_ingest)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List stored items")
    list_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum items to display",
    )
    list_parser.set_defaults(func=cmd_list)
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Check endpoint health")
    health_parser.set_defaults(func=cmd_health)
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear stored items")
    clear_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Skip confirmation",
    )
    clear_parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Also clear logs",
    )
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
