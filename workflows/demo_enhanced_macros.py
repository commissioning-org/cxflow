#!/usr/bin/env python3
"""
Demonstration script for enhanced macro capabilities.

This script shows how to load, validate, and execute the enhanced macros.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflows.cxflow_enhanced import (
    MacroExecutionEngine,
    EnhancedMemoryManager,
    ValidationSchema,
    AuditLogger,
)


def demo_intro():
    """Display introduction."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 5 + "Enhanced Macro Capabilities Demonstration" + " " * 11 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")
    print("This demonstration shows the significantly enhanced macro")
    print("capabilities in .cxflow/macros, including:")
    print()
    print("  ✓ Conditional logic (if/then/else)")
    print("  ✓ Loops and iterations")
    print("  ✓ Data transformations")
    print("  ✓ Error handling and retry logic")
    print("  ✓ Memory management")
    print("  ✓ Multi-stage workflows")
    print("  ✓ Nested operations")
    print("  ✓ Variable resolution")
    print("  ✓ Self-healing capabilities")
    print()


def demo_macro_overview():
    """Show overview of all macros."""
    print("=" * 60)
    print("Available Enhanced Macros")
    print("=" * 60)
    print()
    
    macro_dir = Path(".cxflow/macros")
    macros = sorted(macro_dir.glob("*.json"))
    
    for macro_file in macros:
        data = json.loads(macro_file.read_text())
        name = data["name"]
        description = data["description"]
        version = data.get("version", "1.0.0")
        features = data.get("metadata", {}).get("features", [])
        
        print(f"📋 {name} (v{version})")
        print(f"   {description}")
        if features:
            print(f"   Features: {', '.join(features[:3])}")
            if len(features) > 3:
                print(f"            {', '.join(features[3:])}")
        print()


def demo_simple_execution():
    """Demonstrate simple macro execution."""
    print("=" * 60)
    print("Demo 1: Simple Macro Execution")
    print("=" * 60)
    print()
    
    # Initialize components
    memory = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
        enable_versioning=True,
    )
    engine = MacroExecutionEngine(memory)
    
    # Load build_docs macro
    macro = json.loads(Path(".cxflow/macros/build_docs.json").read_text())
    
    print(f"Executing: {macro['name']}")
    print(f"Description: {macro['description']}")
    print()
    
    # Execute with context
    context = {
        "timestamp": datetime.now().isoformat(),
        "commit_sha": "abc123def456",
    }
    
    print("Context:")
    for key, value in context.items():
        print(f"  {key}: {value}")
    print()
    
    execution = engine.execute_macro(macro, context=context, dry_run=True)
    
    print(f"Status: {execution.status.value}")
    print(f"Duration: {execution.duration_ms}ms")
    print(f"Steps: {execution.steps_completed}/{execution.steps_total}")
    print()


def demo_conditional_logic():
    """Demonstrate conditional logic."""
    print("=" * 60)
    print("Demo 2: Conditional Logic")
    print("=" * 60)
    print()
    
    memory = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
    )
    engine = MacroExecutionEngine(memory)
    
    # Load conditional_alerts macro
    macro = json.loads(Path(".cxflow/macros/conditional_alerts.json").read_text())
    
    print(f"Executing: {macro['name']}")
    print("Demonstrates: Priority-based routing with nested conditionals")
    print()
    
    # Test with different priorities
    for priority in ["high", "medium", "low"]:
        print(f"Testing with priority: {priority}")
        
        context = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": "system_error",
            "priority": priority,
            "alert_message": f"Test alert with {priority} priority",
            "alert_count": 5,
        }
        
        execution = engine.execute_macro(macro, context=context, dry_run=True)
        
        print(f"  Status: {execution.status.value}")
        print(f"  Actions: {execution.steps_completed} steps executed")
        print()


def demo_loops():
    """Demonstrate loop functionality."""
    print("=" * 60)
    print("Demo 3: Loops and Iterations")
    print("=" * 60)
    print()
    
    memory = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
    )
    engine = MacroExecutionEngine(memory)
    
    # Load batch_processing macro
    macro = json.loads(Path(".cxflow/macros/batch_processing.json").read_text())
    
    print(f"Executing: {macro['name']}")
    print("Demonstrates: Nested loops for batch and stage processing")
    print()
    
    context = {
        "timestamp": datetime.now().isoformat(),
        "items": ["item1", "item2", "item3", "item4", "item5"],
    }
    
    memory.set("batch_config", {"size": 100}, category="test")
    
    execution = engine.execute_macro(macro, context=context, dry_run=True)
    
    print(f"Status: {execution.status.value}")
    print(f"Duration: {execution.duration_ms}ms")
    
    # Count loop iterations
    iterations = 0
    for key, value in execution.results.items():
        if isinstance(value, dict) and "iterations" in value:
            iterations += value["iterations"]
    
    print(f"Total loop iterations: {iterations}")
    print()


