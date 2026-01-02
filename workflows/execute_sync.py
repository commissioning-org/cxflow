#!/usr/bin/env python3
"""
Execute comprehensive sync to Power Automate.

This script collects all memory, macros, metadata, and data
then pushes it to the configured Power Automate webhook.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflows.power_automate_sync import (
    CXFlowSyncWorkflow,
    SyncStatus,
    set_memory,
    register_macro,
    set_metadata,
    record_event,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def collect_workspace_data() -> dict:
    """Collect data from the workspace."""
    workspace_path = Path("/workspaces/codespaces-blank")
    
    data = {
        "workspace": str(workspace_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": {},
        "modules": [],
    }
    
    # Collect key files info
    key_dirs = ["jupyterbook", "superset", "workflows", "ml", "ingestion", "docs"]
    
    for dir_name in key_dirs:
        dir_path = workspace_path / dir_name
        if dir_path.exists():
            files = list(dir_path.rglob("*.py")) + list(dir_path.rglob("*.php"))
            data["files"][dir_name] = {
                "count": len(files),
                "files": [str(f.relative_to(workspace_path)) for f in files[:20]],
            }
            data["modules"].append(dir_name)
    
    return data


def setup_sample_data(workflow: CXFlowSyncWorkflow):
    """Set up sample memory, macros, and metadata."""
    
    # Memory entries
    workflow.memory.set(
        "session_id",
        "cxflow-session-" + datetime.now().strftime("%Y%m%d%H%M%S"),
        category="session",
        ttl_seconds=86400,
        tags=["active", "main"],
    )
    
    workflow.memory.set(
        "last_sync",
        datetime.now(timezone.utc).isoformat(),
        category="sync",
    )
    
    workflow.memory.set(
        "workspace_path",
        "/workspaces/codespaces-blank",
        category="config",
    )
    
    workflow.memory.set(
        "active_modules",
        ["jupyterbook", "superset", "workflows", "ml", "ingestion"],
        category="config",
    )
    
    workflow.memory.set(
        "build_status",
        {"html": "success", "pdf": "pending"},
        category="build",
    )
    
    # Macro definitions
    workflow.macros.register(
        name="daily_sync",
        description="Daily sync of all data to Power Automate",
        trigger="schedule",
        actions=[
            {"type": "collect", "source": "memory"},
            {"type": "collect", "source": "macros"},
            {"type": "collect", "source": "metadata"},
            {"type": "sync", "destination": "power_automate"},
        ],
        metadata={"schedule": "0 0 * * *"},  # Daily at midnight
    )
    
    workflow.macros.register(
        name="build_docs",
        description="Build documentation on commit",
        trigger="webhook",
        actions=[
            {"type": "execute", "command": "python -m jupyterbook.book_builder build ."},
            {"type": "notify", "channel": "teams"},
        ],
    )
    
    workflow.macros.register(
        name="refresh_superset",
        description="Refresh Superset datasets",
        trigger="schedule",
        actions=[
            {"type": "api_call", "endpoint": "/superset/datasets/refresh"},
            {"type": "log", "message": "Superset dataset refresh triggered"},
        ],
        metadata={"schedule": "0 6 * * *"},  # Daily at 6 AM
    )
    
    workflow.macros.register(
        name="ml_pipeline_run",
        description="Run ML pipeline on new data",
        trigger="event",
        actions=[
            {"type": "execute", "command": "python ml/app/main.py"},
            {"type": "sync", "destination": "power_automate"},
        ],
        metadata={"event_type": "data_ingestion_complete"},
    )
    
    # Metadata
    workflow.metadata.set(
        "repository",
        "cxflow",
        {
            "owner": "commissioning-org",
            "branch": "main",
            "url": "https://github.com/commissioning-org/cxflow",
            "description": "CXFlow - Commissioning Data Platform",
        },
    )
    
    workflow.metadata.set(
        "module",
        "jupyterbook",
        {
            "version": "1.0.0",
            "status": "active",
            "dependencies": ["pydantic", "aiohttp", "pyyaml"],
            "endpoints": ["/book/health", "/book/build", "/book/parse"],
        },
    )
    
    workflow.metadata.set(
        "module",
        "superset",
        {
            "version": "1.0.0",
            "status": "active",
            "dependencies": ["pydantic"],
            "endpoints": ["/superset/health", "/superset/dashboards", "/superset/datasets"],
        },
    )
    
    workflow.metadata.set(
        "module",
        "workflows",
        {
            "version": "1.0.0",
            "status": "active",
            "dependencies": ["aiohttp", "requests", "pydantic"],
            "webhook": "power_automate",
        },
    )
    
    workflow.metadata.set(
        "environment",
        "development",
        {
            "platform": "codespaces",
            "container": "ubuntu-24.04",
            "python": "3.x",
            "php": "8.x",
        },
    )
    
    # Record events
    workflow.record_event("sync_initiated", {
        "source": "execute_sync.py",
        "full_sync": True,
    })
    
    workflow.record_event("data_collected", {
        "memory_count": len(workflow.memory.get_all()),
        "macro_count": len(workflow.macros.list_all()),
    })


def main():
    """Execute the sync workflow."""
    print("=" * 60)
    print("CXFlow Power Automate Sync")
    print("=" * 60)
    print()
    
    # Initialize workflow
    print("📦 Initializing workflow...")
    workflow = CXFlowSyncWorkflow()
    
    # Setup sample data
    print("📝 Setting up data...")
    setup_sample_data(workflow)
    
    # Collect workspace data
    print("🔍 Collecting workspace data...")
    workspace_data = collect_workspace_data()
    
    print(f"   Found {len(workspace_data['modules'])} modules")
    for module in workspace_data['modules']:
        files = workspace_data['files'].get(module, {})
        print(f"   - {module}: {files.get('count', 0)} files")
    
    # Summary before sync
    print()
    print("📊 Data Summary:")
    print(f"   Memory entries: {len(workflow.memory.get_all())}")
    print(f"   Macros: {len(workflow.macros.list_all())}")
    print(f"   Metadata records: {len(workflow.metadata.export_for_sync())}")
    print()
    
    # Execute sync
    print("🚀 Syncing to Power Automate...")
    print(f"   Webhook: ...{workflow.webhook_url[-50:]}")
    print()
    
    result = workflow.sync_all(
        include_metrics=True,
        include_logs=False,
        custom_data=workspace_data,
    )
    
    # Results
    print()
    print("=" * 60)
    if result.status == SyncStatus.COMPLETED:
        print("✅ SYNC COMPLETED SUCCESSFULLY")
    else:
        print("❌ SYNC FAILED")
    print("=" * 60)
    print()
    print(f"Sync ID:      {result.sync_id}")
    print(f"Status:       {result.status.value}")
    print(f"Items sent:   {result.items_sent}")
    print(f"Items failed: {result.items_failed}")
    print(f"Duration:     {result.duration_ms}ms")
    print(f"Started:      {result.started_at}")
    print(f"Completed:    {result.completed_at}")
    
    if result.errors:
        print()
        print("Errors:")
        for error in result.errors:
            print(f"  - {error}")
    
    if result.response_data:
        print()
        print("Response:")
        print(json.dumps(result.response_data, indent=2, default=str)[:500])
    
    print()
    
    # Return exit code based on status
    return 0 if result.status == SyncStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
