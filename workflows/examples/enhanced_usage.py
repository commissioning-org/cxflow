#!/usr/bin/env python3
"""
Enhanced CXFlow Usage Examples

This script demonstrates all the new enhanced capabilities.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workflows.cxflow_enhanced import (
    EnhancedMemoryManager,
    MacroExecutionEngine,
    MacroTemplateLibrary,
    AuditLogger,
    ValidationSchema,
    MemoryQuery,
    QueryOperator,
    AggregateFunction,
)


def demo_enhanced_memory():
    """Demonstrate enhanced memory capabilities."""
    print("=" * 60)
    print("Enhanced Memory Manager Demo")
    print("=" * 60)
    print()
    
    # Initialize with versioning and encryption
    manager = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
        enable_versioning=True,
        enable_encryption=False,  # Set to True to enable encryption
    )
    
    # 1. Basic operations with enhanced features
    print("1. Setting memory with enhanced features...")
    manager.set(
        "user_config",
        {"theme": "dark", "language": "en", "notifications": True},
        category="config",
        tags=["user", "preferences"],
        metadata={"priority": 5, "sensitive": False},
        user="demo_user",
        comment="Initial user configuration"
    )
    
    manager.set(
        "api_credentials",
        {"api_key": "secret123", "endpoint": "https://api.example.com"},
        category="secrets",
        tags=["api", "credentials"],
        metadata={"priority": 10, "sensitive": True},
        user="demo_user",
        comment="API credentials"
    )
    
    manager.set(
        "cache_stats",
        {"hits": 150, "misses": 20, "ratio": 0.88},
        category="metrics",
        tags=["performance", "cache"],
        metadata={"priority": 3},
        user="system",
        ttl_seconds=3600  # Expires in 1 hour
    )
    
    print("   ✅ Set 3 memory entries\n")
    
    # 2. Advanced querying
    print("2. Advanced querying...")
    
    # Query by category and priority
    query = MemoryQuery()
    query.with_category("config")
    query.add_filter("metadata.priority", QueryOperator.GTE, 5)
    results = manager.query(query)
    print(f"   Config entries with priority >= 5: {len(results)}")
    
    # Query with tags
    query2 = MemoryQuery()
    query2.with_tags(["performance"])
    results2 = manager.query(query2)
    print(f"   Performance tagged entries: {len(results2)}")
    
    # Complex query with sorting and pagination
    query3 = MemoryQuery()
    query3.add_filter("metadata.priority", QueryOperator.GT, 0)
    query3.sort("metadata.priority", desc=True)
    query3.paginate(limit=2)
    results3 = manager.query(query3)
    print(f"   Top 2 entries by priority: {len(results3)}\n")
    
    # 3. Full-text search
    print("3. Full-text search...")
    search_results = manager.search("api", fields=["key", "value", "tags"])
    print(f"   Found {len(search_results)} entries containing 'api'\n")
    
    # 4. Aggregations
    print("4. Aggregations...")
    count = manager.aggregate("key", AggregateFunction.COUNT)
    print(f"   Total entries: {count}")
    
    avg_priority = manager.aggregate("metadata.priority", AggregateFunction.AVG)
    print(f"   Average priority: {avg_priority:.2f}")
    
    max_priority = manager.aggregate("metadata.priority", AggregateFunction.MAX)
    print(f"   Max priority: {max_priority}\n")
    
    # 5. Versioning and history
    print("5. Versioning and history...")
    
    # Update an entry
    manager.set(
        "user_config",
        {"theme": "light", "language": "en", "notifications": False},
        category="config",
        tags=["user", "preferences"],
        user="demo_user",
        comment="Changed theme to light"
    )
    
    # Get history
    history = manager.get_history("user_config")
    print(f"   user_config has {len(history)} versions:")
    for v in history:
        print(f"     v{v.version}: {v.operation} at {v.timestamp[:19]} - {v.comment}")
    
    # Rollback
    print("\n   Rolling back to version 1...")
    manager.rollback("user_config", 1)
    entry = manager.get("user_config")
    print(f"   Current theme: {entry['value']['theme']}\n")
    
    # 6. Batch operations
    print("6. Batch operations...")
    batch_entries = [
        {"key": f"item_{i}", "value": f"value_{i}", "category": "batch", "tags": ["batch"]}
        for i in range(5)
    ]
    created_keys = manager.batch_set(batch_entries, user="batch_user")
    print(f"   Created {len(created_keys)} entries in batch")
    
    deleted_count = manager.batch_delete(created_keys[:3], user="batch_user")
    print(f"   Deleted {deleted_count} entries in batch\n")
    
    # 7. Export and import
    print("7. Export and import...")
    export_path = Path("/tmp/cxflow_demo/export.json")
    export_path.parent.mkdir(parents=True, exist_ok=True)
    manager.export_to_file(export_path, include_versions=True)
    print(f"   ✅ Exported to {export_path}\n")


def demo_macro_execution():
    """Demonstrate macro execution engine."""
    print("=" * 60)
    print("Macro Execution Engine Demo")
    print("=" * 60)
    print()
    
    # Initialize
    memory_manager = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
        enable_versioning=True,
    )
    engine = MacroExecutionEngine(memory_manager)
    
    # 1. Simple macro
    print("1. Executing simple macro...")
    simple_macro = {
        "name": "hello_world",
        "description": "Simple hello world macro",
        "trigger": "manual",
        "actions": [
            {"type": "log", "message": "Hello from CXFlow!"},
            {"type": "set_memory", "key": "last_execution", "value": "hello_world"},
        ]
    }
    
    execution = engine.execute_macro(simple_macro)
    print(f"   Status: {execution.status.value}")
    print(f"   Steps completed: {execution.steps_completed}/{execution.steps_total}")
    print(f"   Duration: {execution.duration_ms}ms\n")
    
    # 2. Macro with conditionals
    print("2. Executing macro with conditionals...")
    conditional_macro = {
        "name": "conditional_test",
        "description": "Test conditional logic",
        "trigger": "manual",
        "actions": [
            {
                "type": "condition",
                "if": "True",  # Simple condition
                "then": [
                    {"type": "log", "message": "Condition was true!"},
                    {"type": "set_memory", "key": "condition_result", "value": "passed"}
                ],
                "else": [
                    {"type": "log", "message": "Condition was false!"}
                ]
            }
        ]
    }
    
    execution2 = engine.execute_macro(conditional_macro, context={"value": 15})
    print(f"   Status: {execution2.status.value}")
    print(f"   Duration: {execution2.duration_ms}ms\n")
    
    # 3. Macro with loops
    print("3. Executing macro with loops...")
    loop_macro = {
        "name": "loop_test",
        "description": "Test loop logic",
        "trigger": "manual",
        "actions": [
            {
                "type": "loop",
                "items": ["apple", "banana", "cherry"],
                "as": "fruit",
                "actions": [
                    {"type": "log", "message": "Processing {{fruit}}"},
                ]
            }
        ]
    }
    
    execution3 = engine.execute_macro(loop_macro)
    print(f"   Status: {execution3.status.value}")
    print(f"   Iterations: {execution3.results.get('step_0', {}).get('iterations', 0)}\n")
    
    # 4. Macro with transformations
    print("4. Executing macro with transformations...")
    transform_macro = {
        "name": "transform_test",
        "description": "Test data transformations",
        "trigger": "manual",
        "actions": [
            {
                "type": "transform",
                "input": "hello world",
                "operation": "uppercase",
                "store_as": "upper_text"
            },
            {
                "type": "log",
                "message": "Transformed: {{upper_text}}"
            }
        ]
    }
    
    execution4 = engine.execute_macro(transform_macro, context={})
    print(f"   Status: {execution4.status.value}")
    print(f"   Result: {execution4.results.get('step_0', {}).get('result')}\n")
    
    # 5. Dry run
    print("5. Dry run (validation without execution)...")
    execution5 = engine.execute_macro(simple_macro, dry_run=True)
    print(f"   Status: {execution5.status.value}")
    print(f"   Would execute: {execution5.results.get('dry_run')}\n")
    
    # 6. View execution history
    print("6. Execution history...")
    history = engine.get_execution_history(limit=5)
    print(f"   Total executions: {len(history)}")
    for exec_record in history:
        print(f"     {exec_record.macro_name}: {exec_record.status.value} ({exec_record.duration_ms}ms)")
    print()


def demo_macro_templates():
    """Demonstrate macro templates."""
    print("=" * 60)
    print("Macro Templates Demo")
    print("=" * 60)
    print()
    
    # 1. List available templates
    print("1. Available templates:")
    templates = MacroTemplateLibrary.get_templates()
    for template in templates:
        print(f"   - {template.name}: {template.description}")
        print(f"     Category: {template.category}")
        print(f"     Parameters: {[p['name'] for p in template.parameters]}")
    print()
    
    # 2. Create macro from template
    print("2. Creating macro from template...")
    macro_def = MacroTemplateLibrary.create_from_template(
        "scheduled_sync",
        {
            "source": "metrics",
            "destination": "power_automate",
            "schedule": "0 */6 * * *"
        }
    )
    print(f"   Created macro: {macro_def['name']}")
    print(f"   Actions: {len(macro_def['actions'])}")
    print()
    
    # 3. Validate macro
    print("3. Validating macro...")
    is_valid, errors = ValidationSchema.validate_macro(macro_def)
    if is_valid:
        print("   ✅ Macro is valid")
    else:
        print(f"   ❌ Validation errors: {errors}")
    print()
    
    # 4. Test invalid macro
    print("4. Testing invalid macro...")
    invalid_macro = {"name": "test"}  # Missing required fields
    is_valid2, errors2 = ValidationSchema.validate_macro(invalid_macro)
    if not is_valid2:
        print(f"   ❌ Expected validation errors:")
        for error in errors2:
            print(f"      - {error}")
    print()


def demo_audit_logging():
    """Demonstrate audit logging."""
    print("=" * 60)
    print("Audit Logging Demo")
    print("=" * 60)
    print()
    
    # Initialize audit logger
    audit = AuditLogger(storage_path=Path("/tmp/cxflow_demo/audit"))
    
    # 1. Log various operations
    print("1. Logging operations...")
    audit.log("read", "memory", "user_config", user="demo_user", success=True)
    audit.log("write", "memory", "api_key", user="admin", success=True)
    audit.log("delete", "macro", "old_macro", user="admin", success=True)
    audit.log("execute", "macro", "daily_sync", user="system", success=False, error="Connection timeout")
    print("   ✅ Logged 4 operations\n")
    
    # 2. Query audit logs
    print("2. Querying audit logs...")
    
    # All operations
    all_logs = audit.query_logs(limit=10)
    print(f"   Total logs: {len(all_logs)}")
    
    # Failed operations
    failed_logs = audit.query_logs(success=False)
    print(f"   Failed operations: {len(failed_logs)}")
    if failed_logs:
        for log in failed_logs:
            print(f"     - {log.operation} on {log.entity_type}:{log.entity_id}: {log.error}")
    
    # Operations by user
    admin_logs = audit.query_logs(user="admin", limit=5)
    print(f"   Admin operations: {len(admin_logs)}")
    
    # Recent operations (last hour)
    since = datetime.now() - timedelta(hours=1)
    recent_logs = audit.query_logs(since=since)
    print(f"   Operations in last hour: {len(recent_logs)}")
    print()


def demo_complete_workflow():
    """Demonstrate a complete workflow using all features."""
    print("=" * 60)
    print("Complete Workflow Demo")
    print("=" * 60)
    print()
    
    # Initialize all components
    memory = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
        enable_versioning=True,
    )
    engine = MacroExecutionEngine(memory)
    audit = AuditLogger(storage_path=Path("/tmp/cxflow_demo/audit"))
    
    print("1. Setting up data...")
    # Store some data
    memory.set(
        "project_metrics",
        {"builds": 150, "tests": 1200, "deployments": 45},
        category="metrics",
        tags=["project", "ci/cd"],
        user="system"
    )
    
    memory.set(
        "alert_threshold",
        {"error_count": 10, "response_time": 500},
        category="config",
        tags=["alerts", "monitoring"],
        user="admin"
    )
    
    audit.log("write", "memory", "project_metrics", user="system", success=True)
    audit.log("write", "memory", "alert_threshold", user="admin", success=True)
    print("   ✅ Data setup complete\n")
    
    print("2. Executing monitoring macro...")
    # Create and execute a monitoring macro
    monitoring_macro = MacroTemplateLibrary.create_from_template(
        "conditional_notification",
        {
            "condition_field": "error_count",
            "threshold": 5,
            "channel": "slack"
        }
    )
    
    execution = engine.execute_macro(
        monitoring_macro,
        context={"error_count": 12}  # Exceeds threshold
    )
    
    audit.log(
        "execute",
        "macro",
        monitoring_macro["name"],
        user="system",
        success=(execution.status.value == "completed"),
        metadata={"duration_ms": execution.duration_ms}
    )
    
    print(f"   Status: {execution.status.value}")
    print(f"   Duration: {execution.duration_ms}ms\n")
    
    print("3. Querying results...")
    # Query performance metrics
    query = MemoryQuery()
    query.with_category("metrics")
    query.add_filter("tags", QueryOperator.CONTAINS, "project")
    results = memory.query(query)
    print(f"   Found {len(results)} project metrics\n")
    
    print("4. Generating report...")
    # Aggregate audit data
    total_operations = audit.query_logs(limit=100)
    failed_operations = audit.query_logs(success=False, limit=100)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "memory_entries": len(memory.query(MemoryQuery())),
        "total_operations": len(total_operations),
        "failed_operations": len(failed_operations),
        "macro_executions": len(engine.get_execution_history()),
    }
    
    print(f"   Report generated:")
    for key, value in report.items():
        print(f"     {key}: {value}")
    print()
    
    print("✅ Complete workflow executed successfully!")
    print()


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "CXFlow Enhanced Capabilities Demo" + " " * 15 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")
    
    try:
        demo_enhanced_memory()
        print()
        
        demo_macro_execution()
        print()
        
        demo_macro_templates()
        print()
        
        demo_audit_logging()
        print()
        
        demo_complete_workflow()
        
        print("=" * 60)
        print("All demos completed successfully! ✅")
        print("=" * 60)
        print()
        print("Enhanced features demonstrated:")
        print("  ✓ Advanced query engine with filtering and aggregation")
        print("  ✓ Macro execution with conditionals and loops")
        print("  ✓ Versioning and rollback capabilities")
        print("  ✓ Audit logging for compliance")
        print("  ✓ Macro templates for rapid development")
        print("  ✓ Batch operations for efficiency")
        print("  ✓ Full-text search across memory")
        print("  ✓ Export/import capabilities")
        print()
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