def demo_self_healing():
    """Demonstrate self-healing workflow."""
    print("=" * 60)
    print("Demo 4: Self-Healing Workflow")
    print("=" * 60)
    print()
    
    memory = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
    )
    engine = MacroExecutionEngine(memory)
    
    # Load self_healing macro
    macro = json.loads(Path(".cxflow/macros/self_healing_workflow.json").read_text())
    
    print(f"Executing: {macro['name']}")
    print("Demonstrates: Automatic recovery with rollback")
    print()
    
    # Store initial state
    memory.set("service_test_service_state", {"version": "1.0", "config": "stable"})
    
    context = {
        "timestamp": datetime.now().isoformat(),
        "service_name": "test_service",
    }
    
    execution = engine.execute_macro(macro, context=context, dry_run=True)
    
    print(f"Status: {execution.status.value}")
    print(f"Duration: {execution.duration_ms}ms")
    print(f"Steps: {execution.steps_completed}/{execution.steps_total}")
    print()
    print("Features demonstrated:")
    print("  ✓ Health checks")
    print("  ✓ Multi-attempt recovery (5 attempts)")
    print("  ✓ State management for rollback")
    print("  ✓ Nested conditionals")
    print()


def demo_etl_pipeline():
    """Demonstrate ETL pipeline."""
    print("=" * 60)
    print("Demo 5: Advanced ETL Pipeline")
    print("=" * 60)
    print()
    
    memory = EnhancedMemoryManager(
        storage_path=Path("/tmp/cxflow_demo/memory"),
    )
    engine = MacroExecutionEngine(memory)
    
    # Load etl_pipeline macro
    macro = json.loads(Path(".cxflow/macros/etl_pipeline.json").read_text())
    
    print(f"Executing: {macro['name']}")
    print("Demonstrates: Multi-stage ETL with validation and rollback")
    print()
    
    context = {
        "timestamp": datetime.now().isoformat(),
        "pipeline_name": "customer_data_pipeline",
        "data": {"customers": 1000, "orders": 5000},
    }
    
    execution = engine.execute_macro(macro, context=context, dry_run=True)
    
    print(f"Status: {execution.status.value}")
    print(f"Duration: {execution.duration_ms}ms")
    print()
    print("Pipeline stages:")
    print("  1. Extract from: database, API, files")
    print("  2. Transform: clean, normalize, enrich, aggregate")
    print("  3. Load to: warehouse, data_lake, analytics")
    print()
    print("Features:")
    print("  ✓ Multi-source extraction")
    print("  ✓ Multiple transformation steps")
    print("  ✓ Parallel loading")
    print("  ✓ Validation with rollback")
    print()


def demo_statistics():
    """Show statistics about enhanced macros."""
    print("=" * 60)
    print("Enhanced Macro Statistics")
    print("=" * 60)
    print()
    
    macro_dir = Path(".cxflow/macros")
    macros = list(macro_dir.glob("*.json"))
    
    feature_counts = {}
    total_actions = 0
    enhanced_count = 0
    
    for macro_file in macros:
        data = json.loads(macro_file.read_text())
        
        # Count enhanced
        if data.get("metadata", {}).get("enhanced"):
            enhanced_count += 1
        
        # Count actions
        total_actions += len(data.get("actions", []))
        
        # Count features
        for feature in data.get("metadata", {}).get("features", []):
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
    
    print(f"Total Macros: {len(macros)}")
    print(f"Enhanced Macros: {enhanced_count} ({enhanced_count/len(macros)*100:.0f}%)")
    print(f"Average Actions per Macro: {total_actions/len(macros):.1f}")
    print()
    print("Top Features:")
    
    sorted_features = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (feature, count) in enumerate(sorted_features[:10], 1):
        print(f"  {i:2}. {feature:<30} {count} macros")
    print()


def main():
    """Run all demonstrations."""
    try:
        demo_intro()
        demo_macro_overview()
        demo_simple_execution()
        demo_conditional_logic()
        demo_loops()
        demo_self_healing()
        demo_etl_pipeline()
        demo_statistics()
        
        print("=" * 60)
        print("✅ Demonstration Complete!")
        print("=" * 60)
        print()
        print("All enhanced macros successfully demonstrated.")
        print()
        print("To learn more:")
        print("  📖 Read docs/ENHANCED_MACROS.md")
        print("  🧪 Run workflows/test_enhanced_macros.py")
        print("  📝 Explore .cxflow/macros/*.json")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
