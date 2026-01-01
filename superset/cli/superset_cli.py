#!/usr/bin/env python3
"""
Superset CLI - Command-line interface for Apache Superset.

Usage:
    superset-cli dashboard list
    superset-cli dashboard get <id>
    superset-cli dashboard export <id> --output dashboard.zip
    superset-cli query execute <database_id> "SELECT * FROM table"
    superset-cli database list
    superset-cli database test <id>
"""

import argparse
import json
import os
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client import SupersetClient
from config import SupersetConfig


def get_client(args) -> SupersetClient:
    """Create Superset client from args or environment."""
    config = SupersetConfig(
        base_url=args.url or os.getenv("SUPERSET_URL", "http://localhost:8088"),
        username=args.username or os.getenv("SUPERSET_USERNAME", "admin"),
        password=args.password or os.getenv("SUPERSET_PASSWORD", "admin"),
    )
    return SupersetClient(config)


def format_output(data, format: str = "json"):
    """Format output data."""
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
    elif format == "table":
        # Simple table format
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                print("\t".join(headers))
                for row in data:
                    print("\t".join(str(row.get(h, "")) for h in headers))
        elif isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}")
    else:
        print(data)


# =============================================================================
# Dashboard Commands
# =============================================================================

def cmd_dashboard_list(args):
    """List all dashboards."""
    client = get_client(args)
    result = client.get_dashboards(page=args.page, page_size=args.limit)
    
    dashboards = result.get("result", [])
    if args.format == "table":
        for d in dashboards:
            print(f"{d['id']}\t{d.get('dashboard_title', 'Untitled')}\t{'Published' if d.get('published') else 'Draft'}")
    else:
        format_output(dashboards, args.format)


def cmd_dashboard_get(args):
    """Get dashboard details."""
    client = get_client(args)
    result = client.get_dashboard(args.id)
    format_output(result, args.format)


def cmd_dashboard_export(args):
    """Export dashboard to file."""
    client = get_client(args)
    data = client.export_dashboards([args.id])
    
    output = args.output or f"dashboard_{args.id}.zip"
    with open(output, "wb") as f:
        f.write(data)
    
    print(f"Exported to {output}")


def cmd_dashboard_create(args):
    """Create a new dashboard."""
    client = get_client(args)
    
    data = {
        "dashboard_title": args.title,
        "published": args.published,
    }
    
    if args.slug:
        data["slug"] = args.slug
    
    result = client.create_dashboard(data)
    format_output(result, args.format)


def cmd_dashboard_delete(args):
    """Delete a dashboard."""
    client = get_client(args)
    client.delete_dashboard(args.id)
    print(f"Dashboard {args.id} deleted")


# =============================================================================
# Database Commands
# =============================================================================

def cmd_database_list(args):
    """List all databases."""
    client = get_client(args)
    result = client.get_databases(page=args.page, page_size=args.limit)
    
    databases = result.get("result", [])
    if args.format == "table":
        for d in databases:
            print(f"{d['id']}\t{d.get('database_name', 'Unnamed')}\t{d.get('backend', '')}")
    else:
        format_output(databases, args.format)


def cmd_database_get(args):
    """Get database details."""
    client = get_client(args)
    result = client.get_database(args.id)
    format_output(result, args.format)


def cmd_database_test(args):
    """Test database connection."""
    client = get_client(args)
    
    if args.uri:
        result = client.test_database_connection({"sqlalchemy_uri": args.uri})
    else:
        db = client.get_database(args.id)
        result = client.test_database_connection({
            "sqlalchemy_uri": db.get("result", {}).get("sqlalchemy_uri", "")
        })
    
    if result.get("message") == "OK":
        print("✓ Connection successful")
    else:
        print(f"✗ Connection failed: {result.get('message', 'Unknown error')}")


def cmd_database_schemas(args):
    """List database schemas."""
    client = get_client(args)
    result = client.get_database_schemas(args.id)
    
    schemas = result.get("result", [])
    for schema in schemas:
        print(schema)


def cmd_database_tables(args):
    """List tables in a schema."""
    client = get_client(args)
    result = client.get_database_tables(args.id, args.schema)
    
    tables = result.get("result", [])
    for table in tables:
        name = table.get("value", table.get("table_name", ""))
        print(name)


# =============================================================================
# Query Commands
# =============================================================================

def cmd_query_execute(args):
    """Execute SQL query."""
    client = get_client(args)
    
    result = client.execute_sql({
        "database_id": args.database_id,
        "sql": args.sql,
        "schema": args.schema,
        "queryLimit": args.limit,
        "runAsync": args.async_,
    })
    
    if "data" in result:
        if args.format == "csv":
            import csv
            import io
            
            columns = result.get("columns", [])
            data = result.get("data", [])
            
            output = io.StringIO()
            if columns and data:
                headers = [c.get("name", c.get("column_name", "")) for c in columns]
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            
            print(output.getvalue())
        else:
            format_output(result.get("data", []), args.format)
    else:
        format_output(result, args.format)


def cmd_query_history(args):
    """Show query history."""
    client = get_client(args)
    result = client.get_queries(page=args.page, page_size=args.limit)
    
    queries = result.get("result", [])
    if args.format == "table":
        for q in queries:
            status = q.get("status", "unknown")
            sql = q.get("sql", "")[:50] + "..." if len(q.get("sql", "")) > 50 else q.get("sql", "")
            print(f"{q['id']}\t{status}\t{sql}")
    else:
        format_output(queries, args.format)


# =============================================================================
# Dataset Commands
# =============================================================================

def cmd_dataset_list(args):
    """List all datasets."""
    client = get_client(args)
    result = client.get_datasets(page=args.page, page_size=args.limit)
    
    datasets = result.get("result", [])
    if args.format == "table":
        for d in datasets:
            print(f"{d['id']}\t{d.get('table_name', 'Unnamed')}\t{d.get('schema', '')}")
    else:
        format_output(datasets, args.format)


def cmd_dataset_get(args):
    """Get dataset details."""
    client = get_client(args)
    result = client.get_dataset(args.id)
    format_output(result, args.format)


def cmd_dataset_refresh(args):
    """Refresh dataset columns."""
    client = get_client(args)
    result = client.refresh_dataset(args.id)
    print(f"Dataset {args.id} refreshed")


# =============================================================================
# Chart Commands
# =============================================================================

def cmd_chart_list(args):
    """List all charts."""
    client = get_client(args)
    result = client.get_charts(page=args.page, page_size=args.limit)
    
    charts = result.get("result", [])
    if args.format == "table":
        for c in charts:
            print(f"{c['id']}\t{c.get('slice_name', 'Unnamed')}\t{c.get('viz_type', '')}")
    else:
        format_output(charts, args.format)


def cmd_chart_get(args):
    """Get chart details."""
    client = get_client(args)
    result = client.get_chart(args.id)
    format_output(result, args.format)


# =============================================================================
# Report Commands
# =============================================================================

def cmd_report_list(args):
    """List all reports."""
    client = get_client(args)
    result = client.get_reports(page=args.page, page_size=args.limit)
    
    reports = result.get("result", [])
    if args.format == "table":
        for r in reports:
            active = "Active" if r.get("active") else "Inactive"
            print(f"{r['id']}\t{r.get('name', 'Unnamed')}\t{r.get('type', '')}\t{active}")
    else:
        format_output(reports, args.format)


# =============================================================================
# User Commands
# =============================================================================

def cmd_user_me(args):
    """Get current user info."""
    client = get_client(args)
    result = client.get_current_user()
    format_output(result, args.format)


def cmd_user_list(args):
    """List all users."""
    client = get_client(args)
    result = client.get_users(page=args.page, page_size=args.limit)
    
    users = result.get("result", [])
    if args.format == "table":
        for u in users:
            active = "Active" if u.get("active") else "Inactive"
            print(f"{u['id']}\t{u.get('username', '')}\t{u.get('email', '')}\t{active}")
    else:
        format_output(users, args.format)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Superset CLI - Command-line interface for Apache Superset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Global options
    parser.add_argument("--url", help="Superset URL (default: $SUPERSET_URL or http://localhost:8088)")
    parser.add_argument("--username", "-u", help="Username (default: $SUPERSET_USERNAME)")
    parser.add_argument("--password", "-p", help="Password (default: $SUPERSET_PASSWORD)")
    parser.add_argument("--format", "-f", choices=["json", "table", "csv"], default="table", help="Output format")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Dashboard commands
    dashboard_parser = subparsers.add_parser("dashboard", help="Dashboard operations")
    dashboard_sub = dashboard_parser.add_subparsers(dest="subcommand")
    
    dash_list = dashboard_sub.add_parser("list", help="List dashboards")
    dash_list.add_argument("--page", type=int, default=0)
    dash_list.add_argument("--limit", type=int, default=25)
    dash_list.set_defaults(func=cmd_dashboard_list)
    
    dash_get = dashboard_sub.add_parser("get", help="Get dashboard")
    dash_get.add_argument("id", type=int, help="Dashboard ID")
    dash_get.set_defaults(func=cmd_dashboard_get)
    
    dash_export = dashboard_sub.add_parser("export", help="Export dashboard")
    dash_export.add_argument("id", type=int, help="Dashboard ID")
    dash_export.add_argument("--output", "-o", help="Output file")
    dash_export.set_defaults(func=cmd_dashboard_export)
    
    dash_create = dashboard_sub.add_parser("create", help="Create dashboard")
    dash_create.add_argument("title", help="Dashboard title")
    dash_create.add_argument("--slug", help="Dashboard slug")
    dash_create.add_argument("--published", action="store_true", help="Publish immediately")
    dash_create.set_defaults(func=cmd_dashboard_create)
    
    dash_delete = dashboard_sub.add_parser("delete", help="Delete dashboard")
    dash_delete.add_argument("id", type=int, help="Dashboard ID")
    dash_delete.set_defaults(func=cmd_dashboard_delete)
    
    # Database commands
    db_parser = subparsers.add_parser("database", help="Database operations")
    db_sub = db_parser.add_subparsers(dest="subcommand")
    
    db_list = db_sub.add_parser("list", help="List databases")
    db_list.add_argument("--page", type=int, default=0)
    db_list.add_argument("--limit", type=int, default=25)
    db_list.set_defaults(func=cmd_database_list)
    
    db_get = db_sub.add_parser("get", help="Get database")
    db_get.add_argument("id", type=int, help="Database ID")
    db_get.set_defaults(func=cmd_database_get)
    
    db_test = db_sub.add_parser("test", help="Test connection")
    db_test.add_argument("id", type=int, nargs="?", help="Database ID")
    db_test.add_argument("--uri", help="SQLAlchemy URI to test")
    db_test.set_defaults(func=cmd_database_test)
    
    db_schemas = db_sub.add_parser("schemas", help="List schemas")
    db_schemas.add_argument("id", type=int, help="Database ID")
    db_schemas.set_defaults(func=cmd_database_schemas)
    
    db_tables = db_sub.add_parser("tables", help="List tables")
    db_tables.add_argument("id", type=int, help="Database ID")
    db_tables.add_argument("schema", help="Schema name")
    db_tables.set_defaults(func=cmd_database_tables)
    
    # Query commands
    query_parser = subparsers.add_parser("query", help="Query operations")
    query_sub = query_parser.add_subparsers(dest="subcommand")
    
    query_exec = query_sub.add_parser("execute", help="Execute SQL")
    query_exec.add_argument("database_id", type=int, help="Database ID")
    query_exec.add_argument("sql", help="SQL query")
    query_exec.add_argument("--schema", help="Schema name")
    query_exec.add_argument("--limit", type=int, default=1000)
    query_exec.add_argument("--async", dest="async_", action="store_true")
    query_exec.set_defaults(func=cmd_query_execute)
    
    query_history = query_sub.add_parser("history", help="Query history")
    query_history.add_argument("--page", type=int, default=0)
    query_history.add_argument("--limit", type=int, default=25)
    query_history.set_defaults(func=cmd_query_history)
    
    # Dataset commands
    ds_parser = subparsers.add_parser("dataset", help="Dataset operations")
    ds_sub = ds_parser.add_subparsers(dest="subcommand")
    
    ds_list = ds_sub.add_parser("list", help="List datasets")
    ds_list.add_argument("--page", type=int, default=0)
    ds_list.add_argument("--limit", type=int, default=25)
    ds_list.set_defaults(func=cmd_dataset_list)
    
    ds_get = ds_sub.add_parser("get", help="Get dataset")
    ds_get.add_argument("id", type=int, help="Dataset ID")
    ds_get.set_defaults(func=cmd_dataset_get)
    
    ds_refresh = ds_sub.add_parser("refresh", help="Refresh columns")
    ds_refresh.add_argument("id", type=int, help="Dataset ID")
    ds_refresh.set_defaults(func=cmd_dataset_refresh)
    
    # Chart commands
    chart_parser = subparsers.add_parser("chart", help="Chart operations")
    chart_sub = chart_parser.add_subparsers(dest="subcommand")
    
    chart_list = chart_sub.add_parser("list", help="List charts")
    chart_list.add_argument("--page", type=int, default=0)
    chart_list.add_argument("--limit", type=int, default=25)
    chart_list.set_defaults(func=cmd_chart_list)
    
    chart_get = chart_sub.add_parser("get", help="Get chart")
    chart_get.add_argument("id", type=int, help="Chart ID")
    chart_get.set_defaults(func=cmd_chart_get)
    
    # Report commands
    report_parser = subparsers.add_parser("report", help="Report operations")
    report_sub = report_parser.add_subparsers(dest="subcommand")
    
    report_list = report_sub.add_parser("list", help="List reports")
    report_list.add_argument("--page", type=int, default=0)
    report_list.add_argument("--limit", type=int, default=25)
    report_list.set_defaults(func=cmd_report_list)
    
    # User commands
    user_parser = subparsers.add_parser("user", help="User operations")
    user_sub = user_parser.add_subparsers(dest="subcommand")
    
    user_me = user_sub.add_parser("me", help="Current user")
    user_me.set_defaults(func=cmd_user_me)
    
    user_list = user_sub.add_parser("list", help="List users")
    user_list.add_argument("--page", type=int, default=0)
    user_list.add_argument("--limit", type=int, default=25)
    user_list.set_defaults(func=cmd_user_list)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Print subcommand help if no subcommand given
        if args.command == "dashboard":
            dashboard_parser.print_help()
        elif args.command == "database":
            db_parser.print_help()
        elif args.command == "query":
            query_parser.print_help()
        elif args.command == "dataset":
            ds_parser.print_help()
        elif args.command == "chart":
            chart_parser.print_help()
        elif args.command == "report":
            report_parser.print_help()
        elif args.command == "user":
            user_parser.print_help()


if __name__ == "__main__":
    main()
